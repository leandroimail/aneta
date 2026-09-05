#!/usr/bin/env python3
"""Validate Aneta LLM voting groups load correctly — WITHOUT revealing any key.

Usage:   python validate_llm_groups.py ABSTRACT FULL_TEXT
Run from the repo root (needs src/ on the path and config/.env loaded).
Exit:    0 every configured client resolved and each group has >=2 | 1 problems | 2 setup error.

Per client it prints: name, provider, model (never the key value). Critically, it diffs the
CONFIGURED client ids (LLM_CLIENTS_<GROUP>) against the RESOLVED configs: the Aneta loader
silently DROPS a client whose *_API_KEY_ENV is unset or whose model is missing, which would
shrink the voting panel without warning — so any dropped id is reported as MISSING + FAIL.
"""
import os
import shutil
import sys

sys.path.insert(0, os.getcwd())

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.abspath(".conf"))
    load_dotenv(os.path.abspath("config/.env"))
    from src.GenerativeAI.multi_llm_config import load_llm_client_configs
except Exception as e:  # noqa: BLE001
    print(f"ERROR: could not import Aneta LLM config layer ({e}). "
          f"Run from the repo root with the aneta-runner interpreter.", file=sys.stderr)
    sys.exit(2)


def _configured_ids(group: str):
    raw = os.getenv(f"LLM_CLIENTS_{group}") or os.getenv("LLM_CLIENTS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def main(groups) -> int:
    bad = 0
    for group in groups:
        configured = _configured_ids(group)
        try:
            cfgs = load_llm_client_configs(group)  # may print "[multi_llm] Ignorando cliente ..."
        except Exception as e:  # noqa: BLE001
            print(f"[{group}] ERROR loading: {e}")
            bad += 1
            continue

        resolved_ids = {c.id for c in cfgs}
        if not cfgs:
            print(f"[{group}] no clients resolved "
                  f"(LLM_CLIENTS_{group}={configured or 'empty'}; check *_API_KEY_ENV / *_MODEL).")
            bad += 1
            continue

        pi_cfgs = [c for c in cfgs if c.provider.lower() == "pi"]
        if configured:
            mode = "list"
        elif pi_cfgs:
            mode = "pi-fast (YAML)"
        else:
            mode = "legacy single-LLM"
        print(f"[{group}] {len(cfgs)} client(s) resolved ({mode}):")
        for c in cfgs:
            if c.provider.lower() == "pi":
                print(f"  - {c.id}: provider=pi/{c.harness_provider} model={c.model_name} key=local-auth")
            else:
                print(f"  - {c.id}: provider={c.provider} model={c.model_name} key=present")

        # Dropped = configured but not resolved (bad key var or missing model → loader returned None).
        dropped = [cid for cid in configured if cid not in resolved_ids]
        if dropped:
            print(f"  FAIL: {len(dropped)} configured client(s) DROPPED (unresolved key/model): "
                  f"{', '.join(dropped)} — fix *_API_KEY_ENV / *_MODEL or remove from LLM_CLIENTS_{group}.")
            bad += 1
        if len(cfgs) < 2:
            print(f"  (warn) only {len(cfgs)} client resolved — majority voting needs >=2 providers.")
        if pi_cfgs and shutil.which(os.getenv("PI_BIN", "pi")) is None:
            print("  FAIL: binário 'pi' não encontrado no PATH — clients pi-fast não conseguem rodar "
                  "(instale o pi ou ajuste PI_BIN).")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    args = sys.argv[1:] or ["ABSTRACT", "FULL_TEXT"]
    sys.exit(main(args))
