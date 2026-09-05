"""Cliente LLM via harness PI (CLI local `pi`) — o "pi-fast".

Contrato informal do pipeline (mesma interface dos clients OpenAI/Gemini/DeepSeek):
``invoke(messages) -> str`` (resposta crua; JSON no caso da triagem) e
``async_invoke(messages) -> str``. Aqui o ``async_invoke`` é implementado com
``asyncio.create_subprocess_exec`` + ``wait_for`` para ser de verdade cancelável —
o default da base (``asyncio.to_thread``) deixaria subprocesso órfão quando o
full-text corta o artigo em 240s.

Comando canônico (spike 2026-09-05, ver .drsd/pi-fast/task_list.md):

    pi -p --provider <P> --model <M> --thinking <T> \\
       --no-tools --no-session -ne -ns -np -nc

com o prompt entrando por **stdin** (testado com 450K chars — sem limite de argv).

Sem segredos: o pi usa a auth local de cada provider (codex/opencode-go/zai).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
from typing import Dict, List, Optional

PI_LEAN_FLAGS = ("-ne", "-ns", "-np", "-nc")


def _kill_group(pid: int) -> None:
    """Mata o grupo de processos inteiro (CLIs agênticas spawnam helpers)."""
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


class PiClient:
    """Chamadas LLM via CLI pi em modo enxuto ("pi-fast").

    Args:
        provider: provider do pi (ex.: openai-codex, opencode-go, zai).
        model: modelo no provider (ex.: gpt-5.6-luna). Sem underscore.
        thinking: nível de thinking do pi (off|minimal|low|medium|high|xhigh|max).
        timeout_seconds: timeout por chamada (default 200s — abaixo do corte
            externo de 240s do full-text para o kill interno ganhar a corrida).
        pi_bin: binário do pi (default: env ``PI_BIN`` ou ``"pi"``).
    """

    def __init__(
        self,
        provider: str,
        model: str,
        thinking: str = "off",
        timeout_seconds: int = 200,
        pi_bin: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.thinking = thinking
        self.timeout_seconds = max(5, min(int(timeout_seconds), 230))
        self.pi_bin = pi_bin or os.getenv("PI_BIN", "pi")
        self.name = name or f"pi-{provider}"

    # ------------------------------------------------------------------ #

    def ensure_available(self) -> None:
        """Fail-fast: binário do pi presente no PATH?"""
        if shutil.which(self.pi_bin) is None:
            raise Exception(
                f"pi: binário '{self.pi_bin}' não encontrado no PATH — "
                "instale o pi ou ajuste PI_BIN"
            )

    def _argv(self) -> List[str]:
        return [
            self.pi_bin,
            "-p",
            "--provider", self.provider,
            "--model", self.model,
            "--thinking", self.thinking,
            "--no-tools",
            "--no-session",
            *PI_LEAN_FLAGS,
        ]

    @staticmethod
    def _prompt_from_messages(messages: List[Dict[str, str]]) -> str:
        return "\n\n".join(
            msg["content"] for msg in messages if msg.get("role") in ("user", "system")
        )

    @staticmethod
    def _check_result(stdout: str, stderr: str, returncode: Optional[int], elapsed: float) -> str:
        if returncode not in (None, 0):
            tail = (stderr or "").strip()[-500:]
            raise Exception(f"pi saiu com código {returncode}: {tail or '(sem stderr)'}")
        if not (stdout or "").strip():
            raise Exception(f"pi retornou saída vazia (rc=0) após {elapsed:.1f}s")
        return stdout.strip()

    # ------------------------------------------------------------------ #

    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """Chamada síncrona (usada via to_thread por quem precisa)."""
        self.ensure_available()
        prompt = self._prompt_from_messages(messages)
        process = subprocess.Popen(
            self._argv(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input=prompt, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_group(process.pid)
            try:
                process.communicate(timeout=5)
            except (subprocess.TimeoutExpired, ValueError):
                process.kill()
            raise Exception(
                f"pi timeout após {self.timeout_seconds}s — grupo de processos morto"
            )
        except Exception:
            _kill_group(process.pid)
            raise
        return self._check_result(stdout, stderr, getattr(process, "returncode", None), self.timeout_seconds)

    # ------------------------------------------------------------------ #

    async def async_invoke(self, messages: List[Dict[str, str]]) -> str:
        """Chamada assíncrona CANCELÁVEL (create_subprocess_exec + wait_for)."""
        self.ensure_available()
        prompt = self._prompt_from_messages(messages)
        process = await asyncio.create_subprocess_exec(
            *self._argv(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        started = asyncio.get_event_loop().time()
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            _kill_group(process.pid)
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
            elapsed = asyncio.get_event_loop().time() - started
            raise Exception(
                f"pi timeout após {self.timeout_seconds}s — grupo de processos morto (async, {elapsed:.1f}s)"
            )
        except asyncio.CancelledError:
            _kill_group(process.pid)
            raise
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return self._check_result(stdout, stderr, process.returncode, self.timeout_seconds)
