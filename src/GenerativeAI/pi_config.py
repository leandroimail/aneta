"""Loader dos clients pi-fast (harness PI via CLI local).

Configuração em ``config/pi_fast.yaml`` (caminho override: env ``PI_FAST_CONFIG_PATH``):

    defaults:
      thinking: off            # off|minimal|low|medium|high|xhigh|max
      timeout_seconds: 200     # por chamada (clamp <= 230; o full-text corta em 240)
      max_concurrent: 4        # subprocessos simultâneos por client (clamp 1..16)
      rate_limit: 30           # req/s (espaçamento mínimo entre chamadas)
    clients:
      - id: pi-luna                  # SEM underscore (regex da consolidação)
        groups: [ABSTRACT, FULL_TEXT]
        provider: openai-codex       # provider do pi (ver `pi --list-models`)
        model: gpt-5.6-luna          # SEM underscore

Nada de segredos aqui: o pi usa a auth local de cada provider (codex/opencode/zai).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional

import yaml

PI_DEFAULT_THINKING = "off"
PI_DEFAULT_TIMEOUT_SECONDS = 200
PI_DEFAULT_MAX_CONCURRENT = 4
PI_DEFAULT_RATE_LIMIT = 30
PI_MAX_TIMEOUT_SECONDS = 230  # abaixo do wait_for externo (240s) do full-text
PI_VALID_GROUPS = ("ABSTRACT", "FULL_TEXT")

# name vira nome de pasta de raw responses e de aba Excel (<=31 chars, sem []:*?/\)
_NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,31}$")

_ALLOWED_CLIENT_KEYS = {
    "id", "name", "groups", "provider", "model",
    "thinking", "timeout_seconds", "max_concurrent", "rate_limit",
    "overwrite", "enabled",
}
_ALLOWED_TOP_KEYS = {"defaults", "clients"}
_ALLOWED_DEFAULT_KEYS = {"thinking", "timeout_seconds", "max_concurrent", "rate_limit"}


@dataclass(frozen=True)
class PiClientSpec:
    """Um client pi-fast configurado no YAML."""

    id: str
    name: str
    groups: tuple
    provider: str
    model: str
    thinking: str = PI_DEFAULT_THINKING
    timeout_seconds: int = PI_DEFAULT_TIMEOUT_SECONDS
    max_concurrent: int = PI_DEFAULT_MAX_CONCURRENT
    rate_limit: float = PI_DEFAULT_RATE_LIMIT
    overwrite: bool = False


def config_path() -> str:
    """Caminho do YAML de clients pi (override: env PI_FAST_CONFIG_PATH)."""
    return os.getenv("PI_FAST_CONFIG_PATH", os.path.join("config", "pi_fast.yaml"))


def _as_int(value, what: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"pi_fast: {what} deve ser inteiro, recebido {value!r}") from error


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _parse_client(raw: dict, defaults: dict) -> PiClientSpec:
    unknown = set(raw) - _ALLOWED_CLIENT_KEYS
    if unknown:
        raise ValueError(
            f"pi_fast: campo(s) desconhecido(s) em client: {', '.join(sorted(unknown))}. "
            "O pi usa a auth local de cada provider — não aceita api_key."
        )

    client_id = str(raw.get("id", "")).strip()
    if not client_id:
        raise ValueError("pi_fast: client sem 'id'")
    if "_" in client_id:
        raise ValueError(
            f"pi_fast: id '{client_id}' tem underscore — use hífen "
            "(o id vira nome de arquivo/pasta na consolidação)"
        )

    name = str(raw.get("name") or client_id)
    if not _NAME_RE.match(name):
        raise ValueError(
            f"pi_fast: name '{name}' inválido — use 1..31 caracteres de [A-Za-z0-9-] "
            "(vira pasta de raw responses e aba de Excel)"
        )

    model = str(raw.get("model", "")).strip()
    if not model:
        raise ValueError(f"pi_fast: client '{client_id}' sem 'model' (verifique `pi --list-models`)")
    if "_" in model:
        raise ValueError(
            f"pi_fast: model '{model}' tem underscore — o nome entra no arquivo de raw "
            "response e quebra a consolidação"
        )

    provider = str(raw.get("provider", "")).strip()
    if not provider:
        raise ValueError(f"pi_fast: client '{client_id}' sem 'provider' (ex.: openai-codex, opencode-go, zai)")

    groups = raw.get("groups") or list(PI_VALID_GROUPS)
    invalid = [g for g in groups if g not in PI_VALID_GROUPS]
    if invalid:
        raise ValueError(
            f"pi_fast: grupo(s) inválido(s) {invalid} — use {list(PI_VALID_GROUPS)}"
        )

    thinking = str(raw.get("thinking") or defaults.get("thinking") or PI_DEFAULT_THINKING)
    timeout_seconds = _clamp(
        _as_int(
            raw.get("timeout_seconds", defaults.get("timeout_seconds", PI_DEFAULT_TIMEOUT_SECONDS)),
            "timeout_seconds",
        ),
        5,
        PI_MAX_TIMEOUT_SECONDS,
    )
    max_concurrent = _clamp(
        _as_int(
            raw.get("max_concurrent", defaults.get("max_concurrent", PI_DEFAULT_MAX_CONCURRENT)),
            "max_concurrent",
        ),
        1,
        16,
    )
    rate_limit = float(raw.get("rate_limit", defaults.get("rate_limit", PI_DEFAULT_RATE_LIMIT)))

    return PiClientSpec(
        id=client_id,
        name=name,
        groups=tuple(groups),
        provider=provider,
        model=model,
        thinking=thinking,
        timeout_seconds=timeout_seconds,
        max_concurrent=max_concurrent,
        rate_limit=rate_limit,
        overwrite=bool(raw.get("overwrite", False)),
    )


def load_pi_client_specs(
    group: Optional[str] = None, selected: Optional[object] = None
) -> List[PiClientSpec]:
    """Carrega os specs de clients pi, filtrando por grupo e por seleção (--llm).

    - Arquivo padrão ausente → lista vazia (feature desligada), silenciosamente.
    - ``PI_FAST_CONFIG_PATH`` apontando para arquivo inexistente → ValueError
      (intenção explícita de configurar e não encontrou).
    """
    path = config_path()
    override = bool(os.getenv("PI_FAST_CONFIG_PATH"))
    if not os.path.isfile(path):
        if override:
            raise ValueError(f"pi_fast: PI_FAST_CONFIG_PATH aponta para arquivo inexistente: {path}")
        return []

    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"pi_fast: {path} deve ser um mapping YAML")
    unknown_top = set(data) - _ALLOWED_TOP_KEYS
    if unknown_top:
        raise ValueError(
            f"pi_fast: chave(s) de topo desconhecida(s): {', '.join(sorted(unknown_top))}"
        )

    defaults = data.get("defaults") or {}
    unknown_defaults = set(defaults) - _ALLOWED_DEFAULT_KEYS
    if unknown_defaults:
        raise ValueError(
            f"pi_fast: chave(s) desconhecida(s) em defaults: {', '.join(sorted(unknown_defaults))}"
        )

    raw_clients = data.get("clients") or []
    if not isinstance(raw_clients, list):
        raise ValueError("pi_fast: 'clients' deve ser uma lista")

    specs: List[PiClientSpec] = []
    seen: set = set()
    for raw in raw_clients:
        spec = _parse_client(raw, defaults)
        if not bool(raw.get("enabled", True)):
            continue
        if spec.id in seen:
            raise ValueError(f"pi_fast: id de client duplicado: {spec.id}")
        seen.add(spec.id)
        if group is not None and group not in spec.groups:
            continue
        specs.append(spec)

    if selected is not None:
        tokens = [selected] if isinstance(selected, str) else list(selected)
        tokens = [str(tok).strip().lower() for tok in tokens if str(tok).strip()]
        if tokens:
            specs = [
                spec for spec in specs
                if any(tok in (spec.id.lower(), spec.name.lower(), spec.model.lower())
                       for tok in tokens)
            ]

    return specs
