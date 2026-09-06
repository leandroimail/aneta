# Pi-fast — triagem via harness PI (CLI `pi` local)

Alternativa às chamadas de **API** para a triagem multi-LLM: os "votos" podem vir de
**clients que executam o CLI `pi` localmente** (o "pi-fast"), usando as assinaturas de
coding-plan (OpenAI Codex, OpenCode Go, Z.ai) em vez de crédito por token de API.

## Como funciona

- Cada client pi é um **subprocesso** `pi -p` (não-interativo) em modo enxuto:
  `--no-tools --no-session -ne -ns -np -nc` (sem extensions/skills/prompt-templates/
  themes/context-files) + `--provider` + `--model` + `--thinking`.
- O **prompt entra por stdin** (testado com 450K chars — sem limite de argv) e a
  resposta é o **stdout** do CLI (JSON da análise; cercas ```json são toleradas).
- O client implementa o mesmo contrato dos demais (`async_invoke(messages) -> str`
  cancelável via `asyncio.create_subprocess_exec` + `wait_for`), então **resume,
  rate-limit, semáforo e consolidação funcionam sem nenhuma mudança** — os raws vão
  para `.data/OUTPUTS/raw_responses[_fulltext]/<client>/` igual aos de API.
- Timeout por chamada: 200s default (mata o grupo de processos do CLI); o full-text
  corta o artigo em 240s — o kill interno sempre ganha a corrida.
- **PATH_DATA**: clients pi gravam/lê em `<PATH_DATA>/OUTPUTS/...` como qualquer
  outro client; a consolidação (`--process_responses*`) também honra `PATH_DATA`
  (o `base_dir` passado é o próprio diretório de dados) e resolve a legenda de
  research questions como best-effort (base_dir → `PROJECT_PATH` → cwd).
- Os raws são salvos **por artigo, imediatamente** (fix B1) — um timeout do pi no
  meio do lote não desalinha o resume dos demais papers.

## Configuração (`config/pi_fast.yaml`)

```yaml
defaults:
  thinking: off          # off|minimal|low|medium|high|xhigh|max
  timeout_seconds: 200   # por chamada (máx. 230)
  max_concurrent: 4      # subprocessos simultâneos por client (1..16)
  rate_limit: 30         # req/s — espaçamento mínimo
clients:
  - id: pi-luna                  # SEM underscore (vira nome de arquivo/pasta)
    groups: [ABSTRACT, FULL_TEXT]
    provider: openai-codex
    model: gpt-5.6-luna
  - id: pi-deepseek
    groups: [FULL_TEXT]
    provider: opencode-go
    model: deepseek-v4-flash
  - id: pi-glm
    groups: [ABSTRACT]
    provider: zai
    model: glm-5.2
```

- Provedores/modelos válidos: `pi --list-models`.
- **Sem segredos neste arquivo**: o pi usa a auth local de cada provider. Campos
  desconhecidos (ex.: `api_key`) são rejeitados ao carregar.
- Para ativar: cite os ids no grupo desejado (`config/.env`), puro ou misto com APIs:
  `LLM_CLIENTS_ABSTRACT=google-flash,pi-glm` — ou deixe o roster vazio e o grupo usará
  apenas os clients pi do YAML (com log avisando).

## Composição e seleção

| Roster (`LLM_CLIENTS_<G>`) | O que roda |
|---|---|
| só ids de API | painel de API (como sempre) |
| ids de API + ids pi | painel misto (votos de API e pi na mesma consolidação) |
| só ids pi | triagem 100% pi-fast |
| vazio | clients pi do YAML (se houver p/ o grupo); senão, fallback legado single-LLM |

Seleção de um único client continua pelo `--llm <id|name|model>` (ex.: `--llm pi-glm`).

## Validação

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
"$PY" .agents/skills/slr-llm-config/scripts/validate_llm_groups.py ABSTRACT FULL_TEXT
```

Clients pi aparecem como `provider=pi/<harness>` e o validador checa a presença do
binário `pi` (env `PI_BIN` para caminho custom).

## Limitações (v1)

- **Sem telemetria de tokens/custo** para clients pi (as chamadas de API também não
  medem hoje); o pipeline_report não reflete consumo de pi.
- Clients pi não rodam nos fluxos legados síncronos (`--abstract_classifier_llm`,
  `--abstract_classifier_llm_one_on_one`) — são filtrados com aviso; use
  `--abstract_classifier_llm_one_on_one_async` / `--fulltext_classifier_llm_async`.
- Modelos disponíveis dependem do catálogo do pi instalado (`pi --list-models`);
  na data deste doc o provider `zai` não expõe glm-5.3 — o default configurado é
  glm-5.2 (troque no YAML quando o catálogo atualizar).
