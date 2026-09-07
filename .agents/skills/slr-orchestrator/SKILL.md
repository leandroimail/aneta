---
name: slr-orchestrator
description: >
  Master coordinator for running a systematic literature review with Aneta. Guides the
  full pipeline step by step in INTERACTIVE mode (confirms with the human before every
  command), detects the current phase for mid-entry/resume, dispatches the right phase
  agent, and reports the funnel at each gate.
  Trigger: /slr-orchestrator, "start systematic review", "run the SLR pipeline",
  "run Aneta", "continue the review", /status.
compatibility: >
  Works within Antigravity, Claude, Cursor, and other agentic environments. Uses aneta-runner
  and slr-status.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Orchestrator

Coordinates the Aneta systematic-review pipeline end to end. It is a **facilitator**: it
never decides the methodology and never runs a step without the human's go-ahead.

## Operating mode: INTERACTIVE (always)

There is **no auto mode**. Before each step the orchestrator:
1. States what it is about to run and why.
2. Shows the current funnel and status (via `slr-status`).
3. Waits for the human's explicit confirmation.
4. Runs the step via `aneta-runner` / `aneta.py`.
5. Reports the result, logs, and the next proposed step.

The human can adjust, skip, redo a previous phase, or stop at any point.

## Pipeline (phases → Aneta commands)

```
Phase 0    Setup            slr-setup              (authors configs + protocol.md)
Phase 1    Search           slr-search             --search → --enrich_async → --selection
Phase 2    Abstract screen  slr-abstract-screening --abstract_classifier_llm_one_on_one_async
                                                   → --process_responses → --filter_relevant_papers
Phase 2.5  Bibliometry      slr-bibliometry        (optional post-abstract: --bibliometry_async --stage post_abstract)
Phase 3    Acquisition      slr-acquisition        --download_pdf_async / --download_pdf_assisted
                                                   → --read_pdfs
Phase 4    Full-text screen slr-fulltext-screening --fulltext_classifier_llm_async
                                                   → --process_responses_fulltext → --filter_final_papers
Phase 5    Bibliometry      slr-bibliometry        (parameterized final: --bibliometry_async --stage final)
Phase 6    Reporting        slr-reporting          --pipeline_report → --export_final
```

Each phase confirms with the human before running and again before advancing.

## Mid-entry / resume

On start (or `/status`), inspect the furthest completed phase from the artifacts under `.data/`:

```
Detected phase: Setup ready.
Next proposed step: Phase 1 — Multi-database search (--search).
Continue from here, re-run an earlier phase, or stop?
```

Screening and download **resume safely** (re-running skips finished work by DOI), so resuming is
the default offer.

## Checkpoints (where the human decides)

| After | The human reviews | Why it matters |
|---|---|---|
| Setup | protocol.md + configs | methodology is human-owned |
| Search | N identified / enriched | scope sanity check |
| Abstract screening | selected vs rejected (decision sheet) | gate before spending on downloads |
| Bibliometry (Post-Abstract) | OpenAlex / Bibliometrix landscape | explore candidate literature before PDF acquisition |
| Download | coverage; resolve Cloudflare (HITL) | some sites need a human |
| Full-text screening | selected vs rejected (decision sheet) | final corpus selection gate |
| Bibliometry (Final) | definitive corpus analytics | characterize final accepted papers |
| Final Delivery | export bundle + PRISMA report | verify deliverables before publication |

## Principles

- Human-in-the-loop at every step; never auto-advance without confirmation.
- Methodology (configs) is authored and approved by the human, not the orchestrator.
- Never expose secrets; never commit `.data/`, `config/.env`, or `review_planning/`.
