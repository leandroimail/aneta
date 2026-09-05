---
name: slr-reporting
description: >
  Runs the reporting and delivery phase of an Aneta systematic review: generates the
  consolidated pipeline funnel (PRISMA-style) and exports the final deliverable folder with
  the selected PDFs, the final BibTeX, and all reports. Can be invoked by the orchestrator or
  directly.
  Trigger: /slr-reporting, "generate the report", "export the results", "build the funnel",
  "package the deliverable", "PRISMA".
skills:
  - aneta-runner
  - slr-status
---

# SLR Reporting Agent

Executes Phase 5: the funnel report and the final delivery package.

## Workflow

```
1. Resolve the interpreter via aneta-runner.

2. Pipeline report (the SLR funnel):
   --pipeline_report   → pipeline_report.md + pipeline_funnel.csv + pipeline_metrics.json
   Present the funnel via slr-status (identification → abstract → download → full-text → final).

3. Export the deliverable (confirm with the human first):
   --export_final      → .data/OUTPUTS/final_results/ with:
                          final_papers.bib, final_papers.json, final_excluded_papers.json,
                          final_papers_report.md, the decision/score spreadsheets,
                          the pipeline report (md/csv/json), pdfs/ (selected PDFs), LEIA-ME.md
   --export_final is idempotent (it clears the folder first) and regenerates the report.

4. Report the delivery: how many selected, how many PDFs copied, and any selected papers
   without a local PDF (listed in LEIA-ME.md).
```

## Entry Points

| Context | Behavior |
|---|---|
| Orchestrator (Phase 5) | Generates report, confirms, exports, reports delivery |
| Direct | Same; delivers the folder path + summary |
| Re-run after changes | Safe — export is idempotent; re-exports the current selection |

## Human-in-the-loop

- Confirm before exporting (it rebuilds the delivery folder).
- Surface the gaps honestly: selected-without-PDF, papers pending for lack of text, and any
  uneven LLM coverage — these belong in the methods/limitations of the write-up.

## Notes

- The delivery folder has a **fixed artifact list** (the files above); a hand-written review
  summary is not picked up automatically — copy it into the folder manually after exporting.
- Everything under `.data/` (including the delivery folder) is run output — not versioned.

## Quality criteria

- [ ] Funnel report generated and presented.
- [ ] Delivery folder exported (after confirmation) with PDFs + BibTeX + reports.
- [ ] Gaps (missing PDFs / pending papers / uneven votes) reported for the write-up.
