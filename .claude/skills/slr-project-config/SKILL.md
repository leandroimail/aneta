---
name: slr-project-config
description: >
  Guides a human to set the Aneta project configuration in .conf — the data paths, output
  file locations, PDF/markdown folders, screening rate limits, full-text text cap, and the
  delivery folder for a systematic review. Use when initializing a new review's .conf,
  relocating data, or tuning operational parameters (concurrency, FULLTEXT_MAX_CHARS,
  FINAL_RESULTS_FOLDER). The skill proposes a draft based on the standard defaults and the
  human reviews and approves.
compatibility: >
  Edits .conf only after the human approves. Pairs with the other slr-* authoring skills,
  whose output paths must match .conf.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Project Config (.conf)

Authoring guide for `.conf`: operational settings and the canonical output paths that the
rest of the pipeline reads via `os.getenv`. Most values are stable defaults; the human
confirms or adjusts a few.

## When To Use

- Initializing `.conf` for a new review, or changing data location / operational knobs.

## Key variables (defaults shown)

| Var | Default | Meaning |
|---|---|---|
| `PATH_DATA` | `.data` | root for all data/outputs (gitignored) |
| `BIB_FILE` | `OUTPUTS/select_bibs.bib` | enriched/selected corpus |
| `FOLDER_SAVE_PDF` | `PDFs` | downloaded PDFs (under `PATH_DATA`) |
| `MARKDOWN_OUTPUT_FOLDER` | `PDFs/markdowns` | docling output |
| `FILTER_LLM_CONFIG_PATH` | `config/filter_accept_results_llm.yaml` | abstract inclusion clause |
| `FILTER_LLM_CONFIG_FULLTEXT_PATH` | `config/filter_accept_results_llm_fulltext.yaml` | final clause |
| `FULLTEXT_MAX_CHARS` | `400000` | cap of text sent per paper (0 = no cap) |
| `FINAL_RESULTS_FOLDER` | `OUTPUTS/final_results` | delivery folder for `--export_final` |
| `PATH_JCR` / `PATH_SCIMAGO` | `ImpactFiles/*.csv` | journal-impact enrichment tables |

There are more `*_OUTPUT` path vars (relevant/unrelevant/final/decision spreadsheets). Keep
their **defaults** unless there is a reason to move them — several skills and the pipeline
report resolve these exact names, so a custom value must be consistent everywhere.

## Method

1. Confirm `PATH_DATA` (one review per checkout — keep `.data` unless archiving).
2. Propose the standard `.conf` (defaults above) as a draft; flag only the knobs worth
   tuning: `FULLTEXT_MAX_CHARS` (lower it if a model's context is small),
   `PDF_MAX_CONCURRENT`/`DOWNLOAD_MAX_CONCURRENT` (download speed), `FINAL_RESULTS_FOLDER`.
3. Present the draft; the human reviews and approves; then save `.conf`.

> Theory of mind: changing an output path here without updating the skills/report that read
> it silently breaks the funnel/export. Prefer defaults; if you must change one, change it
> everywhere it is referenced.

## Quality checklist

- [ ] `PATH_DATA` set; `.data` is gitignored.
- [ ] Filter-config paths point at the files authored by `slr-inclusion-criteria`.
- [ ] Any non-default output path is consistent across `.conf`, the skills, and the report.
- [ ] Human reviewed and approved before saving.

## Outputs

- `.conf` (human-approved).
