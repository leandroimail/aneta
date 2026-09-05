# Configuração

Aneta lê a configuração de três lugares, com papéis distintos:

| Arquivo | Versionado? | Papel |
|---|---|---|
| `.conf` | sim | **Parâmetros operacionais** — caminhos de dados, nomes de saída, concorrência |
| `config/*.yaml` | sim | **Metodologia da revisão** — perguntas, busca, critérios de inclusão, prompts |
| `config/.env` | **não** (gitignored) | **Segredos e painéis de LLM** — chaves de API e blocos `LLM_CLIENTS_*` |

No início de cada execução, `setup_environment()` em `aneta.py` carrega `.conf` e
`config/.env` e exporta `PROJECT_PATH`. Os YAMLs são lidos pelos módulos que precisam
deles.

> **Regra de ouro dos segredos:** as chaves de API vivem **apenas** em `config/.env`,
> são lidas via `os.getenv` e nunca devem ser impressas ou versionadas.

---

## `.conf` — parâmetros operacionais

Formato `CHAVE=valor` (lido como variáveis de ambiente). Principais grupos:

### Caminhos de dados

| Chave | Padrão | Descrição |
|---|---|---|
| `PATH_DATA` | `.data` | Raiz dos dados e saídas (gitignored) |
| `BIB_FILE` | `OUTPUTS/select_bibs.bib` | BibTeX selecionado por metadados (entrada da triagem) |
| `DOI_FILE` | `OUTPUTS/DOIs.txt` | Lista de DOIs |
| `FOLDER_SAVE_PDF` | `PDFs` | Pasta de PDFs baixados |
| `BIB_FILE_DOWNLOAD_PDF` | `OUTPUTS/relevant_abstract_papers.bib` | BibTeX que orienta o download |
| `PATH_JCR` / `PATH_SCIMAGO` | `ImpactFiles/jcr.csv` / `ImpactFiles/scimago.csv` | Tabelas de fator de impacto (JCR 2023 / SCImago 2025) |

> Os caminhos relativos são resolvidos sob `PATH_DATA`. A convenção interna é que os
> `.bib` de origem ficam em `PATH_DATA/.bibs/` (note o sufixo `.bibs`).

### Leitura de PDF (`--read_pdfs`, Docling)

| Chave | Padrão | Descrição |
|---|---|---|
| `PDF_PRE_SELECTION_FOLDER` | `PDFs_PreSelection` | Pasta de PDFs pré-seleção |
| `PDF_POST_SELECTION_FOLDER` | `PDFs` | Pasta de PDFs pós-seleção |
| `PDF_PROCESSING_MODE` | `both` | `pre`, `post` ou `both` (deduplica) |
| `PDF_MAX_CONCURRENT` | `5` | PDFs processados em paralelo (recomendado 3–10) |
| `PDF_TIMEOUT_SECONDS` | `60` | Timeout por PDF |
| `GENERATE_MARKDOWN_OUTPUT` / `MARKDOWN_OUTPUT_FOLDER` | `true` / `PDFs/markdowns` | Exporta markdown extraído |
| `GENERATE_TABLES_OUTPUT` / `TABLES_OUTPUT_FOLDER` | `true` / `PDFs/tables` | Exporta tabelas (CSV) |
| `GENERATE_IMAGES_OUTPUT` / `IMAGES_OUTPUT_FOLDER` | `true` / `PDFs/images` | Exporta imagens (PNG) |

### Filtro de relevância (abstract)

| Chave | Padrão | Descrição |
|---|---|---|
| `FILTER_LLM_RESPONSES_ABSTRACT_PATH` | `OUTPUTS/processed_responses/combined_responses_consolidated.json` | Consolidado de votos por abstract |
| `RELEVANT_ABSTRACT_PAPERS_OUTPUT` | `…/relevant_papers.json` | Aprovados no abstract |
| `UNRELEVANT_ABSTRACT_PAPERS_OUTPUT` | `…/unrelevant_papers.json` | Rejeitados no abstract |
| `RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT` | `OUTPUTS/relevant_abstract_papers.bib` | BibTeX dos aprovados (entrada do download e do full-text) |
| `FILTER_LLM_CONFIG_PATH` | `config/filter_accept_results_llm.yaml` | Cláusula SQL de inclusão (abstract) |
| `SELECTION_DECISIONS_EXCEL_OUTPUT` | `…/selection_decisions.xlsx` | Planilha de decisão com motivo por artigo |

### Filtro final (texto completo)

| Chave | Padrão | Descrição |
|---|---|---|
| `FILTER_LLM_RESPONSES_FULLTEXT_PATH` | `…/combined_responses_fulltext_consolidated.json` | Consolidado de votos por texto completo |
| `FINAL_PAPERS_OUTPUT` / `FINAL_EXCLUDED_PAPERS_OUTPUT` | `…/final_papers.json` / `…/final_excluded_papers.json` | Incluídos / excluídos finais |
| `FINAL_PAPERS_BIBs_OUTPUT` | `OUTPUTS/final_papers.bib` | BibTeX final |
| `FILTER_LLM_CONFIG_FULLTEXT_PATH` | `config/filter_accept_results_llm_fulltext.yaml` | Cláusula SQL final |
| `SELECTION_DECISIONS_FULLTEXT_EXCEL_OUTPUT` | `…/selection_decisions_fulltext.xlsx` | Planilha de decisão final |
| `FULLTEXT_MAX_CHARS` | `400000` | Teto de caracteres enviado ao LLM (0 = sem limite) |
| `FINAL_RESULTS_FOLDER` | `OUTPUTS/final_results` | Pasta de **entrega** (`--export_final`) |

### Outras variáveis lidas do ambiente (não estão no `.conf` por padrão)

- `DOWNLOAD_MAX_CONCURRENT` (default `8`) — concorrência de `--download_pdf_async`.
- `DOWNLOAD_BROWSER_CONCURRENT` — concorrência do download por navegador (Playwright).
- `SCOPUS_VIEW`, `SPRINGER_EXCLUDE_BIBLIOGRAPHY` — ajustes finos por base (ver
  [busca-dsl.md](busca-dsl.md)).

---

## `config/*.yaml` — metodologia

Estes arquivos são a **metodologia autorada pelo humano**. Cada um tem uma skill de
autoria dedicada (ver [facilitador.md](facilitador.md)).

### `research_questions.yaml` — protocolo

Define a pergunta principal, perguntas adicionais/de apoio e os critérios de
aceitação/rejeição. Chaves: `principal_research_question`, `additional_research_questions`
(`arq1`…), `supporting_questions` (`sq1`…), `accepted_criteria` (`ac1`…),
`rejection_criteria` (`rc1`…). Essas chaves são injetadas nos prompts de triagem (os
placeholders `{{questions}}`, `{{accepted_criteria}}`, etc.).

### `search_config.yaml` — estratégia de busca

- **Liga/desliga bases**: `arxiv`, `science_direct`, `spring_nature`, `acm` (não
  suportada para busca), `web_of_science`, `ieee`, `scopus` (`true`/`false`).
- **`search_string`**: a query na DSL do Aneta (ver [busca-dsl.md](busca-dsl.md)).
- **`filter_string`**: cláusula SQL `WHERE` (DuckDB) do filtro de escopo aplicado após a
  busca, sobre `title`, `abstract`, `keywords`, `jcr`, `scimago`, `year`,
  `type_publication`, `publication`.

### `general_config.yaml` — opções de enriquecimento e download

- Enriquecimento: `enrich_bibtex_doi`, `enrich_bibtex_abstract`, `enrich_bibtex_keywords`,
  `enrich_bibtex_jcr_scimago`, `enrich_arxiv`.
- Download: `enable_playwright_download`, `enable_PyPaperBot_download`,
  `enable_search_link_file_by_google_scholars`, `enable_save_md_to_lost_papers`.

> O arquivo também tem chaves `bibliometry_*` (análise bibliométrica via R), fora do escopo
> desta documentação.

### `filter_accept_results_llm.yaml` / `…_fulltext.yaml` — cláusula de inclusão

Uma única chave `filter:` com uma expressão SQL `WHERE` sobre as colunas de votos
consolidados. É **o coração da decisão de inclusão** e está documentada em detalhe em
[triagem-llm.md](triagem-llm.md).

### Prompts

| Arquivo | Usado por |
|---|---|
| `src/GenerativeAI/abstract_base_prompts.yaml` (e `…_one_on_one.yaml`) | Triagem por abstract |
| `config/fulltext_base_prompts.yaml` | Triagem por texto completo |
| `config/aditional_prompts.yaml` | Prompts auxiliares |

Os prompts impõem o **formato de resposta binário** (`yes`/`no` para
`research_questions`, `accepted_criteria`, `rejection_criteria` e `is_relevant`; em caso
de dúvida, `no`) e a estrutura JSON de saída. É esse contrato que torna o voto
consolidável.

---

## `config/.env` — segredos e painéis de LLM

Define os **painéis de LLM** que votam em cada etapa, via blocos `LLM_CLIENTS_<GRUPO>`:

- `LLM_CLIENTS_ABSTRACT` — painel da triagem por abstract.
- `LLM_CLIENTS_FULL_TEXT` — painel da triagem por texto completo.

Cada *id* da lista expande para variáveis `LLM_<ID>_*` (provedor, modelo, env da chave,
rate limit, etc.). O modelo completo está em [exemplo_config_llm.md](../../exemplo_config_llm.md)
e o passo a passo de autoria em [triagem-llm.md](triagem-llm.md).

Se os blocos `LLM_CLIENTS_*` estiverem vazios, o Aneta cai no modo **single-LLM** legado
(variáveis `LLM_*_ABSTRACT`), 100% compatível.
