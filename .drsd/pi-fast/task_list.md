# TASK LIST - Pi-fast (clients LLM via harness PI)

## ✅ LEGEND

- 🔴 Not Started
- 🟡 In Progress
- 🟢 Completed
- ⏸️ Blocked
- ❌ Canceled

---

**Project**: ASRL - Automated Systematic Review Library
**Feature**: Triagem de papers via harness PI (CLI `pi`, modo enxuto "pi-fast") em alternativa às chamadas de API
**Creation Date**: 2026-09-05
**Overall Status**: 🟢 Completed

Plano aprovado (v2, pós-revisão adversarial). Decisões: pi-fast = CLI `pi` sem plugins (`-p --no-tools` sem extensions/skills/templates/themes/context-files, sessão efêmera); zai → glm-5.2; convivência mista por composição; concorrência 4/client (configurável).

---

## 📋 MAIN TASKS

### 1. 🟡 Setup

**Status**: In Progress

**Subtasks**:
- [x] T1: Registrar esta task list em `.drsd/pi-fast/task_list.md`
- [x] T2: Spike ao vivo do CLI `pi` — checklist objetivo:
  - (a) prompt por stdin (`pi -p` lendo stdin) vs `@arquivo` (full-text ~400K chars > argv)
  - (b) stdout parseável como JSON puro nos 3 providers
  - (c) `--thinking off` aceito inclusive por modelo zai não-thinking
  - (d) `git status --porcelain` limpo após chamadas ao vivo
  - (e) auth dos providers openai-codex / opencode-go / zai

**Acceptance Criteria**:
- Comando canônico do pi definido e registrado nas notas abaixo
- 5 itens do checklist com resultado explícito

### 2. 🟢 Testes primeiro (RED)

**Status**: Completed

**Subtasks**:
- [x] T3: Baseline pytest re-medido e registrado (134 funções; subset rápido ~87)
- [x] T4: Testes do loader `pi_config` (grupos, selected, enabled=false, model ausente, id com `_`, name fora de `^[A-Za-z0-9-]{1,31}$`, model com `_`, campo desconhecido, max_concurrent clamp 1..16, id duplicado, PI_FAST_CONFIG_PATH)
- [x] T5: Testes do `PiClient` (golden argv, passthrough stdout, rc≠0/stdout vazio → Exception com stderr, timeout real matando grupo, cleanup temp, stdin=DEVNULL)

**Acceptance Criteria**:
- Novos testes falham (RED) antes das implementações

### 3. 🟢 Core

**Status**: Completed

**Subtasks**:
- [x] T6: `src/GenerativeAI/pi_config.py` (loader + validações)
- [x] T7: `src/GenerativeAI/pi_client.py` — `PiClient(LLMClient)`; `async_invoke` próprio com `create_subprocess_exec` + `wait_for` (cancelável); timeout default 200s (clamp ≤230); `stdin=DEVNULL`; `start_new_session` + killpg; temp file com unlink em finally; preflight `shutil.which("pi")`; `pi_bin`/`PI_BIN` injetável
- [x] T8: `config/pi_fast.yaml` (pi-luna/gpt-5.6-luna, pi-deepseek/deepseek-v4-flash, pi-glm/glm-5.2; defaults thinking off, timeout 200, max_concurrent 4)

**Acceptance Criteria**:
- T4 e T5 verdes

### 4. 🟢 Integração no pipeline

**Status**: Completed

**Subtasks**:
- [x] T9: `multi_llm_config` — campos opcionais (`harness_provider`, `thinking`, `max_concurrent`); anexar clients pi em `load_llm_client_configs` (filtros group/selected; roster vazio + YAML → só pi com log alto); fixture `_clean_llm_env` desliga YAML nos testes
- [x] T10: despacho `provider=="pi"` → `PiClient` no módulo async; módulos legados sync FILTRAM clients pi com warning (não crasham)
- [x] T11: Correção B1 (abstract salva raw por artigo, indexado por sequence+1, imediato) + B2 (normalização de DOI no resume do full-text) + testes de regressão
- [x] T12: semáforos honram `max_concurrent` (clamp 1..16); warning quando `--llm` casa múltiplos clients
- [x] T13: validador da skill slr-llm-config estendido (lista clients pi do YAML; checa binário `pi`)

**Acceptance Criteria**:
- Entrypoints legados não crasham com YAML presente; resume funciona com falha no meio (regressão B1)

### 5. 🟢 Ponta a ponta

**Status**: Completed

**Subtasks**:
- [x] T14: teste de consolidação com raws falsos de clients pi (incl. response_id gap/zfill)
- [x] T15: smoke ao vivo — 1 chamada por provider via PiClient (gpt-5.6-luna, deepseek-v4-flash, glm-5.2)

**Acceptance Criteria**:
- Consolidação idêntica à de clients API; 5/5 chamadas ao vivo OK (2 pi do abstract + 3 do full-text)

### 6. 🟢 Polish

**Status**: Completed

**Subtasks**:
- [x] T16: `docs/tecnica/pi-fast.md` + seção na skill slr-llm-config + nota no exemplo_config_llm.md
- [x] T17: suíte baseline re-medida (antes/depois), `git status` limpo, revisão do diff

**Acceptance Criteria**:
- Baseline antes == depois (sem regressão); novos testes verdes; diff revisado

---

## 📝 NOTES

- Bug pré-existente B1 (save em lote desalinhado do sequence+1) e B2 (DOI sem normalização) serão corrigidos nesta feature — o regime de falhas de subprocesso do pi torna-os críticos.
- Telemetria de tokens/custo para pi fica para v2 (pipeline hoje não mede tokens nem das APIs).
- Revisão adversarial: 4 bloqueadores (resumo desalinhado; corrida de timeout com to_thread; quebra de 3 entrypoints/suíte; contrato rc/stderr) — todos incorporados como T9-T12/T6.
- Restrito a nomes/ids sem underscore: regex de consolidação `response_(\d+)_([^_]+)_([^_]+)_raw\.txt`.


## ✅ RESULTADOS DO SPIKE (T2, 2026-09-05)

- (a) **stdin venceu**: `cat prompt | pi -p ...` funciona (testado com 450K chars). `@arquivo` nem é necessário — SEM temp file no client (desvio documentado do plano: o plano previa temp+@arquivo, o stdin tornou desnecessário).
- (b) stdout é **JSON puro** nos 3 providers (json.loads direto passou).
- (c) `--thinking off` aceito, inclusive pelo zai/glm-5.2 (não-thinking).
- (d) `git status` limpo após chamadas no cwd do repo (pi não cria artefatos com --no-session).
- (e) auth OK nos 3 providers: openai-codex ✓, opencode-go ✓, zai ✓.
- **Comando canônico**: `pi -p --provider <P> --model <M> --thinking <T> --no-tools --no-session -ne -ns -np -nc` (prompt via stdin).
- Correção durante o T15: caminho async precisava de `stdin=PIPE` (não DEVNULL) para o prompt chegar — o smoke pegou o bug antes do merge (200s de silêncio → vazio).

## 🔗 REFERENCES

- Referência do padrão harness: `/Users/leandroimail/Documents/schema-generation` (branch dev/leandro) — generation/base.py (killpg), registry, targets.yaml
- CLI: `pi` v0.80.7 (`--provider`, `--model provider/id`, `-p`, `--no-tools`, `--thinking`, `--no-session`, `-ne -ns -np -nc`)

---

**Last Updated**: 2026-09-05
**Next Review**: ao concluir cada fase
