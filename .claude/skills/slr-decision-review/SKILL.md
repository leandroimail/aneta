---
name: slr-decision-review
description: >
  Summarizes the result of a screening stage for the human checkpoint — reads the
  consolidated multi-LLM votes and the decision spreadsheet, reports selected vs rejected,
  the vote distribution, and surfaces borderline and low-vote papers that deserve a human
  look. Use after abstract screening or full-text screening, before advancing, or whenever
  the user asks "what was selected", "show borderline papers", or "review the decisions".
  Read-only; it does not change any decision.
compatibility: >
  Requires python3 with the repo deps (reads consolidated JSON; optionally openpyxl for the
  xlsx). Run from the repo root.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Decision Review

Turns a screening stage's machine output into a human-readable gate summary so the human
can confirm, or pull specific papers, before the pipeline advances. Used by both the
abstract and full-text screening agents (same skill, different stage).

## When To Use

- After `--select_abstracts` or `--select_fulltext`, at the checkpoint.
- When the user wants to see what was selected/rejected or inspect borderline cases.

## Inputs (stage paths)

| Stage | Consolidated JSON | Decision spreadsheet |
|---|---|---|
| Abstract | `combined_responses_consolidated.json` | `selection_decisions.xlsx` |
| Full text | `combined_responses_fulltext_consolidated.json` | `selection_decisions_fulltext.xlsx` |

(All under `.data/OUTPUTS/processed_responses/`; resolve via `.conf` if customized.)

## Method

1. Summarize the consolidated votes:
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   "$PY" .agents/skills/slr-decision-review/scripts/summarize_decision.py \
       .data/OUTPUTS/processed_responses/combined_responses_fulltext_consolidated.json
   ```
   Reports: total papers, vote distribution (`total_responses`), `is_relevant_yes_percent`
   buckets, **borderline** papers (relevance near the threshold), and **low-vote** papers
   (fewer votes than the panel size → a provider partially failed).
2. Cross-check the decision spreadsheet (`selection_decisions*.xlsx`) for the per-paper
   `selecionado` + `motivo` — the auditable rationale derived from the inclusion clause.
3. Present to the human: counts, the borderline list (these are the judgement calls), and
   any low-vote papers. Offer options: accept as-is, re-run screening to fill missing votes
   (resumes), or adjust the inclusion clause (via `slr-inclusion-criteria`) and re-filter.

> Theory of mind: the LLM vote is evidence, not a verdict. The borderline band and low-vote
> flags are exactly where a human should look — surface them rather than hiding them behind
> a single count.

## Quality checklist

- [ ] Reported selected/rejected counts and the vote distribution.
- [ ] Listed borderline (near-threshold) and low-vote papers explicitly.
- [ ] Pointed to the decision spreadsheet for the per-paper motivation.
- [ ] Read-only: no artifact modified.

## Outputs

A gate summary: counts + funnel delta, borderline list, low-vote list, and recommended
options for the human.
