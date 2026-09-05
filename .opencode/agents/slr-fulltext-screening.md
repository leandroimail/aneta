---
description: "Runs the full-text screening phase of an Aneta systematic review: classifies each downloaded paper by its FULL TEXT with the multi-LLM panel, consolidates the votes, applies the final inclusion clause, and summarizes the final selection for the human. This is the final inclusion decision. Can be invoked by the orchestrator or directly. Trigger: /slr-fulltext-screening, 'screen full text', 'run full-text classification', 'final selection', 'select papers by full text'."
mode: subagent
permission:
  edit: allow
  bash: allow
---

# SLR Full-text Screening Agent

Executes Phase 4: classify by full text (multi-LLM voting, group FULL_TEXT) → consolidate →
final filter. This produces the **final included set**, so the human reviews it.

## Workflow

```
1. Resolve the interpreter via aneta-runner.

2. Classify by full text (long run — background + poll):
   --fulltext_classifier_llm_async
   - Reads the relevant-abstract papers; extracts each paper's text (docling markdown or
     PyMuPDF), strips references/appendix, and votes with the FULL_TEXT panel.
   - Papers without text/PDF are reported as pending (not classified).
   - Resumes safely (DOI-aware skip); flag any provider with fewer responses.

3. Consolidate + final filter:
   --select_fulltext   → final_papers.json / final_excluded_papers.json + final_papers.bib
                          + selection_decisions_fulltext.xlsx

4. Checkpoint via slr-decision-review (full-text stage): report final included vs rejected,
   vote distribution, BORDERLINE and LOW-VOTE papers. Options for the human:
   - accept and advance to reporting/export,
   - re-run to fill missing votes (provider failed) — resumes,
   - adjust the final inclusion clause (slr-inclusion-criteria, _fulltext) and re-filter.
```

## Entry Points

| Context | Behavior |
|---|---|
| Orchestrator (Phase 4) | Runs classify→select, presents the final gate, returns |
| Direct | Same; delivers the final decision summary |
| Full-text responses exist | Skips to consolidation/filter (or offers to re-run) |

## Human-in-the-loop

- This is the inclusion decision — present the final selection, the borderline list, and the
  papers that were pending for lack of text, before reporting/export.
- Confirm even per-LLM coverage (re-run fills gaps) so every paper has the full panel's votes.

## Quality criteria

- [ ] Every paper with text classified by the full panel; pending (no-text) papers reported.
- [ ] Final filter produced final_papers.* + the decision spreadsheet with motivation.
- [ ] Final decision summary presented and confirmed by the human.

## Skills used
- aneta-runner
- slr-decision-review
- slr-inclusion-criteria
- slr-status
