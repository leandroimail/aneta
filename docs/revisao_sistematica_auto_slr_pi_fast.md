# Documentação Técnica e Metodológica da Revisão Sistemática

## Tema: Revisão Sistemática Automatizada com LLMs e IA Generativa (PI-FAST)

---

## 1. Contexto e Solicitação Original

Esta configuração foi gerada para atender à seguinte solicitação:

> **Solicitação do Usuário:**
> *"gostaria agora criar uma revisão sistemática, baseado especificamente no pi-fast,. Quero que você me ajude com os agentes e o workflow a criar as configurações necessárias para criar uma revisão sistemática com a seguinte tema:*
> *tema: 'revisão sistemática automatizada, um enfoque em automatizações com LLM e modelos de AI generativa'.*
> *Quero que você sempre traduzar para o inglês.*
> *Busque os melhores termos de pesquisa.*
> *Use as bases cientificas disponíveis aqui (remova ArXiv)*
> *Busque apenas nos últimos 5 anos.*
> *use os agentes e suas própiras inteligencias para crias os arquivos de configurações necessárias, queries (tanto string de busca como sql). Documente tudo em um documento .md para eu entender como foi feito, o que foi realizado, como foi realizado, incluindo minha solicitação aqui"*

---

## 2. Metodologia Científica e Protocolo (PRISMA-P)

Para assegurar validade científica e reprodutibilidade, todas as questões de pesquisa, termos e critérios de seleção foram formulados formalmente em **inglês** e registrados em [protocol.md](file:///Users/leandroimail/Documents/asrl/protocol.md) e [config/research_questions.yaml](file:///Users/leandroimail/Documents/asrl/config/research_questions.yaml).

### 2.1. Título Oficial em Inglês
> **"Automated Systematic Literature Reviews: A Focus on Automations with Large Language Models (LLMs) and Generative AI Models"**

### 2.2. Questões de Pesquisa (Research Questions)

* **Principal Research Question (PRQ):**
  > *How are Large Language Models (LLMs) and Generative AI models being applied to automate the Systematic Literature Review (SLR) process?*

* **Additional Research Questions (ARQs):**
  * **ARQ1:** *Which stages of the systematic literature review pipeline (e.g., search strategy formulation, primary study selection/screening, data extraction, quality assessment, and evidence synthesis) are automated using LLMs or Generative AI?*
  * **ARQ2:** *What LLM architectures, prompt engineering techniques, multi-agent frameworks, or generative workflows are employed to conduct review automation?*

* **Supporting Questions (SQs):**
  * **SQ1:** *What evaluation metrics and benchmark datasets are used to assess the accuracy, recall, precision, and reliability of LLM-automated screening and data extraction compared to human reviewers?*
  * **SQ2:** *What are the primary benefits, challenges, and limitations (e.g., hallucinations, non-determinism, computational cost, context window constraints, reproducibility) reported in automated reviews?*
  * **SQ3:** *What degree of automation is achieved across existing literature (e.g., fully autonomous end-to-end pipelines versus semi-automated human-in-the-loop workflows)?*

### 2.3. Critérios de Elegibilidade (Inclusão e Exclusão)

Os critérios foram desenhados para serem **operacionais e decidíveis** (avaliáveis como `yes` ou `no` de forma consistente por múltiplos modelos de LLM):

#### Critérios de Inclusão (Accepted Criteria - AC)
* **AC1:** *The study proposes, implements, or evaluates the automation or semi-automation of one or more stages of systematic literature reviews (or systematic mapping/evidence synthesis) using Large Language Models (LLMs) or Generative AI.*
* **AC2:** *The study provides technical details, architectures, workflows, prompt engineering strategies, or multi-agent approaches for automating SLR tasks (e.g., title/abstract screening, full-text screening, data extraction, synthesis).*
* **AC3:** *The study directly addresses the principal research question or at least one of the additional/supporting research questions of this systematic review.*

#### Critérios de Exclusão (Rejection Criteria - RC)
* **RC1 (Non-SLR or Ad-Hoc Search):** *Studies that do not focus on Systematic Literature Reviews (SLRs), Systematic Mapping Studies (SMS), or formal evidence synthesis methodologies (e.g., casual/ad-hoc literature searches, conversational search over arbitrary documents).*
* **RC2 (Classical Methods Only):** *Studies on review automation that rely exclusively on traditional NLP, classical machine learning (e.g., SVM, Naive Bayes), or active learning without using Large Language Models (LLMs) or Generative AI.*
* **RC3 (Application of SLR Without Automation Method):** *Systematic reviews that merely apply standard manual SLR methodology to survey AI/LLMs in a specific domain, without proposing, evaluating, or discussing the automation of the SLR process itself using LLMs.*
* **RC4 (Pure Editorial/Opinion):** *Short commentaries, position papers, or tutorials without a concrete tool, pipeline, architecture, or empirical experiment.*

---

## 3. Estratégia de Busca e Bases Científicas

### 3.1. Bases Científicas Selecionadas
Configurado em [config/search_config.yaml](file:///Users/leandroimail/Documents/asrl/config/search_config.yaml):
* **Bases Habilitadas (`true`):**
  1. `scopus` (Elsevier)
  2. `ieee` (IEEE Xplore)
  3. `web_of_science` (Clarivate)
  4. `science_direct` (Elsevier)
  5. `spring_nature` (Springer Nature)
* **Bases Desabilitadas (`false`):**
  * `arxiv: false` (Removido conforme instrução, garantindo foco em literatura científica formal).
  * `acm: false` (A ACM não disponibiliza API pública de busca REST; o Aneta suporta ACM apenas para enriquecimento).

### 3.2. String de Busca Genérica (DSL Booleana do Aneta)
Para maximizar o recall sem ultrapassar limites rígidos de APIs parceiras (ex.: teto de 250 caracteres do ScienceDirect e limite de 40 termos do IEEE Xplore), elaboramos a query:

```text
("systematic literature review" OR "systematic review" OR "systematic mapping") 
AND ("automation" OR "automated" OR "autonomous") 
AND ("LLM" OR "large language model" OR "generative AI")
```

#### Tradução Automática por API (`query_language.py`):
1. **Scopus:** Envolvida em `TITLE-ABS-KEY(...)` com *loose phrases* (aspas duplas).
2. **IEEE Xplore:** Traduzida para `"Document Title"`, `"Abstract"` e `"Author Keywords"`. Com esta formulação concisa, a expansão permanece em 36 termos, **evitando o estouro do limite de 40 termos da IEEE**.
3. **ScienceDirect:** Traduzida para o parâmetro `qs` (188 caracteres), **respeitando o teto de 250 caracteres**.
4. **Springer Nature:** Mapeada para os campos de metadados permitidos no plano de API.
5. **Web of Science:** Traduzida para `TS=(...)` (Topic Search).

### 3.3. Filtro de Escopo em SQL / DuckDB (`filter_string`)
Após a consulta das APIs e o enriquecimento assíncrono de metadados (`--enrich_async`), o Aneta executa um filtro SQL de escopo sobre DuckDB antes da deduplicação:

```sql
(year >= 2021)
AND
(
    lower(title) LIKE '%systematic review%' OR lower(abstract) LIKE '%systematic review%' OR lower(keywords) LIKE '%systematic review%' OR
    lower(title) LIKE '%systematic literature review%' OR lower(abstract) LIKE '%systematic literature review%' OR lower(keywords) LIKE '%systematic literature review%' OR
    lower(title) LIKE '%systematic mapping%' OR lower(abstract) LIKE '%systematic mapping%' OR lower(keywords) LIKE '%systematic mapping%' OR
    lower(title) LIKE '%evidence synthesis%' OR lower(abstract) LIKE '%evidence synthesis%' OR lower(keywords) LIKE '%evidence synthesis%'
)
AND
(
    lower(title) LIKE '%automat%' OR lower(abstract) LIKE '%automat%' OR lower(keywords) LIKE '%automat%' OR
    lower(title) LIKE '%autonom%' OR lower(abstract) LIKE '%autonom%' OR lower(keywords) LIKE '%autonom%'
)
AND
(
    lower(title) LIKE '%llm%' OR lower(abstract) LIKE '%llm%' OR lower(keywords) LIKE '%llm%' OR
    lower(title) LIKE '%large language model%' OR lower(abstract) LIKE '%large language model%' OR lower(keywords) LIKE '%large language model%' OR
    lower(title) LIKE '%generative ai%' OR lower(abstract) LIKE '%generative ai%' OR lower(keywords) LIKE '%generative ai%' OR
    lower(title) LIKE '%gpt%' OR lower(abstract) LIKE '%gpt%' OR lower(keywords) LIKE '%gpt%'
)
```

> **Garantia dos 5 anos:** A condição `year >= 2021` restringe estritamente o corpus aos últimos 5 anos (2021 a 2026), capturando toda a era moderna de LLMs iniciada a partir do GPT-3/ChatGPT.

---

## 4. Triagem Multi-LLM baseada no PI-FAST

A triagem desta revisão é 100% conduzida através do harness **`pi-fast`**, utilizando o binário local `pi` instalado no sistema (`/opt/homebrew/bin/pi`).

### 4.1. Como funciona o `pi-fast`
* **Subprocessos Locais:** Cada cliente pi é executado como um subprocesso não-interativo (`pi -p --no-tools --no-session -ne -ns -np -nc`).
* **Zero Custo por Token de API:** As chamadas utilizam as contas/assinaturas locais já autenticadas no CLI (OpenAI Codex, OpenCode Go, Z.ai), dispensando cobrança de créditos de API.
* **Salvamento Imediato por Artigo:** Cada resposta bruta é gravada imediatamente em `.data/OUTPUTS/raw_responses/<client>/`, permitindo retomada exata (*resume*) sem reprocessar artigos já avaliados.
* **Tolerância a Falhas:** Timeout configurado por chamada com isolamento de processo.

### 4.2. Painel de Votação (Roster Triplo Independente)
Configurado em [config/pi_fast.yaml](file:///Users/leandroimail/Documents/asrl/config/pi_fast.yaml) e ativado em [config/.env](file:///Users/leandroimail/Documents/asrl/config/.env):

| ID do Cliente | Provedor Local | Modelo | Janela de Contexto | Grupos Habilitados |
|---|---|---|---|---|
| `pi-luna` | `openai-codex` | `gpt-5.6-luna` | 372.000 tokens | ABSTRACT, FULL_TEXT |
| `pi-deepseek` | `opencode-go` | `deepseek-v4-flash` | 1.000.000 tokens | ABSTRACT, FULL_TEXT |
| `pi-glm` | `zai` | `glm-5.2` | 1.000.000 tokens | ABSTRACT, FULL_TEXT |

### 4.3. Regras de Inclusão e Decisão SQL
Arquivos:
* [config/filter_accept_results_llm.yaml](file:///Users/leandroimail/Documents/asrl/config/filter_accept_results_llm.yaml) (Abstract)
* [config/filter_accept_results_llm_fulltext.yaml](file:///Users/leandroimail/Documents/asrl/config/filter_accept_results_llm_fulltext.yaml) (Full Text)

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

* **Semântica:** Um artigo só é selecionado se receber maioria de aprovação (≥65% de "sim") tanto em relevância geral quanto na questão principal, com a garantia de que pelo menos 2 LLMs responderam com sucesso (prevenindo que falha de rede ou timeout de um modelo aprove ou rejeite sozinho um artigo).
* **Transparência Auditável:** A motivação detalhada de cada artigo selecionado ou rejeitado é gravada na planilha `selection_decisions.xlsx` demonstrando o percentual de aprovação e o limiar comparado.

---

## 5. Mapeamento dos Arquivos de Configuração

| Arquivo | Finalidade |
|---|---|
| [protocol.md](file:///Users/leandroimail/Documents/asrl/protocol.md) | Protocolo acadêmico da revisão no padrão PRISMA-P em inglês. |
| [config/research_questions.yaml](file:///Users/leandroimail/Documents/asrl/config/research_questions.yaml) | Perguntas de pesquisa e critérios AC/RC injetados nos prompts multi-LLM. |
| [config/search_config.yaml](file:///Users/leandroimail/Documents/asrl/config/search_config.yaml) | Ativação das 5 bases científicas, DSL de busca e filtro SQL DuckDB (anos ≥ 2021). |
| [config/filter_accept_results_llm.yaml](file:///Users/leandroimail/Documents/asrl/config/filter_accept_results_llm.yaml) | Regra SQL de votação para a triagem por título e resumo (Abstract). |
| [config/filter_accept_results_llm_fulltext.yaml](file:///Users/leandroimail/Documents/asrl/config/filter_accept_results_llm_fulltext.yaml) | Regra SQL de votação para a triagem final por texto completo (Full Text). |
| [config/pi_fast.yaml](file:///Users/leandroimail/Documents/asrl/config/pi_fast.yaml) | Definição dos clientes locais do harness PI (`pi-luna`, `pi-deepseek`, `pi-glm`). |
| [config/.env](file:///Users/leandroimail/Documents/asrl/config/.env) | Ativação dos painéis de triagem (`LLM_CLIENTS_ABSTRACT` e `LLM_CLIENTS_FULL_TEXT`). |

---

## 6. Fluxo de Execução do Pipeline Passo a Passo

Para conduzir a revisão sistemática de ponta a ponta, execute a sequência abaixo no terminal.

### 6.1. Inicializar o Interpretador
```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
```

### 6.2. Validar Toda a Configuração
Antes de iniciar as chamadas de rede:
```bash
"$PY" .agents/skills/slr-protocol/scripts/validate_protocol.py config/research_questions.yaml
"$PY" .agents/skills/slr-search-strategy/scripts/validate_search.py config/search_config.yaml
"$PY" .agents/skills/slr-inclusion-criteria/scripts/validate_filter.py config/filter_accept_results_llm.yaml
"$PY" .agents/skills/slr-inclusion-criteria/scripts/validate_filter.py config/filter_accept_results_llm_fulltext.yaml
"$PY" .agents/skills/slr-llm-config/scripts/validate_llm_groups.py ABSTRACT FULL_TEXT
```

### 6.3. Etapa 1: Busca Científica Multi-Base
Consulta IEEE, Scopus, Web of Science, ScienceDirect e Springer Nature:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --search
```

### 6.4. Etapa 2: Enriquecimento Assíncrono de Metadados
Preenche DOIs, resumos e palavras-chave ausentes via OpenAlex/Crossref:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --enrich_async
```

### 6.5. Etapa 3: Seleção e Deduplicação (DuckDB)
Aplica o filtro de escopo temporal (`year >= 2021`) e textual, seguido da deduplicação:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --selection
```

### 6.6. Etapa 4: Triagem por Título e Resumo (Multi-LLM com PI-FAST)
Dispara a votação paralela dos 3 modelos via `pi-fast`:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --abstract_classifier_llm_one_on_one_async
```
Em seguida, consolida as respostas e aplica a cláusula SQL de decisão:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --process_responses
PYTHONUNBUFFERED=1 "$PY" aneta.py --filter_relevant_papers
```
*Gera: `.data/OUTPUTS/relevant_abstract_papers.bib` e `.data/OUTPUTS/processed_responses/selection_decisions.xlsx`.*

### 6.7. Etapa 5: Aquisição dos PDFs
Baixa os textos completos dos artigos selecionados no abstract:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --download_pdf_async
```

### 6.8. Etapa 6: Triagem por Texto Completo (Full Text com PI-FAST)
Avalia os artigos completos com PyMuPDF/Docling e o painel de contexto longo:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --fulltext_classifier_llm_async
```
Consolida os votos e aplica o filtro final:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --process_responses_fulltext
PYTHONUNBUFFERED=1 "$PY" aneta.py --filter_final_papers
```

### 6.9. Etapa 7: Exportação e Relatório Final
Gera a pasta consolidada de entrega e o funil PRISMA:
```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --export_final
PYTHONUNBUFFERED=1 "$PY" aneta.py --pipeline_report
```
*A entrega final fica disponível em `.data/OUTPUTS/final_results/`.*
