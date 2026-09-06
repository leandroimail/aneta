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
    base = tmp_path / ".data"   # contrato novo: base_dir É o diretório de dados
    monkeypatch.setenv("PATH_DATA", str(base))
    raw_dir = base / "OUTPUTS" / "raw_responses" / "pi-luna"
    raw_dir.mkdir(parents=True)
    (raw_dir / "response_1_pi-luna_gpt-5.6-luna_raw.txt").write_text(
        _analysis_json("10.1000/one", "yes"), encoding="utf-8")
    (raw_dir / "response_2_pi-luna_gpt-5.6-luna_raw.txt").write_text(
        _analysis_json("10.1000/two", "no"), encoding="utf-8")

    bibs_dir = base / "OUTPUTS"
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


# --------------------------------------------------------------------------- pi×legacy

PI_YAML = """
defaults: {thinking: off, timeout_seconds: 200, max_concurrent: 4, rate_limit: 30}
clients:
  - id: pi-glm
    groups: [ABSTRACT]
    provider: zai
    model: glm-5.2
"""


@pytest.fixture()
def pi_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "pi_fast.yaml"
    cfg.write_text(PI_YAML, encoding="utf-8")
    monkeypatch.setenv("PI_FAST_CONFIG_PATH", str(cfg))
    return str(cfg)


def test_sync_flow_filters_pi_without_crash(monkeypatch, pi_yaml):
    """Regressão do NameError: fluxo sync com client pi deve FILTRAR com aviso, não crashar."""
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "pi-glm")
    from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import setup_llms as sync_setup
    with pytest.raises(ValueError, match="Nenhum LLM configurado"):
        sync_setup("ABSTRACT")  # pi filtrado com aviso; erro claro, nada de NameError


def test_legacy_wins_over_yaml_when_configured(monkeypatch, pi_yaml):
    """Roster vazio + single-LLM legado configurado: o legado NÃO é sequestrado pelo YAML pi."""
    monkeypatch.delenv("LLM_CLIENTS_ABSTRACT", raising=False)
    monkeypatch.delenv("LLM_CLIENTS", raising=False)
    monkeypatch.setenv("LLM_MODEL_ABSTRACT", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_API_KEY_ABSTRACT", "sk-legacy")
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    cfgs = load_llm_client_configs("ABSTRACT")
    assert [(c.id, c.provider) for c in cfgs] == [("OpenAI", "openai")]


def test_yaml_pi_used_when_no_roster_and_no_legacy(monkeypatch, pi_yaml):
    monkeypatch.delenv("LLM_CLIENTS_ABSTRACT", raising=False)
    monkeypatch.delenv("LLM_CLIENTS", raising=False)
    monkeypatch.delenv("LLM_MODEL_ABSTRACT", raising=False)
    monkeypatch.delenv("LLM_API_KEY_ABSTRACT", raising=False)
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    cfgs = load_llm_client_configs("ABSTRACT")
    assert [(c.id, c.provider, c.harness_provider) for c in cfgs] == [("pi-glm", "pi", "zai")]


def test_invalid_yaml_yaml_error_is_tolerated(monkeypatch, tmp_path):
    """YAML com sintaxe inválida (tab) não pode derrubar a triagem (era TypeError/YAMLError)."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("clients:\n\t- id: x\n", encoding="utf-8")
    monkeypatch.setenv("PI_FAST_CONFIG_PATH", str(bad))
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-x")
    monkeypatch.setenv("LLM_OPENAI_X_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_X_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_OPENAI_X_API_KEY", "sk-x")
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    cfgs = load_llm_client_configs("ABSTRACT")
    assert [c.id for c in cfgs] == ["openai-x"]  # client de API segue funcionando



# --------------------------------------------------------------------------- rodada 2

class _SyncFakeClient:
    """Client síncrono falso: FALHAR no prompt => invoke levanta; senão JSON válido."""

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
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


def test_b1_sync_resume_recovers_after_mid_failure(monkeypatch, tmp_path):
    """B1 no sync: falha no meio + resume deve recuperar os artigos certos (era 0 antes)."""
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import (
        _process_articles_for_client_sync, clean_and_parse_json,
    )

    cfg = LLMClientConfig(id="t", name="t", provider="openai", model_name="m",
                          api_key="x", rate_limit=1000)
    prompts = ["artigo 1", "artigo 2 FALHAR", "artigo 3"]

    # rodada 1: artigo 2 falha; raws 1 e 3 ficam em disco alinhados
    _process_articles_for_client_sync(cfg, _SyncFakeClient(), prompts)
    raw_dir = tmp_path / "OUTPUTS" / "raw_responses" / "t"
    assert sorted(p.name for p in raw_dir.glob("response_*_raw.txt")) == [
        "response_1_t_m_raw.txt", "response_3_t_m_raw.txt"]

    # rodada 2 (resume): os 2 ok vêm do disco (0 chamadas) e o falhado É re-tentado
    recovered = _SyncFakeClient()
    analyses = _process_articles_for_client_sync(cfg, recovered, prompts)
    assert recovered.calls == 1
    assert len(analyses) == 2
    ids = {a.id for a in analyses}
    assert ids == {"10.1000/a", "10.1000/c"}


def test_clean_and_parse_json_handles_articles_wrapper():
    """Payload canônico {"articles": [...]} não pode crashar o merge cego dict|list."""
    from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import (
        clean_and_parse_json as sync_parse)
    from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOneAsync import (
        clean_and_parse_json as async_parse)

    payload = json.dumps({"articles": [{"id": "10.1", "is_relevant": {"answer": "yes"}}]})
    for parse in (sync_parse, async_parse):
        assert parse(payload)["articles"][0]["id"] == "10.1"


def test_legacy_api_key_env_indirection_resolved(monkeypatch, pi_yaml):
    """LLM_API_KEY_ENV_<G> (indireção) deve ser resolvida pelo builder legado —
    antes, o gate via config válida mas o builder não resolvia (sequestro pelo YAML)."""
    monkeypatch.delenv("LLM_CLIENTS_ABSTRACT", raising=False)
    monkeypatch.delenv("LLM_CLIENTS", raising=False)
    monkeypatch.setenv("LLM_MODEL_ABSTRACT", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_API_KEY_ENV_ABSTRACT", "MINHA_VAR")
    monkeypatch.setenv("MINHA_VAR", "AIza-indireta")
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    cfgs = load_llm_client_configs("ABSTRACT")
    assert len(cfgs) == 1 and cfgs[0].provider == "openai"  # LLM_API_TYPE default
    assert cfgs[0].model_name == "gemini-2.5-flash"
    assert cfgs[0].api_key == "AIza-indireta"


def test_duplicate_api_roster_id_deduped(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    monkeypatch.delenv("PI_FAST_CONFIG_PATH", raising=False)
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "api-a,api-a")
    monkeypatch.setenv("LLM_API_A_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_A_MODEL", "gpt-x")
    monkeypatch.setenv("LLM_API_A_API_KEY", "sk")
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    cfgs = load_llm_client_configs("ABSTRACT")
    assert [c.id for c in cfgs] == ["api-a"]  # sem voto/custo duplicado


def test_yaml_defaults_list_tolerated(monkeypatch, tmp_path):
    """defaults como lista (AttributeError antes) degrada com aviso; API segue."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("defaults: [thinking]\nclients: []\n", encoding="utf-8")
    monkeypatch.setenv("PI_FAST_CONFIG_PATH", str(bad))
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-x")
    monkeypatch.setenv("LLM_OPENAI_X_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_X_MODEL", "gpt-x")
    monkeypatch.setenv("LLM_OPENAI_X_API_KEY", "sk-x")
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
    assert [c.id for c in load_llm_client_configs("ABSTRACT")] == ["openai-x"]
