---
name: slr-bibliometry
description: >
  Guides the execution, parameterization, and analysis of bibliometrics in Aneta.
  Integrates OpenAlex citation and institutional metadata, journal impact metrics (JCR/SJR),
  and R Bibliometrix / Python visual analytics. Supports parameterization to run either
  posterior to abstract screening (post_abstract) or in the final phase (final).
compatibility: >
  Requires the Aneta pipeline with Python environment (resolved via aneta-runner).
  Uses OpenAlex API for citation metrics and optionally Rscript with bibliometrix.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Bibliometry (Aneta)

This skill guides the execution and interpretation of bibliometric analyses within an Aneta Systematic Literature Review.

---

## 1. When To Use

- To characterize the scientific landscape of the review (citation impact, leading authors, top institutions, international collaboration, Bradford's core journals, thematic evolution).
- To run bibliometrics **either after abstract screening** (exploring the candidate literature) **or in the final phase** (characterizing the definitive accepted corpus).

---

## 2. Parameterization in `config/general_config.yaml`

The execution timing and options are configured in `config/general_config.yaml`:

```yaml
######################## Bibliometry options ########################
enable_bibliometry: true
# Execution stage:
#   - "final": runs on papers selected after full-text screening (final_papers.bib)
#   - "post_abstract": runs on papers approved by abstract screening (relevant_abstract_papers.bib)
#   - "both": runs on both stages for comparative funnel analysis
bibliometry_stage: "final"

bibliometry_using_openalex: true
bibliometry_for_arxiv: false
bibliometry_generate_r_plots: true
bibliometry_generate_py_charts: true
```

---

## 3. How To Run

Always resolve the Python environment through `aneta-runner`:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
```

### Execution on Final Selected Papers (Default / Recommended)
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --bibliometry_async --stage final
```

### Execution Posterior to Abstract Screening
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --bibliometry_async --stage post_abstract
```

---

## 4. Generated Artifacts

| Artifact | Location | Purpose |
| :--- | :--- | :--- |
| `openalex_metadata.json` | `.data/OUTPUTS/` | Enriched OpenAlex records (citations, concepts, institutions, co-authors). |
| Bibliometrix R Plots | `.data/BIBLIOMETRY/` | Co-authorship networks, thematic maps, Bradford core sources, Lotka distribution. |
| Python Charts & Tables | `.data/OUTPUTS/BIBLIOMETRY/` | Publication trends by year, citation distributions, top authors and venues. |
| Export Package | `.data/OUTPUTS/final_results/bibliometry/` | Automatically copied into the final delivery bundle by `--export_final`. |

---

## 5. Interpreting Results for the Human Checkpoint

1. **Volume and Growth:** Report publication trajectory over time (2021–2026).
2. **Core Venues:** Surface top journals/conferences and their quartile distribution (Q1–Q4 via SJR/JCR).
3. **Citations & Impact:** Report most cited publications and average citations per year.
4. **Geographic Distribution:** Report leading countries and institutional affiliations.
