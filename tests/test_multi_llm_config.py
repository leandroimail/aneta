"""Testes da camada de configuração multi-LLM (multi_llm_config).

Tudo offline: apenas parsing de variáveis de ambiente, sem rede.
"""

import os

import pytest

from src.GenerativeAI.multi_llm_config import (
    LLMClientConfig,
    load_llm_client_configs,
)


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    """Isola cada teste removendo qualquer variável LLM_* herdada do ambiente."""
    for key in list(os.environ):
        if key.startswith("LLM_"):
            monkeypatch.delenv(key, raising=False)
    yield


# =============================================================================
# Multi-LLM (LLM_CLIENTS_<GROUP>)
# =============================================================================

def test_lista_com_dois_clientes(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")

    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")

    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_GEMINI_FLASH_API_KEY", "g-key")

    configs = load_llm_client_configs("ABSTRACT")

    assert [c.id for c in configs] == ["openai-nano", "gemini-flash"]
    assert configs[0].provider == "openai"
    assert configs[0].model_name == "gpt-4.1-nano"
    assert configs[0].api_key == "sk-openai"
    assert configs[1].provider == "gemini"
    assert configs[1].model_name == "gemini-2.5-flash"
    # name default = id (usado como pasta de saída por cliente)
    assert configs[0].name == "openai-nano"


def test_chave_via_api_key_env_indirecao(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY_ENV", "LLM_API_KEY_ABSTRACT")
    monkeypatch.setenv("LLM_API_KEY_ABSTRACT", "sk-indireto")

    configs = load_llm_client_configs("ABSTRACT")

    assert len(configs) == 1
    assert configs[0].api_key == "sk-indireto"


def test_cliente_sem_chave_e_descartado(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    # gemini-flash sem chave -> descartado
    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")

    configs = load_llm_client_configs("ABSTRACT")

    assert [c.id for c in configs] == ["openai-nano"]


def test_cliente_desabilitado_e_descartado(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_ENABLED", "false")

    assert load_llm_client_configs("ABSTRACT") == []


def test_selected_filtra_subconjunto(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_GEMINI_FLASH_API_KEY", "g-key")

    configs = load_llm_client_configs("ABSTRACT", selected="gemini-flash")

    assert [c.id for c in configs] == ["gemini-flash"]


def test_selected_por_nome_do_modelo(monkeypatch):
    # Selecionar pelo NOME DO MODELO (ex.: --llm gpt-5.4-nano) deve isolar 1 LLM.
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-5.4-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_GEMINI_FLASH_API_KEY", "g-key")

    configs = load_llm_client_configs("ABSTRACT", selected="gpt-5.4-nano")

    assert [c.id for c in configs] == ["openai-nano"]
    assert configs[0].model_name == "gpt-5.4-nano"


def test_selected_por_name_do_cliente(monkeypatch):
    # Selecionar pelo NAME do cliente também deve funcionar.
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")
    monkeypatch.setenv("LLM_OPENAI_NANO_NAME", "openai_small")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-5.4-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_GEMINI_FLASH_API_KEY", "g-key")

    configs = load_llm_client_configs("ABSTRACT", selected="openai_small")

    assert [c.name for c in configs] == ["openai_small"]


def test_selected_sem_correspondencia_retorna_vazio(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-5.4-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")

    assert load_llm_client_configs("ABSTRACT", selected="inexistente") == []


def test_rate_limit_por_cliente_sobrepoe_grupo(monkeypatch):
    monkeypatch.setenv("LLM_SECOND_RATE_LIMITE_ABSTRACT", "10")
    monkeypatch.setenv("LLM_CLIENTS_ABSTRACT", "openai-nano,gemini-flash")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_RATE_LIMIT", "200")
    monkeypatch.setenv("LLM_GEMINI_FLASH_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_GEMINI_FLASH_API_KEY", "g-key")

    configs = {c.id: c for c in load_llm_client_configs("ABSTRACT")}

    assert configs["openai-nano"].rate_limit == 200.0  # override do cliente
    assert configs["gemini-flash"].rate_limit == 10.0   # herda do grupo


def test_llm_clients_generico_como_fallback(monkeypatch):
    # Sem LLM_CLIENTS_ABSTRACT, usa LLM_CLIENTS genérico.
    monkeypatch.setenv("LLM_CLIENTS", "openai-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_NANO_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_OPENAI_NANO_API_KEY", "sk-openai")

    configs = load_llm_client_configs("ABSTRACT")

    assert [c.id for c in configs] == ["openai-nano"]


# =============================================================================
# Fallback legado (single-LLM) — compatibilidade
# =============================================================================

def test_fallback_legado_single_llm(monkeypatch):
    monkeypatch.setenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
    monkeypatch.setenv("LLM_MODEL_ABSTRACT", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_API_KEY_ABSTRACT", "sk-legacy")
    monkeypatch.setenv("LLM_SECOND_RATE_LIMITE_ABSTRACT", "200")

    configs = load_llm_client_configs("ABSTRACT")

    assert len(configs) == 1
    cfg = configs[0]
    # name == llm_type garante pasta raw_responses/OpenAI/ inalterada
    assert cfg.name == "OpenAI"
    assert cfg.provider == "openai"
    assert cfg.model_name == "gpt-4.1-nano"
    assert cfg.api_key == "sk-legacy"
    assert cfg.rate_limit == 200.0


def test_fallback_legado_gemini_preserva_type_na_pasta(monkeypatch):
    monkeypatch.setenv("LLM_API_TYPE_ABSTRACT", "Gemini")
    monkeypatch.setenv("LLM_MODEL_ABSTRACT", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_API_KEY_ABSTRACT", "g-legacy")

    configs = load_llm_client_configs("ABSTRACT")

    assert len(configs) == 1
    assert configs[0].name == "Gemini"
    assert configs[0].provider == "gemini"


def test_sem_nenhuma_config_retorna_vazio(monkeypatch):
    # Nenhuma variável -> lista vazia (sem chave legada).
    assert load_llm_client_configs("ABSTRACT") == []


def test_grupo_full_text_usa_rate_limit_proprio(monkeypatch):
    monkeypatch.setenv("LLM_CLIENTS_FULL_TEXT", "openai-mini")
    monkeypatch.setenv("LLM_OPENAI_MINI_PROVIDER", "openai")
    monkeypatch.setenv("LLM_OPENAI_MINI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_OPENAI_MINI_API_KEY", "sk-ft")
    monkeypatch.setenv("LLM_RATE_LIMIT_FULL_TEXT", "5")

    configs = load_llm_client_configs("FULL_TEXT")

    assert len(configs) == 1
    assert configs[0].rate_limit == 5.0


def test_config_e_imutavel(monkeypatch):
    monkeypatch.setenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
    monkeypatch.setenv("LLM_MODEL_ABSTRACT", "gpt-4.1-nano")
    monkeypatch.setenv("LLM_API_KEY_ABSTRACT", "sk-legacy")

    cfg = load_llm_client_configs("ABSTRACT")[0]
    assert isinstance(cfg, LLMClientConfig)
    with pytest.raises(Exception):
        cfg.model_name = "outro"  # frozen dataclass
