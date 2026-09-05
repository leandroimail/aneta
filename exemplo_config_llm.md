# Configuração de múltiplos LLMs (multi-LLM) na classificação por abstract

O Aneta pode classificar/filtrar papers por abstract usando **vários LLMs ao mesmo tempo**
(múltiplos modelos/provedores). Cada LLM processa **todos** os artigos de forma **independente**
e grava seus resultados em pasta própria — sem voto/consenso embutido. A decisão final de
relevância continua a cargo do SQL em `--filter_relevant_papers`, que opera sobre o consolidado
(o passo `--process_responses` mescla por DOI registrando quais LLMs avaliaram cada paper).

Funciona nos 3 modos de abstract:

| Comando                                           | Modo            | Concorrência entre LLMs |
|---------------------------------------------------|-----------------|-------------------------|
| `--abstract_classifier_llm`                       | batch           | sequencial              |
| `--abstract_classifier_llm_one_on_one`            | one-on-one sync | sequencial              |
| `--abstract_classifier_llm_one_on_one_async`      | one-on-one async| concorrente (1 semáforo/LLM) |

## Como configurar (`config/.env`)

A configuração é **por grupo**. Para o grupo de abstract use `LLM_CLIENTS_ABSTRACT` com uma lista
de *ids* separados por vírgula. Para cada *id* defina as variáveis `LLM_<ID>_*`:

```env
# Lista de LLMs para classificação de abstract.
# Vazio/ausente => usa o LLM único legado (LLM_*_ABSTRACT) — comportamento atual.
LLM_CLIENTS_ABSTRACT=openai-nano,gemini-flash

# --- Cliente 1 ---
LLM_OPENAI_NANO_PROVIDER=openai            # openai | gemini | deepseek
LLM_OPENAI_NANO_MODEL=gpt-4.1-nano
LLM_OPENAI_NANO_API_KEY_ENV=LLM_API_KEY_SIMPLE   # nome da var que guarda a chave (reuso)
# LLM_OPENAI_NANO_API_KEY=sk-...                  # alternativa: chave inline
LLM_OPENAI_NANO_RATE_LIMIT=200             # req/s (opcional; fallback: rate-limit do grupo)
LLM_OPENAI_NANO_OVERWRITE=false            # opcional (fallback: LLM_OVERWRITE_ABSTRACT)

# --- Cliente 2 ---
LLM_GEMINI_FLASH_PROVIDER=gemini
LLM_GEMINI_FLASH_MODEL=gemini-2.5-flash
LLM_GEMINI_FLASH_API_KEY_ENV=LLM_API_KEY_ABSTRACT
LLM_GEMINI_FLASH_IS_REASONER=false         # opcional (Gemini)
```

### Variáveis por cliente (`LLM_<ID>_*`)

O `<ID>` da lista vira o sufixo das variáveis: caracteres não-alfanuméricos viram `_` e tudo
em maiúsculas (ex.: `openai-nano` → `LLM_OPENAI_NANO_*`).

| Variável                 | Obrigatória | Descrição |
|--------------------------|-------------|-----------|
| `LLM_<ID>_PROVIDER`      | sim         | `openai`, `gemini` ou `deepseek` |
| `LLM_<ID>_MODEL`         | sim         | nome do modelo |
| `LLM_<ID>_API_KEY_ENV`   | sim*        | nome da variável que contém a chave (indireção/reuso) |
| `LLM_<ID>_API_KEY`       | sim*        | alternativa: chave inline (*ao menos uma das duas*) |
| `LLM_<ID>_BASE_URL`      | não         | URL base custom (ex.: DeepSeek) |
| `LLM_<ID>_RATE_LIMIT`    | não         | req/s; default = rate-limit do grupo |
| `LLM_<ID>_OVERWRITE`     | não         | sobrescreve respostas já salvas; default = `LLM_OVERWRITE_ABSTRACT` |
| `LLM_<ID>_IS_REASONER`   | não         | modelos de raciocínio (Gemini) |
| `LLM_<ID>_NAME`          | não         | nome de exibição/pasta de saída; default = `<id>` |
| `LLM_<ID>_ENABLED`       | não         | `false` desabilita o cliente |

> **Dica:** prefira *ids* com hífen (`openai-nano`) em vez de underscore — os nomes de arquivo de
> saída ficam mais limpos para o passo de consolidação.

## Compatibilidade (single-LLM)

Se `LLM_CLIENTS_ABSTRACT` (e o genérico `LLM_CLIENTS`) estiverem **vazios/ausentes**, o Aneta usa
exatamente **um** LLM, derivado das variáveis legadas — comportamento 100% idêntico ao atual:

```env
LLM_MODEL_ABSTRACT=gemini-2.5-flash
LLM_API_KEY_ABSTRACT=...
LLM_API_TYPE_ABSTRACT=Gemini            # OpenAI | Gemini | DeepSeek
LLM_SECOND_RATE_LIMITE_ABSTRACT=200
LLM_OVERWRITE_ABSTRACT=false
```

## Saídas

Cada LLM grava de forma independente:

- **one-on-one (sync/async):** `\.data/OUTPUTS/raw_responses/<NAME>/response_<n>_<NAME>_<MODEL>_raw.txt`
- **batch:** `\.data/OUTPUTS/select_bibs_filtered_by_abstract_<NAME>_<MODEL>_raw.txt`

O passo `--process_responses` lê todas as subpastas de `raw_responses/` (uma por LLM) e mescla por
DOI; `--filter_relevant_papers` aplica o SQL configurável sobre o resultado.

## Outros grupos

A mesma mecânica existe para outros grupos (genérica):
`LLM_CLIENTS_FULL_TEXT`, `LLM_CLIENTS_SYSTEMATIC_REVIEW` (com fallback para os respectivos
`LLM_*_FULL_TEXT` / `LLM_*_SYSTEMATIC_REVIEW`). Atualmente apenas o grupo **ABSTRACT** está ligado
nos comandos de classificação.
