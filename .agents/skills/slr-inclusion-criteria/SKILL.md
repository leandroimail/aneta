---
name: slr-inclusion-criteria
description: >
  Guides a human to author the inclusion decision rule of a systematic review for Aneta —
  the SQL voting clause in config/filter_accept_results_llm.yaml (abstract) and
  config/filter_accept_results_llm_fulltext.yaml (full text). Use when defining or tuning
  the threshold that decides which papers are selected from the multi-LLM votes, or when the
  user asks about the selection rule, thresholds, or majority voting. The skill explains the
  available columns, proposes a draft clause, validates it, and the human approves.
compatibility: >
  Requires python3 (PyYAML). Writes the filter YAML files only after the human approves.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Inclusion Criteria (voting threshold)

Authoring guide for the **selection rule**: a single SQL `WHERE` clause over the
consolidated multi-LLM votes that decides inclusion — and, by the same clause, the
per-paper motivation shown in the decision spreadsheet.

## When To Use

- Setting or tuning the threshold that turns LLM votes into selected/rejected.
- Two stages, two files (same column model, independent thresholds):
  - `config/filter_accept_results_llm.yaml` — abstract screening.
  - `config/filter_accept_results_llm_fulltext.yaml` — full-text (final) screening.

## How it works

Each paper is voted independently by N LLMs; `consolidate_responses_by_doi` produces, per
question/criterion `<field>`, the columns:

- `<field>_yes_count` / `_no_count` / `_other_count` / `_total_count`
- `<field>_yes_percent` / `_no_percent` / `_other_percent`
- plus `total_responses`, `providers`, `models`, `id`, `doi`, `article_title`.

Fields include `is_relevant`, `principal_research_question`, and each `ac*`/`rc*`/`sq*`/
`arq*` criterion. The clause selects a paper when it evaluates true. **The same clause
generates the motivation**: each `column OP number` becomes `column=value (OP threshold
✓/✗)` in `selection_decisions*.xlsx` — so editing the clause updates the rationale, no
code change.

## File format

```yaml
filter: >
  ((is_relevant_yes_percent >= 65 AND total_responses >= 2)
   AND (principal_research_question_yes_percent >= 65
        AND principal_research_question_total_count >= 2))
```

Default (3 LLMs): **majority "yes" (≥65%) on relevance AND on the principal research
question, with at least 2 votes**. The `_total_count`/`total_responses` guards prevent a
single vote from deciding when a provider failed.

## Method

1. Decide the bar with the human: majority threshold (e.g. 65% vs simple majority vs
   unanimity), minimum votes, and whether to also require specific `ac*` criteria or to
   exclude on `rc*` (e.g. `AND rc3_yes_percent < 50`).
2. Draft the clause for each stage (full-text is usually stricter or equal).
3. Validate:
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   "$PY" .agents/skills/slr-inclusion-criteria/scripts/validate_filter.py config/filter_accept_results_llm.yaml
   ```
4. Present draft + validation; human approves; save both files.

> Theory of mind: a stricter clause raises precision but can drop borderline-relevant work;
> document the chosen threshold in `protocol.md`. The decision is auditable per paper, so
> prefer a defensible rule over a clever one.

## Quality checklist

- [ ] `filter` key present; clause has balanced parentheses.
- [ ] References only real consolidated columns (`<field>_yes_percent`, `total_responses`, …).
- [ ] Includes a minimum-votes guard (`total_responses >= 2` or a `_total_count`).
- [ ] Both stage files authored and consistent with `protocol.md`.
- [ ] Validator passes; human approved before saving.

## Outputs

- `config/filter_accept_results_llm.yaml` and `config/filter_accept_results_llm_fulltext.yaml`.
