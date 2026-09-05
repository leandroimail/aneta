---
name: aneta-runner
description: >
  Runs the Aneta systematic-review CLI (aneta.py) reliably by bootstrapping a working
  Python interpreter first. Use this whenever any pipeline step must be executed via
  aneta.py — search, enrichment, abstract/full-text screening, PDF download, PDF reading,
  pipeline report, or final export — or whenever "python aneta.py" fails with import
  errors or a broken virtualenv. Always resolve the interpreter through this skill before
  running aneta.py.
compatibility: >
  Requires python3 and bash. Needs network access the first time it bootstraps the
  virtualenv (pip install). Designed for the Aneta repo (aneta.py at the repo root).
metadata:
  version: "1.0"
  project: aneta-slr
---

# Aneta Runner

Single source of truth for **how to invoke `aneta.py`** in this repo. Every SLR agent
uses it so the broken-virtualenv workaround and the long-run pattern live in one place.

## Purpose

The repo ships `pyproject.toml` + `uv.lock`, so `uv sync` (Option B in
docs/como-fazer/executar.md) is a valid alternative. This skill stays the canonical path for
agents, though: it reuses a cached venv (`~/.cache/aneta-run-venv`) across sessions and works
even when `.venv` is absent or broken (e.g. corrupted by a OneDrive sync), which is the
failure mode it was written for.

## When To Use

- Before running **any** `aneta.py` command.
- When `python aneta.py ...` raises `ModuleNotFoundError` or venv errors.
- When an agent needs the funnel/report or to kick off a long screening/download run.

## When Not To Use

- For editing Aneta's Python source (just edit files directly).
- For authoring SLR config files (use the `slr-*` authoring skills).

## Resolve the interpreter (always do this first)

Run the bootstrap script — it prints the path of a working interpreter on stdout and
explains failures on stderr:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
echo "interpreter: $PY"
```

Strategy inside the script: try `~/.cache/aneta-run-venv/bin/python`; if missing or failing
an import-check, create the venv and install `requirements.txt` + the known extra deps,
then re-check. Override the location with `ANETA_VENV=/path` if needed. Exit codes:
`0` ok (path on stdout), `2` dependency install failed, `3` still missing key deps.

## Run a command

Always export the resolved `$PY` and set `PYTHONUNBUFFERED=1` (aneta.py is already
line-buffered, but this also covers child processes and any pre-flush output):

```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --selection
```

### Long runs (screening, download) — run in the background

Screening and download take minutes to ~1 hour. Run them detached with a timestamped log
so the session is not blocked, then poll the log / response folders for progress:

```bash
LOG="/tmp/aneta_$(date +%s).log"
PYTHONUNBUFFERED=1 "$PY" aneta.py --fulltext_classifier_llm_async > "$LOG" 2>&1 &
echo "log: $LOG"
```

Progress signals to grep in the log: `successfully processed`, `⚠ Error`, `⏱ Timeout`,
and the per-LLM counts in `.data/OUTPUTS/raw_responses*/<llm>/`. Screening **resumes
safely**: re-running the same classifier skips already-answered papers (DOI-aware).

## Command catalog (pipeline order)

| Phase | Command | Notes |
|---|---|---|
| Search | `--search` | reads `config/search_config.yaml` |
| Enrichment | `--enrich_async` | metadata via APIs |
| Metadata selection | `--selection` | → `select_bibs.bib` |
| Abstract screening | `--abstract_classifier_llm_one_on_one_async` | multi-LLM, long, background |
| Abstract select | `--select_abstracts` | consolidate + filter → relevant/unrelevant |
| Download PDFs | `--download_pdf_async` | concurrent; `--download_pdf_assisted` for HITL |
| Read PDFs | `--read_pdfs` | docling (heavy, optional dep) |
| Full-text screening | `--fulltext_classifier_llm_async` | multi-LLM, long, background |
| Full-text select | `--select_fulltext` | consolidate + final filter |
| Report | `--pipeline_report` | funnel md/csv/json |
| Export | `--export_final` | delivery folder with PDFs + bib + reports |

Select a subset of LLMs with `--llm <id_or_model>` (e.g. only one model for a cheap smoke test).

## Notes & gotchas

- `--read_pdfs` needs the heavy `docling` stack and assisted download needs
  `playwright`/`undetected_chromedriver` — not installed by the base bootstrap. If a run
  reports a missing optional dep, install it into the resolved venv: `"$PY" -m pip install docling`.
- Never echo API keys. Keys live in `config/.env` (gitignored) and are read by aneta via
  `os.getenv`; this skill never reads or prints them.
- Data outputs live under `.data/` (gitignored). Do not commit them.

## Quality checklist

- [ ] Resolved `$PY` via `ensure_env.sh` (did not assume `python`).
- [ ] Long runs detached with a log; polled progress instead of blocking.
- [ ] Reported errors/timeouts from the log to the user.
- [ ] Did not print secrets or commit `.data/`.
