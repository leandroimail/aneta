---
name: slr-llm-config
description: >
  Guides a human to configure the LLM voting panels for an Aneta systematic review — the
  LLM_CLIENTS_<GROUP> blocks in config/.env for the ABSTRACT and FULL_TEXT screening groups
  (which models vote, their providers, rate limits, and which env var holds each API key).
  Use when choosing or changing the LLMs used for screening, adding/removing a model from a
  voting panel, or wiring API keys. Never reads, prints, or commits API key values — keys
  stay in config/.env (gitignored) and are referenced by env-var name only.
compatibility: >
  Requires python3 with the repo's deps (multi_llm_config) to validate that groups load.
  Edits config/.env only after the human approves; never echoes secrets.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR LLM Config (voting panels)

Authoring guide for the multi-LLM panels that vote during screening. Independent votes are
consolidated per DOI and turned into a decision by the inclusion clause
(see `slr-inclusion-criteria`).

## Security first

`config/.env` is **gitignored and holds API keys**. This skill:

- **Never** reads, prints, logs, or commits a key value.
- References keys only by **env-var name** via `LLM_{ID}_API_KEY_ENV` (e.g.
  `OPENAI_API_KEY`). The key value lives elsewhere in `config/.env`, set by the human.
- Confirms a key var is *present* (non-empty) without revealing it.

## Groups

| Group | Var | Used by |
|---|---|---|
| `ABSTRACT` | `LLM_CLIENTS_ABSTRACT` | abstract screening (cheaper models OK) |
| `FULL_TEXT` | `LLM_CLIENTS_FULL_TEXT` | full-text screening (large-context models) |

`LLM_CLIENTS_<GROUP>` is a comma-separated list of client ids; each id `X` is configured by
`LLM_X_*` vars (id normalized to upper-case, hyphens→underscores).

## Per-client variables

```env
LLM_CLIENTS_FULL_TEXT=deepseek_full,google_full,openai_full

LLM_DEEPSEEK_FULL_PROVIDER=deepseek          # openai | google | deepseek
LLM_DEEPSEEK_FULL_MODEL=deepseek-v4-pro
LLM_DEEPSEEK_FULL_API_KEY_ENV=DEEPSEEK_API_KEY   # name of the env var with the key
LLM_DEEPSEEK_FULL_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_FULL_USE_JSON_SCHEMA=false
LLM_DEEPSEEK_FULL_RATE_LIMIT=3
LLM_OVERWRITE_FULL_TEXT=false                # false = resume (skip already-answered)
```

Known-good model names (verified against the providers): DeepSeek **`deepseek-v4-pro`**
(larger) / `deepseek-v4-flash` (cheap); Google `gemini-3.1-flash-lite` (1M context, cheap);
OpenAI `gpt-5.4-nano` (cheap). Prefer 3 independent providers so a majority vote is
meaningful. For full text, pick large-context models and keep `RATE_LIMIT` modest
(prompts are big); `FULLTEXT_MAX_CHARS` in `.conf` bounds the text sent.

> Gotcha: `LLM_OVERWRITE_<GROUP>=true` disables resume — every run reprocesses all papers.
> Keep it `false` so interrupted screening resumes and fills only missing votes.

## Method

1. With the human, choose the panel per group (3 providers recommended) and the models.
2. Draft the `LLM_CLIENTS_<GROUP>` block(s). Reference each key by env-var name; do not
   paste keys. If a key var is missing, ask the human to add it to `config/.env` themselves.
3. Validate the groups load (no key values printed):
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   "$PY" .agents/skills/slr-llm-config/scripts/validate_llm_groups.py ABSTRACT FULL_TEXT
   ```
4. Present the draft block; the human edits `config/.env` and approves.

## Quality checklist

- [ ] Each group lists ≥2 (ideally 3) distinct providers.
- [ ] Every client has provider, model, and an `*_API_KEY_ENV` pointing to a present var.
- [ ] `LLM_OVERWRITE_<GROUP>=false` (resume enabled).
- [ ] Validator reports all clients resolved; **no key value was printed**.
- [ ] `config/.env` not staged for commit.

## Outputs

- Updated `config/.env` LLM blocks (human-approved; never committed).

## Clients pi-fast (harness PI, CLI local)

Além dos clients de API, os grupos podem incluir **clients pi**: cada chamada roda o
CLI `pi` local em modo enxuto (sem plugins/tools), usando a assinatura de coding-plan
do provider (openai-codex, opencode-go, zai) em vez de crédito de API.

- Configuração em **`config/pi_fast.yaml`** (providers/modelos/thinking/concorrência) —
  sem chaves; o pi usa a auth local de cada provider.
- Para ativar, cite os ids pi no roster do grupo (ex.:
  `LLM_CLIENTS_ABSTRACT=google-flash,pi-glm`) ou deixe o roster vazio (roda só o YAML).
- Detalhes: `docs/tecnica/pi-fast.md`.
