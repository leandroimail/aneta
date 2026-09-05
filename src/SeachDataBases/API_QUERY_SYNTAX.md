# Sintaxe de busca das APIs científicas (referência oficial)

Este documento resume, **a partir da documentação oficial de cada API**, como a
`search_string` (linguagem padrão, em `config/search_config.yaml`) é traduzida
para a sintaxe nativa de cada base. A tradução é feita por
`src/SeachDataBases/query_language.py` (função `translate(query, base)`).

O objetivo é **precisão**: restringir a busca a título/resumo/palavras-chave
sempre que a API permitir, evitando casar termos em referências citadas,
afiliações, nomes de autores ou texto completo — que era a causa do excesso de
resultados.

## Linguagem padrão (DSL)

| Construção | Exemplo | Significado |
|---|---|---|
| Termo simples | `agents` | palavra única (sem aspas) |
| Termo composto | `"large language model"` ou `'large language model'` | frase exata |
| AND / OR / NOT | `"a" AND "b" OR "c"` | precedência `NOT > AND > OR` |
| Parênteses | `("a" OR "b") AND "c"` | sobrescrevem a precedência |
| IN | `"agents" IN ("LLM", "GPT")` | açúcar para `"agents" AND ("LLM" OR "GPT")` |
| Curinga `%` | `organi%` | LIKE: casa `organization`, `organizational`… |

---

## arXiv — `http://export.arxiv.org/api/query`

- **Campos**: `ti` (título), `abs` (resumo), `au`, `cat`, `all`, `co`, `jr`, `rn`, `id`.
  **Não há campo de palavras‑chave** (categorias só via `cat:`).
- **Tradução (precisão)**: cada termo vira `(ti:"x" OR abs:"x")`. `all:` buscaria
  também em comentários, journal‑ref etc.
- **Booleanos**: `AND`, `OR`, `ANDNOT`. `NOT` → `ANDNOT` (binário, sempre `A ANDNOT B`).
- **Frases**: aspas duplas. **Curingas não são documentados** → `%` é removido (com aviso).
- **Paginação/limites**: máx. 2000 por requisição, 30000 no total; **≥ 3 s entre requisições** (Termos de Uso).
- Doc: https://info.arxiv.org/help/api/user-manual.html

## IEEE Xplore — `https://ieeexploreapi.ieee.org/api/v1/search/articles`

- **`querytext`** busca em **todos os metadados + resumo** (não no texto completo) — ainda
  assim casa autores, nome da publicação, afiliações ⇒ excesso de resultados.
- **Tradução (precisão)**: cada termo vira
  `("Document Title":x OR "Abstract":x OR "Author Keywords":x)`
  (sintaxe Command Search aceita no `querytext`).
  **Limite da plataforma: máx. 40 termos** (palavras de uma frase contam separadamente).
  Se a expansão (×3 campos) ultrapassar 40, o tradutor **recua para busca livre**
  em metadados+resumo (com aviso) — degradação graciosa.
- **Booleanos**: `AND`, `OR`, `NOT` **em MAIÚSCULAS** (minúsculas viram termos de busca). `NOT` binário.
- **Curingas**: só `*`; **no máx. 2 palavras com curinga** por consulta; **≥ 3 caracteres antes do `*`**.
- **Paginação**: `max_records` ≤ 200; teto total de 200 resultados.
- Doc: https://developer.ieee.org/docs/read/Metadata_API_details

## ScienceDirect — `PUT https://api.elsevier.com/content/search/sciencedirect` (campo `qs`)

- **`qs`** busca **todo o conteúdo do artigo exceto as referências** (≈ texto completo).
  A **V2 não tem campo título+resumo+palavras‑chave** (o `tak` legado foi removido);
  não há campo de resumo nem de keyword no corpo. ⇒ a precisão depende inteiramente
  dos operadores booleanos da query.
- **Booleanos**: `AND`, `OR`, `NOT` **em MAIÚSCULAS** (minúsculas viram termos). `NOT` pode ser isolado.
- **Frases**: aspas duplas. **Curingas não documentados** → `%` removido (com aviso).
- **Limites**: `qs` ≤ **250 caracteres** (aviso quando excede); `offset` 0–6000; `show` ∈ {10,25,50,100}.
- Doc: https://dev.elsevier.com/tecdoc_sdsearch_migration.html
- **Nota de precisão**: como não há TAK na V2, considere migrar para a *Article Metadata API*
  (`ttl()`, `key()`, `aut()`…) se for necessário restringir a título/keywords. Hoje o
  Aneta usa a V2 (`qs`) seguida de enriquecimento via Article Metadata.

## Scopus — `https://api.elsevier.com/content/search/scopus`

- **`TITLE-ABS-KEY()`** = título + resumo + palavras‑chave (preciso).
  **`ALL()`** inclui **referências citadas (REF)**, afiliações, autores, editora, fonte… ⇒ muito mais amplo.
  *(o script antigo usava `all(...)` — principal causa do excesso de resultados na Scopus.)*
- **Tradução (precisão)**: toda a expressão é envolvida em `TITLE-ABS-KEY(...)`.
- **Booleanos**: `AND`, `OR`, `AND NOT`. Precedência `OR → AND → AND NOT`; parênteses sobrescrevem.
- **Frases**: aspas duplas = *loose phrase* (inclui plurais, ignora pontuação, curingas ativos) — recomendado para revisão sistemática. Chaves `{}` = exato.
- **Curingas**: `*` e `?`; **mínimo de 3 caracteres literais antes do curinga**.
- **Paginação**: COMPLETE ≤ 25/página, STANDARD ≤ 200 (mas o **nível de serviço** da chave
  pode limitar a 25 — `count>25` retorna HTTP 400 "Exceeds the maximum number allowed for the
  service level"; por isso o script limita `count` a 25). Profundidade `start/count` até 5000.
- **View / abstract** (verificado por teste real): a **STANDARD não retorna abstract nem
  author keywords**; a **COMPLETE retorna**, mas só é autorizada nas primeiras ~250 entradas
  (depois HTTP 401) e tem quota própria pequena. O script usa **STANDARD por padrão** (robusta,
  paginação profunda) e o **estágio `--enrich`** preenche o abstract por DOI
  (OpenAlex/Crossref/Semantic Scholar/Scopus Abstract Retrieval) antes do filtro. Para forçar a
  COMPLETE, defina `SCOPUS_VIEW=COMPLETE` no `.env` (o loop faz downgrade automático p/ STANDARD no 401).
- Doc: https://dev.elsevier.com/sc_search_tips.html

## Springer Nature — `https://api.springernature.com/meta/v2/json` (param `q`)

- **Não existe `abstract:`**. Termo sem prefixo = *empty constraint* = busca em **qualquer elemento**
  do registro (inclui o texto da bibliografia). Há `title:` e `keyword:`, mas **não** há restrição
  a título+resumo+keywords (sem `abstract:`), então restringir cortaria os matches só do resumo.
- **`Exclude:Bibliography` é recurso PREMIUM** — chaves Basic recebem **HTTP 403**
  ("premium feature"). Verificado por teste real. Por isso o tradutor **NÃO** o adiciona por padrão;
  para quem tem plano premium, habilite com `SPRINGER_EXCLUDE_BIBLIOGRAPHY=true` no `.env`.
- **Booleanos**: `AND`, `OR`, `NOT`, `NEAR` (maiúsculas nos exemplos); parênteses suportados; constraints implicitamente em AND.
- **Frases**: só aspas duplas. **Curingas em palavras não documentados** → `%` removido (com aviso).
- **Paginação**: `p` ≤ **25** (Basic) / 100 (Premium); 100 req/min, 500/dia (Basic).
- Doc: https://dev.springernature.com/docs/supported-query-params/

## Web of Science Starter — `https://api.clarivate.com/apis/wos-starter/v1/documents` (param `q`)

- **`TS=(...)`** (Topic) = título + resumo + *author keywords* + *Keywords Plus* — campo correto para revisão sistemática.
  (`AB` resumo‑apenas **não** existe no Starter.)
- **Booleanos**: `AND`, `OR`, `NOT`, `NEAR/x`, `SAME` (não sensíveis a caixa). **`AND` não pode coexistir com `NEAR`** na mesma query.
- **Frases**: aspas duplas = exato **e desativa lematização** (`"mouse"` não casa `mice`).
  Palavras simples **sem aspas** mantêm a lematização (plural/singular) — por isso o tradutor
  não coloca aspas em termos de palavra única.
- **Curingas**: `*`, `?`, `$`; **≥ 3 caracteres antes do curinga** em título/tópico.
- **Paginação**: `limit` ≤ **50** (o tradutor força `PAGE_SIZE ≤ 50`); trial 1 req/s, 50/dia.
- **Resposta**: o Starter **não retorna o resumo** (só a API Expanded).
- Doc: https://developer.clarivate.com/apis/wos-starter

---

## Resumo do ganho de precisão

| Base | Antes | Depois |
|---|---|---|
| Scopus | `all(...)` (inclui referências, autores, afiliações) | `TITLE-ABS-KEY(...)` |
| arXiv | `all:termo` (todos os campos) | `(ti:... OR abs:...)` |
| IEEE | `querytext` cru (todos metadados) | campos título/resumo/keywords (recua p/ metadados se > 40 termos) |
| Springer | termo solto (inclui bibliografia) | `+ Exclude:Bibliography` |
| WoS | `TS=(...)` já era ok | mantém `TS=(...)`, sem aspas em palavra única (lematização) |
| ScienceDirect | `qs` (texto completo) | `qs` (sem TAK na V2 — limitação da API documentada) |

## Acurácia da filtragem local (pós-busca)

O `filter_string` (DuckDB, em `Selection.py`) filtra sobre `title`, `abstract` e `keywords`.
Dois ajustes (fora dos tradutores) foram necessários para ele enxergar os dados:

1. **`src/Config.py` → `list_keywords`** agora inclui `author_keywords` (e variantes). Antes,
   bases que entregam as palavras-chave em `author_keywords` (ScienceDirect, WoS, Scopus) ficavam
   com a coluna `keywords` vazia no DuckDB e o filtro cego a elas. Impacto medido nos `.bib` reais:
   WoS 2 → 7 e ScienceDirect 23 → 25 artigos aprovados pelo filtro.
2. **Abstract via enriquecimento**: WoS Starter e Scopus STANDARD não trazem abstract na busca, mas
   o estágio `--enrich` o preenche por DOI antes da seleção. **Rode `--enrich` antes de `--selection`.**

### Tentativas que NÃO valem a pena (verificadas empiricamente)
- **Springer título+resumo**: `title:` e `subject:` são **premium** (HTTP 403 em chave Basic); só
  `keyword:` e termo livre funcionam. Termo livre + filtro local é o melhor possível no plano Basic.
- **ScienceDirect título+keyword** (`ttl`/`key` na Article Metadata API): cortaria o recall de
  9983 → **2** resultados (o resumo é onde os conceitos aparecem). Mantida a busca full-text + filtro local.
