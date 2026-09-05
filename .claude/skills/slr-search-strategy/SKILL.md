---
name: slr-search-strategy
description: >
  Guides a human to author the search strategy of a systematic review in
  config/search_config.yaml for Aneta — which databases to query, the generic search
  string (Aneta's boolean DSL), and the DuckDB scope filter. Use when defining or revising
  the search query, choosing databases, or tuning the scope filter. The skill interviews,
  proposes a draft, validates it, and the human reviews and approves — the human owns the
  search strategy.
compatibility: >
  Requires python3 (PyYAML) for validation. Writes config/search_config.yaml only after the
  human approves.
metadata:
  version: "1.0"
  project: aneta-slr
---

# SLR Search Strategy

Authoring guide for `config/search_config.yaml`: the databases, the generic search string,
and the scope filter. The human owns the strategy (reproducibility); this skill interviews,
drafts, and validates.

## When To Use

- Defining the search for a new review, or revising the query/databases/scope filter.

## File structure (config/search_config.yaml)

1. **Database toggles** (booleans): `arxiv`, `science_direct`, `spring_nature`,
   `web_of_science`, `ieee`, `scopus` (`acm` is not API-supported). Enable the bases the
   protocol commits to.
2. **`search_string`**: the generic query in Aneta's DSL — **translated automatically to
   each database's native syntax**, restricted to title/abstract/keywords where supported.
   - Operators: `AND`, `OR`, `NOT` (case-insensitive); precedence `NOT > AND > OR`.
   - Parentheses set precedence: `("a" OR "b") AND "c"`.
   - `IN`: `"agents" IN ("LLM","GPT")` ≡ `"agents" AND ("LLM" OR "GPT")`.
   - Phrases in quotes: `"large language model"`; single terms may be unquoted.
   - Wildcard `%` (LIKE-style): `organi%` matches organization/organizational. Scopus/WoS/
     IEEE use `*` (min 3 chars before `%`); arXiv/ScienceDirect/Springer **do not support
     wildcards** (the `%` is stripped with a warning).
3. **`filter_string`**: a DuckDB SQL `WHERE` clause applied to the merged results
   (title/abstract/keywords) — the **scope filter** before deduplication. Keep it aligned
   with the inclusion criteria but broad enough not to drop relevant work prematurely.

## Method

1. Interview: research concepts → synonyms → boolean structure. Build the `search_string`
   from concept blocks joined by `AND`, each block an `OR` of synonyms.
2. Decide databases from the protocol's information sources.
3. Draft `search_string` and (optionally) tune `filter_string`. Explain how the DSL maps to
   each enabled base (wildcards, field restriction) so the human anticipates coverage.
4. Validate structure:
   ```bash
   PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
   "$PY" .agents/skills/slr-search-strategy/scripts/validate_search.py config/search_config.yaml
   ```
5. Present the draft + validation; the human edits and **approves**; then save.

> Theory of mind: a search that is too narrow silently loses studies (a SLR validity
> threat); too broad explodes screening cost. Aim for high recall, then let the LLM
> screening + scope filter trim precision.

## Quality checklist

- [ ] At least one database enabled; all enabled bases match the protocol.
- [ ] `search_string` parses (balanced parentheses/quotes; valid operators).
- [ ] Wildcards used only where supported (or accepted that they are stripped).
- [ ] `filter_string` is valid SQL over title/abstract/keywords (no typos in fields).
- [ ] For every enabled base, its API key exists in `config/.env` (`IEEE_API_KEY`,
      `ELSEVIER_API_KEY`, `SPRINGER_API_KEY`, `WEB_OF_SCIENCE_KEY`; arXiv needs none).
- [ ] Validator passes; human reviewed and approved before saving.

## Outputs

- `config/search_config.yaml` (human-approved).
