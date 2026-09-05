---
name: slr-pdf-acquisition
description: >
  Playbook for acquiring the PDFs of the papers selected by abstract screening in Aneta,
  including the human-in-the-loop path for sites protected by Cloudflare. Use when
  downloading PDFs for a systematic review, when many downloads fail or are blocked, when
  coverage is low, or when the user mentions Cloudflare, paywalls, assisted download, or
  missing PDFs. Explains the automatic cascade, the assisted (visible-browser) mode, and how
  to track and improve coverage.
compatibility: >
  Automatic download needs network. Assisted mode needs a real Chrome plus playwright /
  undetected_chromedriver (installed on demand into the aneta-runner venv). Reads keys (e.g.
  Elsevier) from config/.env via os.getenv — never printed.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR PDF Acquisition

How to get the selected papers' PDFs with the best coverage and minimal human effort. Used
by the acquisition agent; the human only steps in where a site demands it.

## When To Use

- After abstract screening, to download the PDFs of the selected papers.
- When downloads fail, coverage is low, or a publisher blocks automation (Cloudflare).

## The download cascade (`--download_pdf_async`)

One concurrent command tries, per paper, several strategies in order and stops at the first
success:

1. **Direct async fetch** (aiohttp) — open-access / arXiv / direct PDF links.
2. **Real Chrome over CDP** (headful) — passes Cloudflare automatically because a genuine
   browser has `navigator.webdriver = false` (headless and Playwright-launched headful do
   **not** pass). Uses a local temp profile + a free port.
3. **Elsevier Article Retrieval API** — for ScienceDirect, via `ELSEVIER_API_KEY` /
   institutional token (entitlement by IP). Keys come from `config/.env`, never printed.
4. **PyPaperBot** — last-resort metadata-based retrieval.

Run it in the background (it takes a while) and watch coverage:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
LOG="/tmp/dl_$(date +%s).log"
PYTHONUNBUFFERED=1 "$PY" aneta.py --download_pdf_async > "$LOG" 2>&1 &
```

Downloads **resume**: re-running only fetches the still-missing PDFs.

> Variant `--download_pdf_fast`: same cascade but skips PDF validation (faster,
> riskier). Prefer the default for a review; use the fast lane only to grab obvious
> open-access PDFs you will re-check later.

## Assisted mode (human-in-the-loop) — `--download_pdf_assisted`

For the papers a site still blocks, run assisted mode: a **visible** real Chrome opens each
remaining URL and **the human solves the Cloudflare / login**, then the page's PDF is
captured. It asks before starting and walks through the missing set. Use this for the tail
of stubborn publishers after the automatic cascade.

> Some sites open the PDF in an in-page viewer instead of downloading — assisted mode
> captures those too once the human passes the gate.

## Tracking coverage

Use `slr-status` / `--pipeline_report`: the download stage reports `com_pdf` / `sem_pdf` and
`sem_pdf_por_publisher` (missing grouped by publisher), so the human can decide whether the
remaining tail is worth assisted effort or institutional access (e.g. VPN).

> Theory of mind: 100% coverage is rarely free. Get the automatic cascade's coverage first,
> then spend human effort (assisted / VPN) only on the publishers that dominate the misses.
> Papers without a PDF simply don't enter full-text screening — report them, don't hide them.

## Environment note

Assisted/CDP needs a real Chrome and `playwright`/`undetected_chromedriver` (+ `setuptools<81`
on Python 3.12). If a run reports a missing dep, install it into the resolved venv:
`"$PY" -m pip install playwright undetected_chromedriver "setuptools<81" && "$PY" -m playwright install chromium`.

## Quality checklist

- [ ] Ran the automatic cascade first; reported coverage and the missing-by-publisher table.
- [ ] Used assisted mode only for the blocked tail, with the human present.
- [ ] Did not print API keys; ran long downloads in the background.
- [ ] Reported papers left without a PDF (they skip full-text screening).
