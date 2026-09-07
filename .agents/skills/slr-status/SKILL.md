---
name: slr-status
description: >
  Detects which phase a systematic review is in and summarizes the SLR funnel from the
  Aneta data artifacts. Use when starting or resuming a review (mid-entry), before/after
  any pipeline step to report progress, or whenever the user asks "where are we", "status",
  "how many papers", or "show the funnel". Reads artifacts under .data/; never runs LLM calls.
compatibility: >
  Requires the Aneta repo with .data/OUTPUTS artifacts. Uses the aneta-runner skill to
  (re)generate the pipeline report when needed.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Status

Answers "where is this review and how big is each stage?" by inspecting Aneta's artifacts.
This is how the orchestrator does **mid-entry** (resume from the right phase) and how every
phase reports its before/after counts at a checkpoint.

## When To Use

- At the start of a session, to detect the current phase and offer to resume.
- After any pipeline step, to report the new funnel numbers.
- When the user asks for status / counts / the funnel.

## Method

### 1. Refresh and read the funnel

Regenerate the consolidated report, then read the machine-readable state:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
PYTHONUNBUFFERED=1 "$PY" aneta.py --pipeline_report >/dev/null 2>&1 || true
```

- Human-readable funnel: `.data/OUTPUTS/pipeline_report.md`
- Machine state: `.data/OUTPUTS/pipeline_metrics.json` (per-stage metrics)
- Funnel table: `.data/OUTPUTS/pipeline_funnel.csv`

If the report cannot be generated (no data yet), fall back to artifact existence (below).

### 2. Detect the current phase (mid-entry)

Map artifact existence to the furthest completed phase. Read paths from `.conf`
(`PATH_DATA`, `FOLDER_SAVE_PDF`, the `*_OUTPUT` vars); defaults shown:

| Artifact present | Phase reached |
|---|---|
| `config/research_questions.yaml` + `config/search_config.yaml` | Setup done (protocol authored) |
| `.data/OUTPUTS/select_bibs.bib` | Search + enrichment + metadata selection |
| `.data/OUTPUTS/raw_responses/<llm>/response_*` | Abstract classification (LLM) |
| `.data/OUTPUTS/processed_responses/relevant_papers.json` | Abstract filter done |
| `.data/PDFs/*.pdf` | PDF download |
| `.data/PDFs/markdowns/*.md` | PDF reading (docling) |
| `.data/OUTPUTS/raw_responses_fulltext/<llm>/response_*` | Full-text classification |
| `.data/OUTPUTS/processed_responses/final_papers.json` | Final filter done |
| `.data/OUTPUTS/openalex_metadata.json` ou `.data/BIBLIOMETRY/` | Bibliometria executada |
| `.data/OUTPUTS/final_results/` | Export done |

The **next** step is the first phase whose artifact is missing. Report the detected phase
and ask the human whether to continue from there or re-run an earlier phase.

### 3. Summarize for a checkpoint

Present a compact funnel (stage → count → % of top) plus, for screening stages, the vote
distribution (`total_responses`) and selection rate, so the human can decide at the gate.
Per-LLM coverage lives in `pipeline_metrics.json` under `classificacao_llm` /
`classificacao_fulltext` (`respostas_por_llm`) — flag any LLM with fewer responses (a
provider that partially failed → some papers got fewer votes).

## Quality checklist

- [ ] Reported the detected phase and the concrete "next step".
- [ ] Funnel numbers came from `pipeline_metrics.json` / `pipeline_report.md`, not guesses.
- [ ] Flagged uneven per-LLM coverage when present.
- [ ] Did not modify any artifact (read-only).

## Outputs

A short status: current phase, next step, the funnel, and (for screening) vote/selection
summary — ready for the orchestrator's checkpoint prompt.
