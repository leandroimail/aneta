---
name: slr-protocol
description: >
  Guides a human to author the protocol of a systematic review for Aneta — the research
  questions and the inclusion/exclusion criteria in config/research_questions.yaml, plus a
  human-readable protocol.md. Use when starting a new systematic review, defining or
  revising research questions, acceptance/rejection criteria, or the review scope. The
  skill interviews, proposes a draft, validates it, and the human reviews and saves it —
  the human is always the author of the methodology.
compatibility: >
  Requires python3 (PyYAML) for the validator. Writes config/research_questions.yaml and
  protocol.md only after the human approves.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Protocol (research questions + criteria)

Authoring guide for the scientific core of the review. The protocol drives every LLM
screening decision downstream, so it must be **human-owned**: this skill interviews,
drafts, and validates, but the human reviews, edits, and saves the final files.

## When To Use

- Starting a new systematic review (no `config/research_questions.yaml` yet, or a snapshot
  of a previous review was just archived).
- Refining research questions or inclusion/exclusion criteria.

## Authoring contract (important)

The human is the author. The flow is **interview → propose draft → human reviews/edits →
human approves and saves**. Never silently overwrite `config/research_questions.yaml`;
present the draft and ask for explicit approval before writing.

## Inputs to collect (interview)

Ask, one topic at a time, and reflect answers back:

1. **Topic & objective** of the review (one paragraph).
2. **Principal research question** — the single main question (`principal_research_question`).
3. **Additional research questions** (`arq1`, `arq2`, …) — optional, each a distinct angle.
4. **Supporting questions** (`sq1`, …) — finer sub-questions the review should answer.
5. **Acceptance criteria** (`ac1`, …) — what makes a paper *in scope* (operational, checkable).
6. **Rejection criteria** (`rc1`, …) — explicit exclusions (operational, checkable).

> Theory of mind: criteria are read by an LLM per paper and turned into yes/no votes.
> Vague criteria → noisy votes. Push for **operational, decidable** statements
> (e.g. "excludes single-agent systems" rather than "not very relevant").

## Schema (config/research_questions.yaml)

```yaml
principal_research_question: >
  <one main question>
additional_research_questions:
  arq1: >
    <question>
supporting_questions:
  sq1: >
    <question>
rejection_criteria:
  rc1: >
    <explicit, decidable exclusion>
accepted_criteria:
  ac1: >
    <explicit, decidable inclusion>
```

Keys must follow `arq*` / `sq*` / `rc*` / `ac*`. The downstream prompt and the SQL filter
reference `principal_research_question` and the per-criterion yes/no counts, so keep keys
stable once screening has started.

## Method

1. Interview using the list above; restate the scope to confirm shared understanding.
2. Draft `config/research_questions.yaml` in the schema, plus a `protocol.md` (see below).
3. Validate the draft:
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   "$PY" .agents/skills/slr-protocol/scripts/validate_protocol.py config/research_questions.yaml
   ```
4. Present the draft + validation result. The human edits as desired and **approves**.
5. Only after approval, save the files (human-confirmed).

## protocol.md (human-readable protocol)

Alongside the YAML, draft a short `protocol.md` (PRISMA-P spirit): title, objective,
research questions, eligibility criteria (inclusion/exclusion), information sources
(databases), planned screening method (multi-LLM voting + thresholds — see
`slr-inclusion-criteria`), and date. This is the registered, citable methodology.

## Quality checklist

- [ ] `principal_research_question` is a single, answerable question.
- [ ] Every acceptance/rejection criterion is operational and decidable (LLM can vote yes/no).
- [ ] Keys follow `arq*`/`sq*`/`ac*`/`rc*`; no duplicates.
- [ ] Validator passes (`validate_protocol.py` exit 0).
- [ ] Human reviewed and explicitly approved before the files were saved.

## Outputs

- `config/research_questions.yaml` (human-approved)
- `protocol.md` (human-readable protocol)
