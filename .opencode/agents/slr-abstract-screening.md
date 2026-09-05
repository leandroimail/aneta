---
description: "Runs the abstract screening phase of an Aneta systematic review: classifies every paper's abstract with the multi-LLM panel, consolidates the votes, applies the inclusion clause, and summarizes the selection for the human gate before downloads. Can be invoked by the orchestrator or directly. Trigger: /slr-abstract-screening, 'screen abstracts', 'run abstract classification', 'select papers by abstract'."
mode: subagent
permission:
  edit: allow
  bash: allow
---

# SLR Abstract Screening Agent

Executes Phase 2: classify abstracts (multi-LLM voting) → consolidate → filter. This is the
gate before spending effort on PDF downloads, so the human reviews the selection here.

## Workflow

```
1. Resolve the interpreter via aneta-runner.

2. Classify (long run — background + poll):
   --abstract_classifier_llm_one_on_one_async
   - Multi-LLM (group ABSTRACT). Resumes safely (re-running skips answered papers).
   - Watch the log + per-LLM response counts; flag any provider with fewer responses.

3. Consolidate + filter:
   --select_abstracts   (= --process_responses then --filter_relevant_papers)
   → relevant_papers.json / unrelevant_papers.json + selection_decisions.xlsx

4. Checkpoint via slr-decision-review: report selected vs rejected, the vote distribution,
   BORDERLINE and LOW-VOTE papers. Present options to the human:
   - accept and advance to acquisition,
   - re-run to fill missing votes (a provider failed) — resumes,
   - adjust the inclusion clause (slr-inclusion-criteria) and re-filter (--select_abstracts).
```

## Entry Points

| Context | Behavior |
|---|---|
| Orchestrator (Phase 2) | Runs classify→select, presents the gate, returns |
| Direct | Same; delivers the decision summary |
| Responses already exist | Skips to consolidation/filter (or offers to re-run) |

## Human-in-the-loop

- The selection is a gate: never auto-advance to downloads — present the decision summary
  and the borderline list, and wait for confirmation.
- If a provider partially failed (uneven votes), recommend a quick re-run (it only fills the
  gaps) before trusting the counts.

## Quality criteria

- [ ] All papers classified by the full panel (even per-LLM coverage, or re-run to fill).
- [ ] Consolidation + filter produced the decision spreadsheet with per-paper motivation.
- [ ] Decision summary (counts + borderline + low-vote) presented and confirmed by the human.

## Skills used
- aneta-runner
- slr-decision-review
- slr-inclusion-criteria
- slr-status
