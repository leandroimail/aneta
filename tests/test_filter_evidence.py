"""Testes da decisão + evidência por artigo do filtro de relevância.

Tudo offline: sem rede e sem tocar em .data. Usa registros consolidados sintéticos
e DuckDB em memória. Cobre:
  - extract_predicates: localiza as comparações atômicas do clause SQL;
  - annotate_with_decision: decisão (_selected) + motivo (_selection_reason) por artigo;
  - build_selection_reason: formatação do motivo (✓/✗) e fallback sem predicados;
  - consistência da divisão selecionado/rejeitado com a avaliação do DuckDB;
  - write_decision_excel: gera as abas esperadas e as colunas selecionado/motivo.
"""

import pandas as pd
import pytest

from src.FilterRelevantPapers import (
    extract_predicates,
    build_selection_reason,
    annotate_with_decision,
    write_decision_excel,
)


# Clause autossuficiente (espelha o padrão atual do projeto), independente do YAML real.
CLAUSE = (
    "is_relevant_yes_percent >= 65 AND total_responses >= 2 "
    "AND principal_research_question_yes_percent >= 65 "
    "AND principal_research_question_total_count >= 2"
)


def _records():
    """3 artigos: 1 selecionado, 2 rejeitados (por motivos diferentes)."""
    base = {
        "providers": "OpenAI, Gemini, DeepSeek",
        "models": "m1, m2, m3",
        "is_relevant_total_count": 3,
        "principal_research_question_total_count": 3,
    }
    return [
        # SELECIONADO: tudo acima do limiar
        {**base, "_response_id": "00001", "id": "a1", "doi": "10.1/x",
         "article_title": "Paper One", "total_responses": 3,
         "is_relevant_yes_percent": 100.0,
         "principal_research_question_yes_percent": 66.67},
        # REJEITADO: is_relevant abaixo de 65
        {**base, "_response_id": "00002", "id": "a2", "doi": "10.1/y",
         "article_title": "Paper Two", "total_responses": 3,
         "is_relevant_yes_percent": 40.0,
         "principal_research_question_yes_percent": 80.0},
        # REJEITADO: poucas respostas (total_responses < 2)
        {**base, "_response_id": "00003", "id": "a3", "doi": "10.1/z",
         "article_title": "Paper Three", "total_responses": 1,
         "is_relevant_yes_percent": 100.0,
         "principal_research_question_yes_percent": 100.0,
         "principal_research_question_total_count": 1},
    ]


# =============================================================================
# extract_predicates
# =============================================================================

def test_extract_predicates_acha_quatro_comparacoes():
    known = set(_records()[0].keys())
    preds = extract_predicates(CLAUSE, known)
    assert preds == [
        ("is_relevant_yes_percent", ">=", "65"),
        ("total_responses", ">=", "2"),
        ("principal_research_question_yes_percent", ">=", "65"),
        ("principal_research_question_total_count", ">=", "2"),
    ]


def test_extract_predicates_ignora_coluna_desconhecida():
    # 'coluna_inexistente' não está nas colunas reais -> não vira predicado.
    preds = extract_predicates("coluna_inexistente >= 10 AND total_responses >= 2",
                               {"total_responses"})
    assert preds == [("total_responses", ">=", "2")]


# =============================================================================
# build_selection_reason
# =============================================================================

def test_build_reason_selecionado_marca_passou():
    rec = {"is_relevant_yes_percent": 100.0, "total_responses": 3}
    preds = [("is_relevant_yes_percent", ">=", "65"), ("total_responses", ">=", "2")]
    reason = build_selection_reason(rec, preds, [True, True], selected=True)
    assert reason.startswith("SELECIONADO —")
    assert "is_relevant_yes_percent=100 (>=65 ✓)" in reason
    assert "total_responses=3 (>=2 ✓)" in reason


def test_build_reason_rejeitado_marca_falhou():
    rec = {"is_relevant_yes_percent": 40.0, "total_responses": 3}
    preds = [("is_relevant_yes_percent", ">=", "65"), ("total_responses", ">=", "2")]
    reason = build_selection_reason(rec, preds, [False, True], selected=False)
    assert reason.startswith("REJEITADO —")
    assert "is_relevant_yes_percent=40 (>=65 ✗)" in reason
    assert "total_responses=3 (>=2 ✓)" in reason


def test_build_reason_sem_predicados_usa_fallback():
    reason = build_selection_reason({}, [], [], selected=True, filter_clause="some_fn(x)")
    assert reason == "SELECIONADO — (filtro: some_fn(x))"


# =============================================================================
# annotate_with_decision (DuckDB avalia, função formata)
# =============================================================================

def test_annotate_decisao_e_motivo_por_artigo():
    annotated = annotate_with_decision(_records(), CLAUSE)
    by_id = {r["id"]: r for r in annotated}

    assert by_id["a1"]["_selected"] is True
    assert by_id["a1"]["_selection_reason"].startswith("SELECIONADO —")

    assert by_id["a2"]["_selected"] is False
    assert "is_relevant_yes_percent=40 (>=65 ✗)" in by_id["a2"]["_selection_reason"]

    assert by_id["a3"]["_selected"] is False
    assert "total_responses=1 (>=2 ✗)" in by_id["a3"]["_selection_reason"]


def test_annotate_consistente_com_duckdb():
    """O conjunto _selected deve bater com uma avaliação direta do mesmo clause."""
    records = _records()
    annotated = annotate_with_decision(records, CLAUSE)
    selected_ids = {r["id"] for r in annotated if r["_selected"]}

    import duckdb
    df = pd.DataFrame(records)
    expected = duckdb.connect(":memory:").execute(
        f"SELECT id FROM df WHERE {CLAUSE}"
    ).fetchdf()["id"].tolist()
    assert selected_ids == set(expected)


def test_annotate_lista_vazia():
    assert annotate_with_decision([], CLAUSE) == []


# =============================================================================
# write_decision_excel
# =============================================================================

def test_write_decision_excel_abas_e_colunas(tmp_path):
    annotated = annotate_with_decision(_records(), CLAUSE)
    preds = extract_predicates(CLAUSE, set(_records()[0].keys()))
    out = tmp_path / "selection_decisions.xlsx"

    write_decision_excel(annotated, str(out), CLAUSE, preds, questions=None)
    assert out.exists()

    sheets = pd.read_excel(out, sheet_name=None)
    assert {"Decisão", "Selecionados", "Rejeitados", "Critério"}.issubset(sheets.keys())

    decisao = sheets["Decisão"]
    assert "selecionado" in decisao.columns
    assert "motivo" in decisao.columns
    # abstract/keywords não entram na planilha de decisão
    assert "article_abstract" not in decisao.columns

    assert len(decisao) == 3
    assert len(sheets["Selecionados"]) == 1
    assert len(sheets["Rejeitados"]) == 2
    assert set(decisao["selecionado"]) <= {"sim", "não"}
