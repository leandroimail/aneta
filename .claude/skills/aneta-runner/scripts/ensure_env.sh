#!/usr/bin/env bash
# ensure_env.sh — resolve a working Python interpreter for Aneta and print its path.
#
# Usage:   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
# Output:  the interpreter path on stdout (only). Diagnostics go to stderr.
# Env:     ANETA_VENV overrides the venv location (default: ~/.cache/aneta-run-venv).
# Exit:    0 ok | 2 dependency install failed | 3 still missing key deps after bootstrap.
set -euo pipefail

REPO="${1:-$PWD}"
VENV="${ANETA_VENV:-$HOME/.cache/aneta-run-venv}"
PYBIN="$VENV/bin/python"

# Key modules that must import for the core pipeline (screening/consolidation/filter).
# NB: import importlib.util explicitly — "import importlib" alone does NOT bind the .util
# submodule on a clean interpreter, which would make find_spec raise AttributeError.
CORE_CHECK='import importlib.util,sys
mods=("openai","pydantic","dotenv","yaml","bibtexparser","openpyxl","fitz","lancedb","duckdb","pandas","requests")
missing=[m for m in mods if importlib.util.find_spec(m) is None]
sys.exit(1 if missing else 0)'

import_ok() { "$1" -c "$CORE_CHECK" >/dev/null 2>&1; }

need_bootstrap=1
if [ -x "$PYBIN" ] && import_ok "$PYBIN"; then
  need_bootstrap=0
fi

if [ "$need_bootstrap" = "1" ]; then
  echo "aneta-runner: no working interpreter at $PYBIN — bootstrapping..." >&2
  if [ ! -x "$PYBIN" ]; then
    python3 -m venv "$VENV" >&2 || { echo "aneta-runner: ERROR could not create venv at $VENV (is python3 installed?)." >&2; exit 2; }
  fi
  "$PYBIN" -m pip install --quiet --upgrade pip >&2 || true
  if [ -f "$REPO/requirements.txt" ]; then
    "$PYBIN" -m pip install --quiet -r "$REPO/requirements.txt" >&2 \
      || echo "aneta-runner: WARN requirements.txt install had issues; continuing with explicit deps." >&2
  fi
  # Known core deps (LLM clients, parsing, excel, pdf text, data stack). Heavy/optional
  # stacks (docling, playwright, undetected_chromedriver) are installed on demand, not here.
  "$PYBIN" -m pip install --quiet \
      openai google-genai google-generativeai pydantic aiohttp python-dotenv pyyaml \
      bibtexparser chardet openpyxl markdownify scholarly json-repair pymupdf \
      "lancedb>=0.19.0,<0.21.0" duckdb "pandas>=2.2.3,<3.0.0" "numpy>=1.20.1,<2.0.0" requests \
      "wrapt>=1.16" "setuptools<81" >&2 \
    || { echo "aneta-runner: ERROR installing core dependencies (see pip output above)." >&2; exit 2; }
fi

if ! import_ok "$PYBIN"; then
  echo "aneta-runner: ERROR — $PYBIN still missing key deps after bootstrap (see CORE_CHECK in this script)." >&2
  exit 3
fi

echo "$PYBIN"
