"""Testes do parser e dos tradutores da linguagem padrão de busca (query_language)."""

import pytest

from src.SeachDataBases.query_language import (
    And,
    Not,
    Or,
    QueryParseError,
    QueryTranslationError,
    Term,
    parse_query,
    translate,
)


# =============================================================================
# Parser
# =============================================================================

def test_parse_termo_simples():
    parsed = parse_query("agents")
    assert parsed.root == Term("agents", phrase=False)
    assert parsed.warnings == []


def test_parse_frase_aspas_duplas():
    parsed = parse_query('"large language model"')
    assert parsed.root == Term("large language model", phrase=True)


def test_parse_frase_aspas_simples():
    parsed = parse_query("'large language model'")
    assert parsed.root == Term("large language model", phrase=True)


def test_parse_and_or_com_precedencia():
    parsed = parse_query('"a" AND "b" OR "c"')
    # AND tem precedência sobre OR
    assert parsed.root == Or([And([Term("a", True), Term("b", True)]), Term("c", True)])


def test_parse_parenteses_definem_precedencia():
    parsed = parse_query('"a" AND ("b" OR "c")')
    assert parsed.root == And([Term("a", True), Or([Term("b", True), Term("c", True)])])


def test_parse_operadores_case_insensitive():
    parsed = parse_query('"a" and "b" or "c"')
    assert parsed.root == Or([And([Term("a", True), Term("b", True)]), Term("c", True)])


def test_parse_not():
    parsed = parse_query('"a" AND NOT "b"')
    assert parsed.root == And([Term("a", True), Not(Term("b", True))])


def test_parse_in_vira_and_com_or():
    parsed = parse_query('"agents" IN ("LLM", "GPT", "Claude")')
    assert parsed.root == And([
        Term("agents", True),
        Or([Term("LLM", True), Term("GPT", True), Term("Claude", True)]),
    ])


def test_parse_query_exemplo_do_config():
    query = (
        '("agents" AND "multi") AND ("LLM" OR "large language model" OR "generative AI") '
        'AND ("organization" OR "coordination")'
    )
    parsed = parse_query(query)
    assert isinstance(parsed.root, And)
    assert len(parsed.root.children) == 3
    assert parsed.warnings == []


def test_parse_and_implicito_gera_aviso():
    parsed = parse_query('"a" "b"')
    assert parsed.root == And([Term("a", True), Term("b", True)])
    assert any("AND" in w for w in parsed.warnings)


def test_parse_erro_parentese_desbalanceado():
    with pytest.raises(QueryParseError):
        parse_query('("a" AND "b"')


def test_parse_erro_parentese_extra():
    with pytest.raises(QueryParseError):
        parse_query('"a" AND "b")')


def test_parse_erro_vazio():
    with pytest.raises(QueryParseError):
        parse_query("   ")


def test_parse_erro_operador_sem_termo():
    with pytest.raises(QueryParseError):
        parse_query('"a" AND')


def test_parse_wildcard_preservado_no_termo():
    parsed = parse_query("organi%")
    assert parsed.root == Term("organi%", phrase=False)


# =============================================================================
# Tradutores por API
# =============================================================================

def test_arxiv_restringe_a_titulo_e_resumo():
    resultado = translate('"agents" AND "multi"', "arxiv")
    assert resultado.query == (
        '((ti:"agents" OR abs:"agents") AND (ti:"multi" OR abs:"multi"))'
    )


def test_arxiv_not_vira_andnot():
    resultado = translate('"agents" AND NOT "survey"', "arxiv")
    assert resultado.query == (
        '((ti:"agents" OR abs:"agents") ANDNOT (ti:"survey" OR abs:"survey"))'
    )


def test_arxiv_remove_wildcard_com_aviso():
    resultado = translate("organi%", "arxiv")
    assert resultado.query == "(ti:organi OR abs:organi)"
    assert any("curinga" in w.lower() or "%" in w for w in resultado.warnings)


def test_scopus_usa_title_abs_key():
    resultado = translate('("agents" AND "multi") AND ("LLM" OR "generative AI")', "scopus")
    assert resultado.query == (
        'TITLE-ABS-KEY((("agents" AND "multi") AND ("LLM" OR "generative AI")))'
    )
    assert resultado.warnings == []


def test_scopus_wildcard_vira_asterisco():
    resultado = translate('"organi%"', "scopus")
    assert resultado.query == 'TITLE-ABS-KEY("organi*")'
    assert resultado.warnings == []


def test_scopus_wildcard_com_prefixo_curto_gera_aviso():
    resultado = translate('"or%"', "scopus")
    assert any("3" in w for w in resultado.warnings)


def test_scopus_not_vira_and_not():
    resultado = translate('"agents" AND NOT "survey"', "scopus")
    assert resultado.query == 'TITLE-ABS-KEY(("agents" AND NOT "survey"))'


def test_wos_usa_ts():
    resultado = translate('"agents" AND ("LLM" OR "large language model")', "web_of_science")
    assert resultado.query == 'TS=(("agents" AND ("LLM" OR "large language model")))'


def test_wos_palavra_sem_aspas_fica_sem_aspas():
    # sem aspas a API aplica lematização (plural/singular)
    resultado = translate("agents AND coordination", "web_of_science")
    assert resultado.query == "TS=((agents AND coordination))"


def test_wos_wildcard_vira_asterisco():
    resultado = translate("organi%", "web_of_science")
    assert resultado.query == "TS=(organi*)"


def test_springer_default_basico_sem_exclude_bibliography():
    # Default (plano Basic): Exclude:Bibliography é premium e geraria HTTP 403
    resultado = translate('"agents" AND "multi"', "spring_nature")
    assert resultado.query == '("agents" AND "multi")'


def test_springer_exclude_bibliography_quando_premium_habilitado(monkeypatch):
    monkeypatch.setenv("SPRINGER_EXCLUDE_BIBLIOGRAPHY", "true")
    resultado = translate('"agents" AND "multi"', "spring_nature")
    assert resultado.query == '("agents" AND "multi") Exclude:Bibliography'


def test_springer_remove_wildcard_com_aviso():
    resultado = translate('"organi%"', "spring_nature")
    assert resultado.query == '"organi"'
    assert len(resultado.warnings) == 1


def test_in_traduzido_em_todas_as_bases():
    resultado = translate('"agents" IN ("LLM", "GPT")', "scopus")
    assert resultado.query == 'TITLE-ABS-KEY(("agents" AND ("LLM" OR "GPT")))'


def test_ieee_expande_para_campos():
    resultado = translate('"agents" AND "multi"', "ieee")
    assert resultado.query == (
        '(("Document Title":"agents" OR "Abstract":"agents" OR "Author Keywords":"agents") '
        'AND ("Document Title":"multi" OR "Abstract":"multi" OR "Author Keywords":"multi"))'
    )


def test_ieee_recua_para_busca_livre_quando_excede_limite():
    # 20 termos * 3 campos = 60 > 40: deve desativar a expansão por campo
    termos = " OR ".join(f'"t{i}"' for i in range(20))
    resultado = translate(termos, "ieee")
    assert '"Document Title"' not in resultado.query
    assert any("limite" in w.lower() for w in resultado.warnings)


def test_ieee_wildcard_vira_asterisco():
    resultado = translate('"organi%"', "ieee")
    assert '"organi*"' in resultado.query


def test_science_direct_qs_simples():
    resultado = translate('"agents" AND ("LLM" OR "generative AI")', "science_direct")
    assert resultado.query == '("agents" AND ("LLM" OR "generative AI"))'


def test_science_direct_remove_wildcard():
    resultado = translate('"organi%"', "science_direct")
    assert resultado.query == '"organi"'
    assert len(resultado.warnings) == 1


def test_science_direct_avisa_quando_excede_250_chars():
    termos = " OR ".join(f'"termo numero {i}"' for i in range(40))
    resultado = translate(termos, "science_direct")
    assert any("250" in w for w in resultado.warnings)


def test_base_desconhecida_levanta_erro():
    with pytest.raises(ValueError):
        translate('"a"', "google_scholar")


# =============================================================================
# Regressões (achados da verificação adversarial)
# =============================================================================

def test_ieee_um_curinga_nao_dispara_aviso_de_limite():
    # 'organi%' é UM termo com curinga, ainda que expandido em 3 campos
    resultado = translate("organi%", "ieee")
    assert not any("2 palavras com curinga" in w for w in resultado.warnings)


def test_ieee_tres_curingas_disparam_aviso_de_limite():
    resultado = translate("organi% AND compan% AND sys%", "ieee")
    assert any("2 palavras com curinga" in w for w in resultado.warnings)


def test_wos_truncamento_a_esquerda_nao_avisa():
    # %agents tem 6 caracteres após o curinga: válido no WoS (truncamento à esquerda)
    resultado = translate("%agents", "web_of_science")
    assert resultado.query == "TS=(*agents)"
    assert resultado.warnings == []


def test_wos_prefixo_curto_ainda_avisa():
    resultado = translate("or%", "web_of_science")
    assert any("3 caracteres" in w for w in resultado.warnings)


def test_scopus_truncamento_a_esquerda_avisa_pois_nao_permitido():
    # Scopus exige caracteres ANTES do curinga; '%agents' deve gerar aviso
    resultado = translate('"%agents"', "scopus")
    assert any("não permite curinga no início" in w for w in resultado.warnings)


def test_or_not_em_base_binaria_levanta_erro_claro():
    with pytest.raises(QueryTranslationError, match="AND NOT"):
        translate('"a" OR NOT "b"', "web_of_science")
    with pytest.raises(QueryTranslationError):
        translate('"a" OR NOT "b"', "scopus")
    with pytest.raises(QueryTranslationError):
        translate('"a" OR NOT "b"', "arxiv")


def test_or_not_valido_no_science_direct():
    # ScienceDirect aceita NOT isolado (qs: "NOT London")
    resultado = translate('"a" OR NOT "b"', "science_direct")
    assert resultado.query == '("a" OR NOT "b")'
