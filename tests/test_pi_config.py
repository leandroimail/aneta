"""Testes do loader de clients pi-fast (config/pi_fast.yaml)."""

import pytest
from src.GenerativeAI.pi_config import (
    PiClientSpec,
    load_pi_client_specs,
    PI_DEFAULT_THINKING,
    PI_DEFAULT_TIMEOUT_SECONDS,
    PI_DEFAULT_MAX_CONCURRENT,
)

VALID_YAML = """
defaults:
  thinking: off
  timeout_seconds: 200
  max_concurrent: 4
  rate_limit: 30
clients:
  - id: pi-luna
    groups: [ABSTRACT, FULL_TEXT]
    provider: openai-codex
    model: gpt-5.6-luna
  - id: pi-deepseek
    groups: [FULL_TEXT]
    provider: opencode-go
    model: deepseek-v4-flash
    thinking: low
    max_concurrent: 2
"""


@pytest.fixture()
def pi_config_path(tmp_path, monkeypatch):
    """Factory que grava um YAML temporário e aponta PI_FAST_CONFIG_PATH para ele."""

    def _write(content: str) -> str:
        cfg = tmp_path / "pi_fast.yaml"
        cfg.write_text(content, encoding="utf-8")
        monkeypatch.setenv("PI_FAST_CONFIG_PATH", str(cfg))
        return str(cfg)

    return _write


def test_load_valid_yaml_returns_specs(pi_config_path):
    pi_config_path(VALID_YAML)
    specs = load_pi_client_specs()
    assert [s.id for s in specs] == ["pi-luna", "pi-deepseek"]


def test_defaults_applied_when_absent(pi_config_path):
    pi_config_path(VALID_YAML)
    specs = {s.id: s for s in load_pi_client_specs()}
    assert specs["pi-luna"].thinking == "off"
    assert specs["pi-luna"].timeout_seconds == 200
    assert specs["pi-luna"].max_concurrent == 4
    assert specs["pi-luna"].rate_limit == 30


def test_per_client_overrides_defaults(pi_config_path):
    pi_config_path(VALID_YAML)
    specs = {s.id: s for s in load_pi_client_specs()}
    assert specs["pi-deepseek"].thinking == "low"
    assert specs["pi-deepseek"].max_concurrent == 2


def test_group_filter(pi_config_path):
    pi_config_path(VALID_YAML)
    abstract = [s.id for s in load_pi_client_specs(group="ABSTRACT")]
    fulltext = [s.id for s in load_pi_client_specs(group="FULL_TEXT")]
    assert abstract == ["pi-luna"]
    assert fulltext == ["pi-luna", "pi-deepseek"]


def test_selected_matches_id_name_and_model(pi_config_path):
    pi_config_path(VALID_YAML)
    by_id = [s.id for s in load_pi_client_specs(selected="pi-luna")]
    by_model = [s.id for s in load_pi_client_specs(selected="GPT-5.6-LUNA")]
    assert by_id == ["pi-luna"]
    assert by_model == ["pi-luna"]


def test_enabled_false_excluded(pi_config_path):
    pi_config_path(VALID_YAML.replace("id: pi-deepseek", "id: pi-deepseek\n    enabled: false"))
    assert [s.id for s in load_pi_client_specs()] == ["pi-luna"]


def test_missing_model_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("    model: gpt-5.6-luna\n", ""))
    with pytest.raises(ValueError, match="model"):
        load_pi_client_specs()


def test_id_with_underscore_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("id: pi-luna", "id: pi_luna"))
    with pytest.raises(ValueError, match="underscore"):
        load_pi_client_specs()


def test_model_with_underscore_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("model: gpt-5.6-luna", "model: gpt_5_6_luna"))
    with pytest.raises(ValueError, match="underscore"):
        load_pi_client_specs()


def test_name_invalid_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("id: pi-luna", "id: pi-luna\n    name: nome_com_underline"))
    with pytest.raises(ValueError, match="name"):
        load_pi_client_specs()


def test_name_too_long_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("id: pi-luna", "id: pi-luna\n    name: " + "x" * 32))
    with pytest.raises(ValueError, match="name"):
        load_pi_client_specs()


def test_unknown_field_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("model: gpt-5.6-luna", "model: gpt-5.6-luna\n    api_key: vazou"))
    with pytest.raises(ValueError, match="api_key"):
        load_pi_client_specs()


def test_duplicate_id_rejected(pi_config_path):
    pi_config_path(VALID_YAML + VALID_YAML.split("clients:", 1)[1])
    with pytest.raises(ValueError, match="duplicad"):
        load_pi_client_specs()


def test_invalid_group_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("groups: [FULL_TEXT]", "groups: [NOT_A_GROUP]"))
    with pytest.raises(ValueError, match="grupo"):
        load_pi_client_specs()


@pytest.mark.parametrize("raw,clamped", [(0, 1), (-5, 1), (99, 16)])
def test_max_concurrent_clamped(pi_config_path, raw, clamped):
    pi_config_path(VALID_YAML.replace("  max_concurrent: 4\n  rate_limit: 30", f"  max_concurrent: {raw}\n  rate_limit: 30"))
    specs = {s.id: s for s in load_pi_client_specs()}
    assert specs["pi-luna"].max_concurrent == clamped


def test_missing_default_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.delenv("PI_FAST_CONFIG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)  # sem config/pi_fast.yaml no cwd
    assert load_pi_client_specs() == []


def test_constants_exist():
    assert PI_DEFAULT_THINKING == "off"
    assert PI_DEFAULT_TIMEOUT_SECONDS == 200
    assert PI_DEFAULT_MAX_CONCURRENT == 4


def test_enabled_string_false_excludes(pi_config_path):
    pi_config_path(VALID_YAML.replace("id: pi-deepseek", "id: pi-deepseek\n    enabled: \"false\""))
    assert [s.id for s in load_pi_client_specs()] == ["pi-luna"]


def test_rate_limit_nan_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("rate_limit: 30", "rate_limit: .nan"))
    with pytest.raises(ValueError, match="rate_limit"):
        load_pi_client_specs()


def test_negative_rate_limit_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("rate_limit: 30", "rate_limit: -5"))
    with pytest.raises(ValueError, match="rate_limit"):
        load_pi_client_specs()


def test_invalid_thinking_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("thinking: off", "thinking: TURBO"))
    with pytest.raises(ValueError, match="thinking"):
        load_pi_client_specs()


def test_groups_as_string_rejected(pi_config_path):
    pi_config_path(VALID_YAML.replace("groups: [ABSTRACT, FULL_TEXT]", "groups: ABSTRACT"))
    with pytest.raises(ValueError, match="lista"):
        load_pi_client_specs()
