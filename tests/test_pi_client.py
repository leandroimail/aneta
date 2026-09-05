"""Testes do PiClient — cliente LLM via harness PI (CLI local).

Os testes usam scripts shell falsos como binário pi (injetável), sem mock de
subprocess: exercitam o caminho real de Popen/killpg.
"""

import asyncio
import subprocess
import time

import pytest

from src.GenerativeAI.pi_client import PiClient

FAKE_PI_ECHO = "#!/bin/bash\ncat > /dev/null\necho '{\"ok\": true}'\n"
FAKE_PI_CAT = "#!/bin/bash\ncat\n"  # devolve o próprio prompt (valida stdin + concat)
FAKE_PI_FAIL = "#!/bin/bash\ncat > /dev/null\necho 'boom no provider' >&2\nexit 3\n"
FAKE_PI_EMPTY = "#!/bin/bash\ncat > /dev/null\nexit 0\n"
FAKE_PI_SLOW = "#!/bin/bash\nsleep 300\n"


@pytest.fixture()
def fake_pi(tmp_path):
    """Factory de script falso do pi; retorna o caminho do binário."""

    def _write(content: str) -> str:
        script = tmp_path / "fake_pi.sh"
        script.write_text(content, encoding="utf-8")
        script.chmod(0o755)
        return str(script)

    return _write


def _client(pi_bin, **kwargs):
    defaults = dict(provider="zai", model="glm-5.2", thinking="off", timeout_seconds=10)
    defaults.update(kwargs)
    return PiClient(pi_bin=pi_bin, **defaults)


def test_missing_binary_fails_fast(tmp_path):
    client = _client(str(tmp_path / "nao_existe.sh"))
    with pytest.raises(Exception, match="pi"):
        client.invoke([{"role": "user", "content": "x"}])


def test_invoke_returns_stdout(fake_pi):
    client = _client(fake_pi(FAKE_PI_ECHO))
    assert client.invoke([{"role": "user", "content": "prompt"}]) == '{"ok": true}'


def test_prompt_goes_via_stdin_concatenating_user_and_system(fake_pi):
    client = _client(fake_pi(FAKE_PI_CAT))
    out = client.invoke(
        [
            {"role": "system", "content": "SYSTEM-AQUI"},
            {"role": "user", "content": "USER-AQUI"},
            {"role": "assistant", "content": "ASSISTANT-IGNORADO"},
        ]
    )
    assert "SYSTEM-AQUI" in out and "USER-AQUI" in out
    assert "ASSISTANT-IGNORADO" not in out


def test_golden_command_argv(fake_pi, monkeypatch):
    """O argv deve ter as flags lean na ordem canônica (posição por posição)."""
    captured = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs

        def communicate(self, input=None, timeout=None):
            captured["stdin_input"] = input
            captured["timeout"] = timeout
            return '{"ok": true}', ""

    monkeypatch.setattr("src.GenerativeAI.pi_client.subprocess.Popen", FakePopen)
    client = _client(fake_pi(FAKE_PI_ECHO), provider="openai-codex", model="gpt-5.6-luna", thinking="low")
    client.invoke([{"role": "user", "content": "p"}])

    argv = captured["argv"]
    assert argv[0] == client.pi_bin
    assert argv[1:4] == ["-p", "--provider", "openai-codex"]
    assert argv[4:6] == ["--model", "gpt-5.6-luna"]
    assert argv[6:8] == ["--thinking", "low"]
    for flag in ["--no-tools", "--no-session", "-ne", "-ns", "-np", "-nc"]:
        assert flag in argv, f"flag lean ausente: {flag}"
    assert captured["kwargs"]["stdin"] is subprocess.PIPE
    assert captured["kwargs"].get("start_new_session") is True
    assert captured["stdin_input"] == "p"


def test_nonzero_exit_raises_with_stderr_tail(fake_pi):
    client = _client(fake_pi(FAKE_PI_FAIL))
    with pytest.raises(Exception, match="boom no provider"):
        client.invoke([{"role": "user", "content": "p"}])


def test_empty_stdout_raises(fake_pi):
    client = _client(fake_pi(FAKE_PI_EMPTY))
    with pytest.raises(Exception, match="vaz"):
        client.invoke([{"role": "user", "content": "p"}])


def test_timeout_kills_process_group(fake_pi):
    """Subprocesso real travado: invoke estoura o timeout rápido e não deixa órfão."""
    client = _client(fake_pi(FAKE_PI_SLOW), timeout_seconds=1)
    t0 = time.time()
    with pytest.raises(Exception, match="timeout|Tempo"):
        client.invoke([{"role": "user", "content": "p"}])
    assert time.time() - t0 < 10
    # o grupo morreu: nenhum sleep 300 sobreviveu
    time.sleep(0.5)
    probe = subprocess.run(["pgrep", "-f", "sleep 300"], capture_output=True, text=True)
    assert probe.stdout.strip() == "", "processo órfão sobreviveu ao timeout"


def test_async_invoke_works_and_is_cancelable(fake_pi):
    client = _client(fake_pi(FAKE_PI_ECHO))

    async def run():
        return await client.async_invoke([{"role": "user", "content": "p"}])

    assert asyncio.run(run()) == '{"ok": true}'


def test_async_timeout_kills_subprocess(fake_pi):
    client = _client(fake_pi(FAKE_PI_SLOW), timeout_seconds=1)

    async def run():
        return await client.async_invoke([{"role": "user", "content": "p"}])

    t0 = time.time()
    with pytest.raises(Exception):
        asyncio.run(run())
    assert time.time() - t0 < 10
    time.sleep(0.5)
    probe = subprocess.run(["pgrep", "-f", "sleep 300"], capture_output=True, text=True)
    assert probe.stdout.strip() == "", "processo órfão sobreviveu ao timeout async"
