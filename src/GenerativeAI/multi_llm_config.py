"""
Camada de configuração para rodar MÚLTIPLOS LLMs por grupo de filtragem.

Inspirado no design do projeto `autometa` (src/llm.py), adaptado aos "grupos" do Aneta
(ABSTRACT, FULL_TEXT, SYSTEMATIC_REVIEW). Esta camada é apenas de CONFIGURAÇÃO: ela não
instancia clientes de LLM (cada módulo de classificação mantém suas próprias classes de
cliente) — ela só transforma variáveis de ambiente em uma lista de ``LLMClientConfig``.

Formato preferido no ``config/.env`` (exemplo para o grupo ABSTRACT):

    # Vazio  => usa o LLM único legado (LLM_*_ABSTRACT) — comportamento atual.
    # Definido => roda TODOS os LLMs da lista, salvando resultado independente por cliente.
    LLM_CLIENTS_ABSTRACT=openai-nano,gemini-flash

    LLM_OPENAI_NANO_PROVIDER=openai            # openai | gemini | deepseek
    LLM_OPENAI_NANO_MODEL=gpt-4.1-nano
    LLM_OPENAI_NANO_API_KEY_ENV=LLM_API_KEY_ABSTRACT   # nome da var que guarda a chave
    # ou LLM_OPENAI_NANO_API_KEY=sk-...                # chave inline (alternativa)
    LLM_OPENAI_NANO_RATE_LIMIT=200             # req/s (fallback: rate-limit do grupo)
    LLM_OPENAI_NANO_OVERWRITE=false

Se ``LLM_CLIENTS_<GROUP>`` (e o genérico ``LLM_CLIENTS``) estiverem ausentes, esta função
retorna exatamente UM config derivado das variáveis legadas ``LLM_*_<GROUP>`` — preservando
100% do comportamento single-LLM atual.

Segurança: nenhuma chave é hardcoded aqui; tudo vem de ``os.getenv``.
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass(frozen=True)
class LLMClientConfig:
    """Configuração de um alvo de execução de LLM."""

    id: str
    name: str
    provider: str  # openai | gemini | deepseek
    model_name: str
    api_key: str
    base_url: Optional[str] = None
    rate_limit: Optional[float] = None
    overwrite: bool = False
    is_reasoner: bool = False


# Variáveis legadas de rate-limit por grupo (mantém compatibilidade com nomes atuais).
_GROUP_RATE_LIMIT_ENVS = {
    "ABSTRACT": ["LLM_SECOND_RATE_LIMITE_ABSTRACT", "LLM_RATE_LIMIT_ABSTRACT"],
    "FULL_TEXT": ["LLM_RATE_LIMIT_FULL_TEXT"],
    "SYSTEMATIC_REVIEW": ["LLM_RATE_LIMIT_SYSTEMATIC_REVIEW"],
}

# Modelos padrão por provedor (espelham os defaults das funções get_*_llm existentes).
_DEFAULT_MODELS = {
    "openai": "gpt-4.1-nano",
    "gemini": "gemini-2.0-flash-lite",
    "google": "gemini-2.0-flash-lite",
    "deepseek": "deepseek-chat",
}

# Base URLs padrão por provedor.
# - "google": endpoint OpenAI-compatível do Gemini (usado via cliente OpenAI).
_DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str) -> Optional[float]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_client_id(value: str) -> str:
    """Converte um id de cliente no sufixo usado nas variáveis de ambiente.

    Ex.: ``openai-nano`` -> ``OPENAI_NANO`` (prefixo final ``LLM_OPENAI_NANO``).
    """
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _group_rate_limit(group: str) -> Optional[float]:
    env_names = list(_GROUP_RATE_LIMIT_ENVS.get(group.upper(), [f"LLM_RATE_LIMIT_{group.upper()}"]))
    # Fallback global (compat com config estilo autometa)
    env_names.append("LLM_REQUESTS_PER_SECOND")
    for env_name in env_names:
        value = _env_float(env_name)
        if value is not None:
            return value
    return None


def _resolve_api_key(env_prefix: str) -> Optional[str]:
    """Resolve a chave: ``{PREFIX}_API_KEY`` inline ou ``{PREFIX}_API_KEY_ENV`` (indireção)."""
    api_key = os.getenv(f"{env_prefix}_API_KEY")
    if api_key:
        return api_key
    api_key_env = os.getenv(f"{env_prefix}_API_KEY_ENV")
    if api_key_env:
        return os.getenv(api_key_env)
    return None


def _load_client_config_from_env(client_id: str, group: str) -> Optional[LLMClientConfig]:
    env_prefix = f"LLM_{_normalize_client_id(client_id)}"

    if not _env_bool(f"{env_prefix}_ENABLED", True):
        return None

    provider = os.getenv(f"{env_prefix}_PROVIDER", client_id).strip().lower()
    model_name = (
        os.getenv(f"{env_prefix}_MODEL")
        or os.getenv(f"{env_prefix}_MODEL_NAME")
        or _DEFAULT_MODELS.get(provider)
    )
    api_key = _resolve_api_key(env_prefix)

    if not api_key:
        print(f"[multi_llm] Ignorando cliente '{client_id}': API key não encontrada.")
        return None
    if not model_name:
        print(f"[multi_llm] Ignorando cliente '{client_id}': modelo não configurado.")
        return None

    rate_limit = _env_float(f"{env_prefix}_RATE_LIMIT")
    if rate_limit is None:
        rate_limit = _group_rate_limit(group)

    base_url = os.getenv(f"{env_prefix}_BASE_URL") or _DEFAULT_BASE_URLS.get(provider)

    return LLMClientConfig(
        id=client_id,
        name=os.getenv(f"{env_prefix}_NAME", client_id),
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        rate_limit=rate_limit,
        overwrite=_env_bool(f"{env_prefix}_OVERWRITE", _env_bool(f"LLM_OVERWRITE_{group.upper()}", False)),
        is_reasoner=_env_bool(f"{env_prefix}_IS_REASONER", _env_bool(f"LLM_IS_REASONER_{group.upper()}", False)),
    )


def _legacy_single_config(group: str) -> List[LLMClientConfig]:
    """Constrói UM config a partir das variáveis legadas ``LLM_*_<GROUP>``.

    Mantém o comportamento single-LLM atual: ``name == LLM_API_TYPE_<GROUP>`` para que a
    pasta de saída continue sendo ``raw_responses/<llm_type>/`` (idêntico a hoje).
    """
    g = group.upper()
    llm_type = os.getenv(f"LLM_API_TYPE_{g}", "OpenAI")
    provider = llm_type.strip().lower()
    model_name = os.getenv(f"LLM_MODEL_{g}") or _DEFAULT_MODELS.get(provider)
    api_key = os.getenv(f"LLM_API_KEY_{g}")

    if not api_key or not model_name:
        return []

    base_url = os.getenv(f"LLM_API_URL_{g}") or ""
    base_url = base_url.strip() or _DEFAULT_BASE_URLS.get(provider)

    return [
        LLMClientConfig(
            id=llm_type,
            name=llm_type,
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            rate_limit=_group_rate_limit(g),
            overwrite=_env_bool(f"LLM_OVERWRITE_{g}", False),
            is_reasoner=_env_bool(f"LLM_IS_REASONER_{g}", False),
        )
    ]


def load_llm_client_configs(
    group: str = "ABSTRACT",
    selected: Optional[Union[str, List[str]]] = None,
) -> List[LLMClientConfig]:
    """Carrega a lista de LLMs configurados para um grupo.

    Lê ``LLM_CLIENTS_<GROUP>`` (ou o genérico ``LLM_CLIENTS``). Se ambos estiverem vazios,
    cai no fallback legado single-LLM (``LLM_*_<GROUP>``).

    Args:
        group: nome do grupo (ex.: "ABSTRACT", "FULL_TEXT", "SYSTEMATIC_REVIEW").
        selected: filtra um subconjunto (string CSV ou lista). Cada item casa com o
            ``id``, o ``name`` OU o ``model_name`` do cliente (case-insensitive), permitindo
            selecionar um único LLM pelo nome do modelo (ex.: "gpt-5.4-nano").

    Returns:
        Lista de ``LLMClientConfig`` (clientes sem chave/modelo são descartados).
    """
    g = group.upper()

    if isinstance(selected, str) and selected:
        selected_ids = {item.strip().lower() for item in selected.split(",") if item.strip()}
    elif isinstance(selected, list):
        selected_ids = {item.strip().lower() for item in selected if item.strip()}
    else:
        selected_ids = set()

    raw_list = os.getenv(f"LLM_CLIENTS_{g}") or os.getenv("LLM_CLIENTS", "")
    client_ids = [item.strip() for item in raw_list.split(",") if item.strip()]

    if not client_ids:
        configs = _legacy_single_config(g)
    else:
        configs = []
        for client_id in client_ids:
            config = _load_client_config_from_env(client_id, g)
            if config:
                configs.append(config)

    # Filtra por id, name OU model_name (permite selecionar 1 LLM pelo modelo)
    if selected_ids:
        configs = [
            c for c in configs
            if selected_ids & {c.id.lower(), c.name.lower(), c.model_name.lower()}
        ]
    return configs
