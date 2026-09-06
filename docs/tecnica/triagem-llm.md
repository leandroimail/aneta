# Triagem multi-LLM e cláusula de inclusão

Esta é a decisão central do Aneta. Em vez de um único modelo decidir, **vários LLMs
classificam cada paper de forma independente**, os votos são **consolidados por DOI**, e a
inclusão é decidida por uma **cláusula SQL escrita por um humano** sobre esses votos.
Resultado: cada decisão é auditável e o motivo fica registrado por artigo.

O mesmo mecanismo roda duas vezes no pipeline:

- **por abstract** (etapa 4–5) — gate barato antes do download;
- **por texto completo** (etapa 8–9) — a decisão de inclusão final.

---

## 1. Cada LLM vota de forma independente

O painel é configurado em `config/.env` por grupo:

- `LLM_CLIENTS_ABSTRACT` — painel da triagem por abstract;
- `LLM_CLIENTS_FULL_TEXT` — painel da triagem por texto completo.

Cada *id* da lista expande para variáveis `LLM_<ID>_*`:

```env
LLM_CLIENTS_ABSTRACT=openai-nano,gemini-flash

LLM_OPENAI_NANO_PROVIDER=openai          # openai | gemini | deepseek
LLM_OPENAI_NANO_MODEL=gpt-4.1-nano
LLM_OPENAI_NANO_API_KEY_ENV=LLM_API_KEY_SIMPLE   # nome da var que guarda a chave
LLM_OPENAI_NANO_RATE_LIMIT=200           # req/s (opcional)

LLM_GEMINI_FLASH_PROVIDER=gemini
LLM_GEMINI_FLASH_MODEL=gemini-2.5-flash
LLM_GEMINI_FLASH_API_KEY_ENV=LLM_API_KEY_ABSTRACT
```

Variáveis por cliente (resumo — tabela completa em
[exemplo_config_llm.md](../../exemplo_config_llm.md)):

| Variável | Obrigatória | Descrição |
|---|---|---|
| `LLM_<ID>_PROVIDER` | sim | `openai`, `google`, `gemini` ou `deepseek` |
| `LLM_<ID>_MODEL` | sim | nome do modelo |
| `LLM_<ID>_API_KEY_ENV` *ou* `LLM_<ID>_API_KEY` | sim | nome da var com a chave (indireção) ou chave inline |
| `LLM_<ID>_RATE_LIMIT` | não | req/s (default: rate-limit do grupo) |
| `LLM_<ID>_OVERWRITE` | não | reprocessa respostas já salvas |
| `LLM_<ID>_NAME` | não | nome de exibição / pasta de saída |
| `LLM_<ID>_ENABLED` | não | `false` desabilita o cliente |

> Não há voto/consenso embutido no código de classificação. Cada LLM apenas grava sua
> resposta; o "voto" emerge na consolidação + filtro SQL.

Se os blocos `LLM_CLIENTS_*` estiverem vazios — e não houver clients pi no
`config/pi_fast.yaml` para o grupo — o Aneta usa **um** LLM (modo legado
`LLM_*_ABSTRACT`), 100% compatível.

### Onde cada LLM grava (respostas brutas)

| Modo | Caminho |
|---|---|
| one-on-one (sync/async) | `.data/OUTPUTS/raw_responses/<NAME>/response_<n>_<NAME>_<MODEL>_raw.txt` |
| batch | `.data/OUTPUTS/select_bibs_filtered_by_abstract_<NAME>_<MODEL>_raw.txt` |
| texto completo | `.data/OUTPUTS/raw_responses_fulltext/<NAME>/response_<n>_…_raw.txt` |

A triagem **retoma com segurança**: re-rodar pula papers já respondidos por aquele LLM.
No full-text o skip é ciente de DOI (compara o `id` salvo com o esperado); no abstract
o skip é por existência do arquivo — seguro porque os raws são gravados por artigo com
índice estável (sequence+1). Se um provedor falhar no meio, basta re-rodar para preencher
as lacunas.

Dois contratos que sustentam essa retomada (fixes de 2026-09-05):

- **Raw salvo por artigo, na hora** (abstract, fluxo async): cada resposta é gravada
  imediatamente como `response_<sequence+1>_..._raw.txt` dentro do worker — um erro no
  meio do lote não desalinha os índices dos demais (antes, o save em lote ao final
  comprimia a numeração e o resume podia reaproveitar a resposta do paper errado).
  O legado síncrono `--abstract_classifier_llm_one_on_one` ainda salva em lote; os
  clients pi só rodam no fluxo async.
- **`PATH_DATA` honrado de ponta a ponta**: classificação, consolidação
  (`--process_responses*`, que usa `<PATH_DATA>/OUTPUTS/...` como base) e filtro
  operam no mesmo diretório de dados; a legenda de research questions é resolvida
  como best-effort (base_dir → `PROJECT_PATH` → cwd, em `Config/` ou `config/`).

---

## 2. O contrato de resposta (prompt)

Os prompts (`src/GenerativeAI/abstract_base_prompts*.yaml`,
`config/fulltext_base_prompts.yaml`) injetam a metodologia
(`research_questions.yaml`) e exigem um JSON estruturado. A regra crítica: para
`research_questions`, `accepted_criteria`, `rejection_criteria` e `is_relevant`, a
resposta é **estritamente `yes` ou `no`** — nunca "maybe", percentuais, números. Em caso
de dúvida ou falta de informação, o modelo **deve** responder `no`. Só
`supporting_questions` admite classes / "not sure".

É esse formato binário que torna os votos somáveis e a regra de inclusão simples.

---

## 3. Consolidação por DOI

`--process_responses` (abstract) e `--process_responses_fulltext` (texto completo) leem
todas as subpastas de `raw_responses*/` (uma por LLM) e **mesclam as respostas do mesmo
paper**, registrando quantos LLMs disseram sim/não para cada pergunta/critério. O resultado
é o **consolidado** (`combined_responses_consolidated.json` / `…_fulltext_consolidated.json`).

> O alinhamento usa o **índice estável do artigo** (`response_<N>_…`): o mesmo `N` aponta o
> mesmo paper em todas as pastas de LLM, e o DOI/título vêm de `select_bibs.json`. Em
> `LLMUtilExcel.py`, `classify_answer` mapeia `yes`/`sim` → positivo e `no`/`não` →
> negativo antes de contar os votos.

Para **cada** pergunta/critério `<campo>` (ex.: `is_relevant`,
`principal_research_question`, `arq1`, `ac1`, `rc1`, …), a consolidação gera as colunas:

| Coluna | Significado |
|---|---|
| `<campo>_yes_count` / `<campo>_no_count` / `<campo>_other_count` | nº de LLMs que responderam sim / não / outro |
| `<campo>_total_count` | nº de LLMs que responderam a esse campo |
| `<campo>_yes_percent` / `<campo>_no_percent` / `<campo>_other_percent` | percentuais correspondentes |

Mais os campos por artigo: `total_responses` (nº de LLMs que avaliaram o paper),
`providers`, `models`, `id`, `doi`, `article_title`.

---

## 4. A cláusula de inclusão (SQL)

`--filter_relevant_papers` (abstract) e `--filter_final_papers` (texto completo) aplicam a
cláusula SQL `WHERE` configurada — sobre o consolidado — para decidir incluído/rejeitado.

- abstract: `config/filter_accept_results_llm.yaml`
- texto completo: `config/filter_accept_results_llm_fulltext.yaml`

Cada arquivo tem uma única chave `filter:`. Padrão atual (idêntico nos dois): **maioria
diz "sim" (≥ 65%) E pelo menos 2 LLMs responderam**, tanto para `is_relevant` quanto para
a pergunta principal:

```yaml
filter: >
  ((is_relevant_yes_percent >= 65
  AND total_responses >= 2)
  AND
  (
    principal_research_question_yes_percent >= 65
    AND principal_research_question_total_count >= 2
  ))
```

Você pode usar qualquer coluna da consolidação. Exemplos de ajuste:

- **Unanimidade**: `is_relevant_yes_percent >= 100`
- **Maioria absoluta de 3 LLMs**: `is_relevant_yes_count >= 2`
- **Endurecer o full-text**: subir o limiar ou exigir mais respostas que no abstract.

### Decisão auditável

A motivação **não é texto fixo no código**: ela é derivada da própria cláusula. Cada
comparação `coluna OP número` vira `coluna=valor (OP limiar ✓/✗)` na **planilha de
decisão** (`selection_decisions.xlsx` / `selection_decisions_fulltext.xlsx`) e no
relatório. Mudar o filtro atualiza automaticamente a motivação de cada artigo.

---

## 5. Saídas da triagem

| Etapa | Saídas |
|---|---|
| abstract | `relevant_papers.json`, `unrelevant_papers.json`, `relevant_abstract_papers.bib`, `selection_decisions.xlsx` |
| texto completo | `final_papers.json`, `final_excluded_papers.json`, `final_papers.bib`, `selection_decisions_fulltext.xlsx` |

O BibTeX dos aprovados no abstract (`relevant_abstract_papers.bib`) é a entrada do
download e da triagem por texto completo. O `final_papers.bib` é o resultado da revisão.

> **Revisão humana (checkpoint):** depois de cada triagem, revise a planilha de decisão e
> os casos limítrofes / com poucos votos antes de avançar. A skill `slr-decision-review`
> resume isso automaticamente. Ver [facilitador.md](facilitador.md).
