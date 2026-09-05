"""
Parser e tradutores da linguagem padrão de busca do Aneta.

A linguagem padrão, declarada em ``search_string`` no arquivo
``config/search_config.yaml``, é simples:

  - Operadores lógicos: ``AND``, ``OR``, ``NOT`` (case-insensitive);
  - ``IN``: ``<expr> IN ("a", "b", "c")`` equivale a ``<expr> AND ("a" OR "b" OR "c")``;
  - Precedência definida por parênteses (sem parênteses: NOT > AND > OR);
  - Termos compostos entre aspas simples ou duplas: ``"large language model"``;
  - Termos simples sem aspas: ``agents``;
  - Filtro parcial com ``%`` no estilo SQL LIKE: ``organi%`` casa
    "organization", "organizational" etc. (traduzido para o curinga de cada API).

Cada base científica possui sua própria sintaxe. Este módulo converte a
linguagem padrão para a sintaxe oficial de cada API, restringindo a busca a
título/resumo/palavras-chave sempre que a API permitir — o que aumenta a
precisão (menos resultados irrelevantes) em relação à busca em "todos os
campos" (que em algumas bases inclui referências citadas e texto completo).

Uso típico em um script de busca::

    from src.SeachDataBases.query_language import translate

    resultado = translate(search_string, "scopus")
    for w in resultado.warnings:
        print(f"[AVISO] {w}")
    params = {"query": resultado.query, ...}
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Union

# =============================================================================
# Erros e resultado
# =============================================================================

class QueryParseError(ValueError):
    """Erro de sintaxe na linguagem padrão de busca."""


class QueryTranslationError(ValueError):
    """A expressão é válida, mas não pode ser representada na API alvo."""


@dataclass
class TranslatedQuery:
    """Resultado de uma tradução: a query no formato da API + avisos."""
    query: str
    warnings: List[str] = field(default_factory=list)


# =============================================================================
# AST
# =============================================================================

@dataclass
class Term:
    text: str
    phrase: bool = False  # True quando o termo veio entre aspas (simples ou duplas)


@dataclass
class Not:
    child: "Node"


@dataclass
class And:
    children: List["Node"]


@dataclass
class Or:
    children: List["Node"]


Node = Union[Term, Not, And, Or]


# =============================================================================
# Tokenizador
# =============================================================================

@dataclass
class _Token:
    type: str           # LP, RP, COMMA, AND, OR, NOT, IN, TERM
    text: str = ""
    phrase: bool = False


_TOKEN_RE = re.compile(
    r"""
      (?P<space>\s+)
    | (?P<lparen>\()
    | (?P<rparen>\))
    | (?P<comma>,)
    | (?P<dquote>"[^"]*")
    | (?P<squote>'[^']*')
    | (?P<word>[^\s(),'"]+)
    """,
    re.VERBOSE,
)

_OPERATORS = {"AND": "AND", "OR": "OR", "NOT": "NOT", "IN": "IN", "ANDNOT": "ANDNOT"}


def _tokenize(query: str) -> List[_Token]:
    tokens: List[_Token] = []
    pos = 0
    for match in _TOKEN_RE.finditer(query):
        if match.start() != pos:
            raise QueryParseError(
                f"Caractere inesperado na posição {pos}: {query[pos:match.start()]!r}"
            )
        pos = match.end()
        kind = match.lastgroup
        text = match.group()
        if kind == "space":
            continue
        if kind == "lparen":
            tokens.append(_Token("LP"))
        elif kind == "rparen":
            tokens.append(_Token("RP"))
        elif kind == "comma":
            tokens.append(_Token("COMMA"))
        elif kind in ("dquote", "squote"):
            inner = text[1:-1].strip()
            if not inner:
                raise QueryParseError("Termo vazio entre aspas na search_string")
            tokens.append(_Token("TERM", inner, phrase=True))
        else:  # word
            op = _OPERATORS.get(text.upper())
            if op == "ANDNOT":
                tokens.append(_Token("AND"))
                tokens.append(_Token("NOT"))
            elif op:
                tokens.append(_Token(op))
            else:
                tokens.append(_Token("TERM", text))
    if pos != len(query):
        raise QueryParseError(f"Caractere inesperado na posição {pos}: {query[pos:]!r}")
    if not tokens:
        raise QueryParseError("search_string vazia")
    return tokens


# =============================================================================
# Parser (descida recursiva)
#   or_expr  := and_expr ((OR | ,) and_expr)*
#   and_expr := not_expr ((AND)? not_expr)*      -- AND implícito gera aviso
#   not_expr := NOT not_expr | postfix
#   postfix  := atom (IN '(' lista ')')*
#   atom     := '(' or_expr ')' | TERM
# =============================================================================

class _Parser:
    def __init__(self, tokens: List[_Token]):
        self.tokens = tokens
        self.i = 0
        self.warnings: List[str] = []

    def _peek(self) -> Optional[_Token]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _peek_type(self) -> Optional[str]:
        tok = self._peek()
        return tok.type if tok else None

    def _next(self) -> _Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self._parse_or()
        if self._peek() is not None:
            tok = self._peek()
            raise QueryParseError(
                f"Token inesperado após o fim da expressão: {tok.text or tok.type!r}"
                " — verifique parênteses desbalanceados"
            )
        return node

    def _parse_or(self) -> Node:
        items = [self._parse_and()]
        while self._peek_type() in ("OR", "COMMA"):
            if self._peek_type() == "COMMA":
                self.warnings.append(
                    "Vírgula fora de lista IN interpretada como OR"
                )
            self._next()
            items.append(self._parse_and())
        return items[0] if len(items) == 1 else Or(items)

    def _parse_and(self) -> Node:
        items = [self._parse_not()]
        while True:
            t = self._peek_type()
            if t == "AND":
                self._next()
                items.append(self._parse_not())
            elif t in ("TERM", "LP", "NOT"):
                # termos adjacentes sem operador explícito
                self.warnings.append(
                    "Termos adjacentes sem operador foram interpretados como AND"
                )
                items.append(self._parse_not())
            else:
                break
        return items[0] if len(items) == 1 else And(items)

    def _parse_not(self) -> Node:
        if self._peek_type() == "NOT":
            self._next()
            return Not(self._parse_not())
        return self._parse_postfix()

    def _parse_postfix(self) -> Node:
        node = self._parse_atom()
        while self._peek_type() == "IN":
            self._next()
            if self._peek_type() != "LP":
                raise QueryParseError("IN deve ser seguido de uma lista entre parênteses")
            self._next()
            items: List[Node] = []
            expecting_term = True
            while True:
                t = self._peek_type()
                if t == "TERM":
                    tok = self._next()
                    items.append(Term(tok.text, tok.phrase))
                    expecting_term = False
                elif t in ("COMMA", "OR"):
                    self._next()
                    expecting_term = True
                elif t == "RP":
                    self._next()
                    break
                elif t is None:
                    raise QueryParseError("Lista do IN não foi fechada com ')'")
                else:
                    raise QueryParseError(
                        "Apenas termos separados por vírgula ou OR são permitidos na lista do IN"
                    )
            if not items:
                raise QueryParseError("Lista do IN está vazia")
            del expecting_term
            grouped: Node = items[0] if len(items) == 1 else Or(items)
            node = And([node, grouped])
        return node

    def _parse_atom(self) -> Node:
        tok = self._peek()
        if tok is None:
            raise QueryParseError("Fim inesperado da expressão — faltou um termo")
        if tok.type == "LP":
            self._next()
            node = self._parse_or()
            if self._peek_type() != "RP":
                raise QueryParseError("Parêntese aberto sem fechamento")
            self._next()
            return node
        if tok.type == "TERM":
            self._next()
            return Term(tok.text, tok.phrase)
        raise QueryParseError(f"Token inesperado: {tok.text or tok.type}")


def parse_query(query: str) -> "ParsedQuery":
    """Faz o parse da linguagem padrão e retorna a AST + avisos de parse."""
    cleaned = " ".join(query.split())
    parser = _Parser(_tokenize(cleaned))
    node = parser.parse()
    return ParsedQuery(node, parser.warnings)


@dataclass
class ParsedQuery:
    root: Node
    warnings: List[str]


# =============================================================================
# Utilitários comuns aos emissores
# =============================================================================

def _map_wildcards(text: str, symbol: Optional[str], api_name: str,
                   warnings: List[str], min_prefix: int = 0,
                   allow_left_trunc: bool = False) -> str:
    """
    Converte ``%`` para o curinga da API (ou remove, com aviso, se não houver).

    ``min_prefix``: nº mínimo de caracteres literais exigido junto ao curinga.
    Para truncamento à direita (``abc%``) conta-se o prefixo antes do ``%``.
    ``allow_left_trunc``: quando a API aceita truncamento à esquerda (``%abc``,
    ex.: Web of Science), conta-se o sufixo depois do último ``%`` em vez do
    prefixo. Caso contrário, ``%`` no início já viola a regra de prefixo.
    """
    if "%" not in text:
        return text
    if symbol is None:
        stripped = text.replace("%", "")
        warnings.append(
            f"{api_name} não suporta curinga: '%' removido do termo '{text}' "
            f"(buscando '{stripped}')"
        )
        return stripped
    if min_prefix:
        if text.startswith("%"):
            # Truncamento à esquerda: a regra recai sobre os caracteres após o %
            suffix = text.rsplit("%", 1)[-1]
            if not allow_left_trunc:
                warnings.append(
                    f"{api_name} não permite curinga no início do termo '{text}' "
                    f"(exige ao menos {min_prefix} caracteres antes do curinga) "
                    f"— a API pode rejeitar a consulta"
                )
            elif len(suffix) < min_prefix:
                warnings.append(
                    f"{api_name} exige ao menos {min_prefix} caracteres após o curinga "
                    f"no termo '{text}' — a API pode rejeitar a consulta"
                )
        else:
            prefix = text.split("%", 1)[0]
            if len(prefix) < min_prefix:
                warnings.append(
                    f"{api_name} exige ao menos {min_prefix} caracteres antes do curinga "
                    f"no termo '{text}' — a API pode rejeitar a consulta"
                )
    return text.replace("%", symbol)


# =============================================================================
# Emissor genérico de expressão booleana infixa
# =============================================================================

def _render_boolean(node: Node, term_fn, and_word: str = "AND",
                    or_word: str = "OR", not_word: Optional[str] = "NOT",
                    not_is_binary: bool = False) -> str:
    """
    Serializa a AST como expressão booleana infixa.

    term_fn(Term) -> str é fornecido por cada API.
    not_is_binary=True emite ``A <not_word> B`` (ex.: arXiv ``ANDNOT``,
    Scopus ``AND NOT``) — exige que o Not seja filho de um And com um termo
    positivo antes dele.
    """

    def render(n: Node) -> str:
        if isinstance(n, Term):
            return term_fn(n)
        if isinstance(n, Or):
            return "(" + f" {or_word} ".join(render(c) for c in n.children) + ")"
        if isinstance(n, And):
            parts: List[str] = []
            for child in n.children:
                if isinstance(child, Not) and not_is_binary:
                    if not parts:
                        raise QueryTranslationError(
                            f"NOT no início de um grupo não é suportado nesta API "
                            f"(use 'termo {not_word} termo')"
                        )
                    parts.append(f"{not_word} {render(child.child)}")
                elif isinstance(child, Not):
                    parts.append(f"{not_word} {render(child.child)}")
                    # vira "... AND NOT x" naturalmente via join abaixo
                else:
                    parts.append(render(child))
            if not_is_binary:
                # filhos Not já carregam o operador; join apenas com espaço p/ eles
                out = parts[0]
                for raw, child in zip(parts[1:], n.children[1:]):
                    if isinstance(child, Not):
                        out += f" {raw}"
                    else:
                        out += f" {and_word} {raw}"
                return "(" + out + ")"
            return "(" + f" {and_word} ".join(parts) + ")"
        if isinstance(n, Not):
            if not_word is None or not_is_binary:
                raise QueryTranslationError(
                    "Esta base só aceita NOT como operador binário, logo após um "
                    "termo positivo (ex.: 'termo AND NOT outro'). Construções como "
                    "'A OR NOT B' ou 'NOT B' isolado não são suportadas — reescreva "
                    "a search_string usando 'AND NOT' para a exclusão."
                )
            return f"{not_word} {render(n.child)}"
        raise QueryTranslationError(f"Nó desconhecido: {n!r}")

    return render(node)


# =============================================================================
# Emissores por API (preenchidos conforme a documentação oficial de cada base)
# =============================================================================

def to_arxiv(parsed: ParsedQuery) -> TranslatedQuery:
    """
    arXiv API (https://info.arxiv.org/help/api/user-manual.html).

    - Campos: cada termo é restrito a título OU resumo: ``(ti:"x" OR abs:"x")``
      (o arXiv não tem campo de palavras-chave; ``all:`` buscaria também em
      comentários, journal-ref etc., reduzindo a precisão).
    - Operadores: AND, OR, ANDNOT (NOT vira ANDNOT, sempre binário).
    - Frases entre aspas duplas; curingas NÃO são suportados (removidos com aviso).
    """
    warnings = list(parsed.warnings)

    def term_fn(t: Term) -> str:
        text = _map_wildcards(t.text, None, "arXiv", warnings)
        if t.phrase or " " in text or "-" in text:
            rendered = f'"{text}"'
        else:
            rendered = text
        return f"(ti:{rendered} OR abs:{rendered})"

    query = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="ANDNOT", not_is_binary=True,
    )
    return TranslatedQuery(query, warnings)


def to_scopus(parsed: ParsedQuery) -> TranslatedQuery:
    """
    Scopus Search API (https://dev.elsevier.com/sc_search_tips.html).

    - Toda a expressão é embrulhada em ``TITLE-ABS-KEY(...)`` — título, resumo
      e palavras-chave. ``ALL()`` incluiria referências citadas, afiliações,
      editora etc. (documentado: ABS, AFFIL, AUTH, PUBLISHER, REF, SRCTITLE...),
      o que infla os resultados.
    - Termos sempre entre aspas duplas ("loose phrase": plurais incluídos,
      pontuação ignorada, curingas ativos) — recomendado para revisão sistemática.
    - ``%`` vira ``*`` (mínimo de 3 caracteres antes do curinga, regra da API).
    - NOT vira ``AND NOT`` (binário, processado por último).
    """
    warnings = list(parsed.warnings)

    def term_fn(t: Term) -> str:
        text = _map_wildcards(t.text, "*", "Scopus", warnings, min_prefix=3)
        return f'"{text}"'

    expr = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="AND NOT", not_is_binary=True,
    )
    return TranslatedQuery(f"TITLE-ABS-KEY({expr})", warnings)


def to_web_of_science(parsed: ParsedQuery) -> TranslatedQuery:
    """
    Web of Science Starter API (https://developer.clarivate.com/apis/wos-starter).

    - ``TS=(...)`` (Topic) busca título, resumo, palavras-chave do autor e
      Keywords Plus — o campo correto para revisão sistemática.
    - Frases entre aspas duplas (casamento exato, sem lematização). Palavras
      simples não citadas ficam sem aspas para manter a lematização
      (plural/singular) da API.
    - ``%`` vira ``*`` (mínimo de 3 caracteres antes, regra da API).
    - NOT é binário (``A NOT B``), sem AND antes.
    """
    warnings = list(parsed.warnings)

    def term_fn(t: Term) -> str:
        text = _map_wildcards(t.text, "*", "Web of Science", warnings,
                              min_prefix=3, allow_left_trunc=True)
        if t.phrase or " " in text:
            return f'"{text}"'
        return text

    expr = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="NOT", not_is_binary=True,
    )
    return TranslatedQuery(f"TS=({expr})", warnings)


_IEEE_FIELDS = ('"Document Title"', '"Abstract"', '"Author Keywords"')
# Limite documentado da plataforma IEEE Xplore (Advanced Search Tips): máximo
# de 40 termos por consulta, contando separadamente as palavras de cada frase.
_IEEE_MAX_WORDS = 40


def to_ieee(parsed: ParsedQuery) -> TranslatedQuery:
    """
    IEEE Xplore Metadata Search API, parâmetro ``querytext``
    (https://developer.ieee.org/docs/read/Metadata_API_details).

    - Cada termo é restrito a título/resumo/palavras-chave do autor via
      sintaxe de campo ``"Document Title":x OR "Abstract":x OR
      "Author Keywords":x`` (sintaxe do Command Search, aceita no querytext).
      Sem isso, ``querytext`` busca em todos os metadados (autores, nome da
      publicação...), inflando os resultados.
    - Se a expansão por campo estourar o limite de 40 termos da plataforma,
      recua para busca livre normalizada (com aviso).
    - Operadores precisam ser MAIÚSCULOS; NOT é binário.
    - ``%`` vira ``*``: mínimo de 3 caracteres antes e no máximo 2 palavras
      com curinga por consulta (regras documentadas da API).
    """
    warnings = list(parsed.warnings)

    def count_words(node: Node) -> int:
        if isinstance(node, Term):
            return len(node.text.split())
        if isinstance(node, Not):
            return count_words(node.child)
        return sum(count_words(child) for child in node.children)

    total_words = count_words(parsed.root)
    expand = total_words * len(_IEEE_FIELDS) <= _IEEE_MAX_WORDS
    if not expand:
        warnings.append(
            f"IEEE: a restrição por campo (título/resumo/palavras-chave) foi "
            f"desativada porque a query expandida teria "
            f"{total_words * len(_IEEE_FIELDS)} termos (limite da plataforma: "
            f"{_IEEE_MAX_WORDS}). A busca usará todos os metadados + resumo."
        )

    wildcard_words = 0

    def term_fn(t: Term) -> str:
        nonlocal wildcard_words
        text = _map_wildcards(t.text, "*", "IEEE Xplore", warnings, min_prefix=3)
        if "*" in text:
            # Conta 1 por termo lógico com curinga (a expansão em 3 campos é só
            # representação sintática — o limite da API é por palavra com curinga).
            wildcard_words += 1
        rendered = f'"{text}"' if (t.phrase or " " in text) else text
        if expand:
            return "(" + " OR ".join(f"{f}:{rendered}" for f in _IEEE_FIELDS) + ")"
        return rendered

    query = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="NOT", not_is_binary=True,
    )
    if wildcard_words > 2:
        warnings.append(
            f"IEEE permite no máximo 2 palavras com curinga por consulta; a "
            f"query traduzida contém {wildcard_words} e pode ser rejeitada"
        )
    return TranslatedQuery(query, warnings)


def to_science_direct(parsed: ParsedQuery) -> TranslatedQuery:
    """
    ScienceDirect Search API V2, campo ``qs`` do corpo PUT
    (https://dev.elsevier.com/tecdoc_sdsearch_migration.html).

    - ``qs`` busca todo o conteúdo do artigo EXCETO as referências; a V2 não
      possui campo título+resumo+palavras-chave (o ``tak`` legado foi removido).
    - Operadores devem ser MAIÚSCULOS — ``and``/``or`` minúsculos são tratados
      como termos de busca pela API (o tradutor normaliza).
    - Frases entre aspas duplas; curingas não são documentados (removidos com
      aviso); limite de 250 caracteres em ``qs`` (aviso quando excedido).
    """
    warnings = list(parsed.warnings)

    def term_fn(t: Term) -> str:
        text = _map_wildcards(t.text, None, "ScienceDirect", warnings)
        if t.phrase or " " in text:
            return f'"{text}"'
        return text

    expr = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="NOT", not_is_binary=False,
    )
    if len(expr) > 250:
        warnings.append(
            f"A API ScienceDirect limita o campo 'qs' a 250 caracteres; a query "
            f"traduzida tem {len(expr)} e pode ser rejeitada — reduza os termos"
        )
    return TranslatedQuery(expr, warnings)


def to_spring_nature(parsed: ParsedQuery) -> TranslatedQuery:
    """
    Springer Nature Meta API v2
    (https://dev.springernature.com/docs/supported-query-params/).

    - Não existe constraint ``abstract:``; termos sem prefixo buscam em
      qualquer elemento do documento.
    - ``Exclude:Bibliography`` (documentado) impediria casar termos que
      aparecem apenas na bibliografia/referências, ganhando precisão — MAS é
      um recurso PREMIUM (a API retorna HTTP 403 em chaves Basic). Por isso
      ele só é adicionado quando ``SPRINGER_EXCLUDE_BIBLIOGRAPHY`` está
      habilitado no .env (default: desligado, compatível com o plano Basic).
    - Termos sempre entre aspas duplas (exigido para frases; %22 na URL).
    - Operadores AND, OR, NOT (NOT binário) e parênteses são documentados.
    - Curingas em palavras NÃO são documentados (removidos com aviso).
    """
    warnings = list(parsed.warnings)

    def term_fn(t: Term) -> str:
        text = _map_wildcards(t.text, None, "Springer Nature", warnings)
        return f'"{text}"'

    expr = _render_boolean(
        parsed.root, term_fn, and_word="AND", or_word="OR",
        not_word="NOT", not_is_binary=True,
    )
    if os.getenv("SPRINGER_EXCLUDE_BIBLIOGRAPHY", "").strip().lower() in ("1", "true", "yes", "sim"):
        expr = f"{expr} Exclude:Bibliography"
    return TranslatedQuery(expr, warnings)


# =============================================================================
# API pública
# =============================================================================

def translate(query: str, target: str) -> TranslatedQuery:
    """
    Traduz a ``search_string`` (linguagem padrão) para a sintaxe oficial da
    base alvo. ``target`` aceita: arxiv, ieee, science_direct, scopus,
    spring_nature, web_of_science (mesmos nomes do search_config.yaml).
    """
    emitters = {
        "arxiv": to_arxiv,
        "ieee": to_ieee,
        "science_direct": to_science_direct,
        "scopus": to_scopus,
        "spring_nature": to_spring_nature,
        "web_of_science": to_web_of_science,
    }
    if target not in emitters:
        raise ValueError(
            f"Base desconhecida: {target!r}. Disponíveis: {sorted(emitters)}"
        )
    return emitters[target](parse_query(query))

