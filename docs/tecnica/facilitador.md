# Facilitador agêntico (cross-IDE)

O repositório traz um **facilitador de IA** que conduz o pipeline do Aneta passo a passo,
**confirmando cada comando com você**. Ele é compatível com **Claude Code**, **OpenCode**
e **OpenAI Codex**, a partir de um conjunto único de agentes e skills.

Princípio central: o facilitador **nunca decide a metodologia** e **nunca roda um passo
sem o seu aval**. A metodologia é sua; os agentes apenas entrevistam, rascunham, validam,
executam e relatam.

---

## Como usar com agentes

Comece pelo **orquestrador** na IDE em uso:

- `/slr-orchestrator`, "start systematic review", "continue the review", `/status`.

Ele detecta a fase atual (reentrada/retomada), propõe o próximo passo, mostra o funil e
espera sua confirmação antes de rodar. Você pode ajustar, pular, refazer uma fase anterior
ou parar a qualquer momento.

Se você não quiser usar agentes, execute `aneta.py` diretamente com o padrão descrito em
[como executar](../como-fazer/executar.md). O resultado é o mesmo pipeline; o facilitador
apenas adiciona detecção de fase, checkpoints humanos e execução assistida dos comandos.

---

## Agentes (fases do pipeline)

| Agente | Fase | Comandos Aneta |
|---|---|---|
| `slr-orchestrator` | coordenação ponta a ponta | despacha os demais |
| `slr-setup` | Fase 0 — configuração | autora configs + `protocol.md` |
| `slr-search` | Fase 1 — busca | `--search` → `--enrich_async` → `--selection` |
| `slr-abstract-screening` | Fase 2 — triagem por abstract | `--abstract_classifier_llm_one_on_one_async` → `--select_abstracts` |
| `slr-acquisition` | Fase 3 — aquisição | `--download_pdf_async` / `--download_pdf_assisted` → `--read_pdfs` |
| `slr-fulltext-screening` | Fase 4 — triagem por texto completo | `--fulltext_classifier_llm_async` → `--select_fulltext` |
| `slr-reporting` | Fase 5 — relatório/entrega | `--pipeline_report` → `--export_final` |

Cada fase confirma com você antes de rodar e de novo antes de avançar. Os checkpoints
humanos (onde você decide) são: configs/`protocol.md` após o setup; escopo após a busca;
selecionados vs rejeitados após cada triagem (gate antes de gastar com downloads);
cobertura e Cloudflare após o download; funil + pasta de entrega ao final.

---

## Skills

**Autoria da metodologia** (entrevistam, rascunham e validam — você aprova e salva):

| Skill | Autora |
|---|---|
| `slr-protocol` | `research_questions.yaml` + `protocol.md` |
| `slr-search-strategy` | `search_config.yaml` (bases, `search_string`, `filter_string`) |
| `slr-inclusion-criteria` | as cláusulas SQL de inclusão (abstract e full-text) |
| `slr-llm-config` | os painéis `LLM_CLIENTS_*` em `config/.env` |
| `slr-project-config` | os parâmetros operacionais do `.conf` |

**Execução e revisão:**

| Skill | Para quê |
|---|---|
| `aneta-runner` | resolve um interpretador funcional e roda `aneta.py` (ver abaixo) |
| `slr-status` | detecta a fase e resume o funil a partir de `.data/` (não roda nada caro) |
| `slr-decision-review` | resume o resultado de uma triagem para o checkpoint humano (limítrofes, poucos votos) |
| `slr-pdf-acquisition` | playbook de download, incluindo o modo assistido (Cloudflare) |

> O `aneta-runner` é a fonte única de verdade de **como** invocar `aneta.py` (resolve o
> interpretador + padrão de execução em background). Ver
> [como-fazer/executar.md](../como-fazer/executar.md).

---

## Layout cross-IDE

A fonte de verdade das regras é o `AGENTS.md`. As skills canônicas vivem em
`.agents/skills/`; os arquivos de agente são adaptadores por IDE da mesma definição em
`.agents/agents/`.

```
AGENTS.md                this file — regras canônicas (fonte única)
.agents/skills/          skills CANÔNICAS (carregadas por OpenCode e Codex)
.agents/agents/          definições de agente (markdown neutro)
.claude/skills/          cópia das skills para o Claude Code (idêntica a .agents/skills/)
.claude/agents/          subagentes do Claude Code
.opencode/agents/        agentes do OpenCode (mode/permission)
.codex/agents/           agentes do OpenAI Codex (.toml)
```

As skills são carregadas de `.agents/skills/` (OpenCode/Codex) e `.claude/skills/`
(Claude Code) — as duas árvores são idênticas. Os arquivos de agente são adaptações por
IDE das mesmas definições em `.agents/agents/`.

---

## Iniciar uma revisão nova

Use a `slr-setup`: ela arquiva a revisão anterior em `.slr-archive/` e o guia a autorar
cada arquivo de configuração e o `protocol.md`. **Você** autora e aprova a metodologia; as
skills só entrevistam, rascunham e validam.
