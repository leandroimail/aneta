"""Testes de integração da feature pi-fast + regressões B1/B2.

- B1: raw responses do abstract devem ser salvos POR ARTIGO (sequence+1) na hora,
  para o resume continuar alinhado mesmo com falhas no meio do lote.
- B2: o skip do full-text normaliza DOI (prefixo doi.org, caixa) antes de comparar.
- Consolidação: raws de clients pi devem fluir por process_responses_to_excel
  exatamente como os de clients de API.
"""

import json
import os

import pytest

from dotenv import load_dotenv

from src.GenerativeAI.multi_llm_config import LLMClientConfig
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOneAsync import (
    _process_articles_for_client,
    check_raw_response_exists,
)
from src.GenerativeAI.LLMSelectPapersByFullTextAsync import _normalize_doi
from src.GenerativeAI.LLMUtilExcel import process_responses_to_excel

load_dotenv(".conf")


# --------------------------------------------------------------------------- B1

class _FakeClient:
    """Client falso: prompts com o marcador FALHAR levantam exceção no invoke."""

    def __init__(self):
        self.calls = 0

    async def async_invoke(self, messages):
        self.calls += 1
        prompt = messages[0]["content"]
        if "FALHAR" in prompt:
            raise Exception("provider explodiu (simulado)")
        article_id = "10.1000/a" if "artigo 1" in prompt else "10.1000/c"
        return json.dumps({
            "id": article_id,
            "research_questions": {
                "principal_research_question": {"answer": "yes", "comment": "c"}
            },
            "is_relevant": {"answer": "no", "comment": "c"},
        })


@pytest.mark.asyncio
async def test_b1_raw_saved_per_article_with_mid_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    cfg = LLMClientConfig(id="t", name="t", provider="openai", model_name="m",
                          api_key="x", rate_limit=1000)
    prompts = ["artigo 1", "artigo 2 FALHAR", "artigo 3"]

    await _process_articles_for_client(cfg, _FakeClient(), prompts)

    raw_dir = tmp_path / "OUTPUTS" / "raw_responses" / "t"
    files = sorted(p.name for p in raw_dir.glob("response_*_raw.txt"))
    # artigo 2 falhou → sem response_2; artigos 1 e 3 mantêm os PRÓPRIOS índices
    assert files == ["response_1_t_m_raw.txt", "response_3_t_m_raw.txt"]
    content_3 = (raw_dir / "response_3_t_m_raw.txt").read_text()
    assert "10.1000/c" in content_3  # response_3 é do artigo 3 (não desalinhado)
    assert not check_raw_response_exists(1, "t", "m", str(raw_dir)) is False or True
    assert check_raw_response_exists(0, "t", "m", str(raw_dir)) is True
    assert check_raw_response_exists(1, "t", "m", str(raw_dir)) is False  # falhado
    assert check_raw_response_exists(2, "t", "m", str(raw_dir)) is True


# --------------------------------------------------------------------------- B2

def test_b2_doi_normalization():
    assert _normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert _normalize_doi("http://dx.doi.org/10.1000/x") == "10.1000/x"
    assert _normalize_doi(" 10.1000/X ") == "10.1000/x"
    assert _normalize_doi("") == ""


# --------------------------------------------------------------------------- consolidação

def _analysis_json(doi: str, answer: str) -> str:
    return json.dumps({
        "id": doi,
        "research_questions": {
            "principal_research_question": {"answer": answer, "comment": "c"}
        },
        "is_relevant": {"answer": answer, "comment": "c"},
    })


def test_pi_raws_flow_through_consolidation(tmp_path, monkeypatch):
    base = tmp_path
    monkeypatch.setenv("PATH_DATA", str(base / ".data"))
    raw_dir = base / ".data" / "OUTPUTS" / "raw_responses" / "pi-luna"
    raw_dir.mkdir(parents=True)
    (raw_dir / "response_1_pi-luna_gpt-5.6-luna_raw.txt").write_text(
        _analysis_json("10.1000/one", "yes"), encoding="utf-8")
    (raw_dir / "response_2_pi-luna_gpt-5.6-luna_raw.txt").write_text(
        _analysis_json("10.1000/two", "no"), encoding="utf-8")

    bibs_dir = base / ".data" / "OUTPUTS"
    (bibs_dir / "select_bibs.json").write_text(json.dumps([
        {"id": "10.1000/one", "doi": "10.1000/one", "title": "One",
         "abstract": "a", "keywords": "k"},
        {"id": "10.1000/two", "doi": "10.1000/two", "title": "Two",
         "abstract": "a", "keywords": "k"},
    ]), encoding="utf-8")
    # Config/ (best-effort legend) presente para o caso-sensitive também funcionar
    cfg_dir = base / "Config"
    cfg_dir.mkdir()
    (cfg_dir / "research_questions.yaml").write_text(
        "principal_research_question: 'q?'\n", encoding="utf-8")

    full, simple, consolidated = process_responses_to_excel(
        base_dir=str(base), raw_subdir="raw_responses",
        article_info="select_bibs.json", out_prefix="combined_responses")

    consolidated_json = consolidated.replace("_consolidated.xlsx", "_consolidated.json")
    assert os.path.exists(consolidated_json)
    data = json.load(open(consolidated_json, encoding="utf-8"))
    rows = data if isinstance(data, list) else list(data.values())
    assert len(rows) == 2
    providers = {row["providers"] for row in rows}
    assert providers == {"pi-luna"}
    by_doi = {row["doi"]: row for row in rows}
    assert by_doi["10.1000/one"]["is_relevant_yes_count"] == 1
    assert by_doi["10.1000/two"]["is_relevant_no_count"] == 1
