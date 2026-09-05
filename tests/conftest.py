"""Fixtures globais dos testes.

Por padrão, os testes NÃO enxergam o config/pi_fast.yaml do repositório
(feature pi-fast desligada) — um teste que queira clients pi aponta
PI_FAST_CONFIG_PATH para o próprio YAML de fixture (sobrescreve o autouse).
"""

import pytest


@pytest.fixture(autouse=True)
def _pi_fast_disabled_by_default(monkeypatch, tmp_path_factory):
    nonexistent = tmp_path_factory.mktemp("pi_fast") / "desligado.yaml"
    monkeypatch.setenv("PI_FAST_CONFIG_PATH", str(nonexistent))
    yield
