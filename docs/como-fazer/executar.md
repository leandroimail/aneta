# Como executar o Aneta

Antes de rodar qualquer comando você precisa de um interpretador Python com as
dependências do Aneta instaladas. Este guia mostra como resolvê-lo e o padrão de execução
(incluindo runs longos).

---

## Uso sem agentes

Este guia é o caminho manual: você resolve o interpretador e chama `aneta.py` diretamente.
Se quiser conduzir a revisão com confirmação passo a passo por agentes, veja
[facilitador.md](../tecnica/facilitador.md).

## 1. Resolva um interpretador funcional

### Opção A — bootstrap do `aneta-runner` (recomendado neste repositório)

É a forma usada pelo facilitador. O script tenta `~/.cache/aneta-run-venv/bin/python`; se
faltar ou falhar um *import-check*, cria o venv e instala as dependências centrais, então
imprime **só o caminho do Python** em stdout:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
echo "interpretador: $PY"
```

Códigos de saída: `0` ok (caminho no stdout) · `2` falha ao instalar dependências · `3`
ainda faltam deps essenciais após o bootstrap. Sobrescreva o local com
`ANETA_VENV=/caminho`. O *import-check* exige: `openai`, `pydantic`, `dotenv`, `yaml`,
`bibtexparser`, `openpyxl`, `fitz` (PyMuPDF), além de `lancedb`, `duckdb`, `pandas` e
`requests` (núcleo de enriquecimento/seleção). Stacks pesados/opcionais (`docling`,
`playwright`, `undetected_chromedriver`) **não** entram no bootstrap básico.

### Opção B — uv

Usa o `pyproject.toml` (+ `uv.lock`) para criar o ambiente:

```bash
uv sync
PY=".venv/bin/python"      # ou rode os comandos com: uv run python aneta.py …
```

### Opção C — venv manual (pip)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PY="$(which python)"
```

---

## 2. Rode um comando

Sempre exporte o `$PY` resolvido e use `PYTHONUNBUFFERED=1` (o `aneta.py` já é
line-buffered, mas isso cobre subprocessos e qualquer saída antes do flush):

```bash
PYTHONUNBUFFERED=1 "$PY" aneta.py --selection
```

Sem flags, `aneta.py` imprime a ajuda. A lista completa de comandos está em
[../tecnica/pipeline.md](../tecnica/pipeline.md).

---

## 3. Runs longos (triagem, download) — em background

Triagem e download levam de minutos a ~1 hora. Rode-os destacados, com um log
timestampado, e acompanhe o progresso pelo log / pastas de resposta:

```bash
PY="$(bash .agents/skills/aneta-runner/scripts/ensure_env.sh "$PWD")"
LOG="/tmp/aneta_$(date +%s).log"
PYTHONUNBUFFERED=1 "$PY" aneta.py --fulltext_classifier_llm_async > "$LOG" 2>&1 &
echo "log: $LOG"
```

Sinais de progresso para `grep` no log: `successfully processed`, `⚠ Error`, `⏱ Timeout`,
e as contagens por LLM em `.data/OUTPUTS/raw_responses*/<llm>/`.

> **Retomada segura:** re-rodar a mesma triagem/download pula o trabalho já concluído
> (ciente de DOI). Se um provedor falhar no meio, basta re-rodar para preencher as
> lacunas. É por isso que, ao reentrar, o padrão é continuar de onde parou.

---

## 4. Dependências opcionais sob demanda

| Comando | Dep extra | Instalação |
|---|---|---|
| `--read_pdfs` | `docling` (stack de ML) | `"$PY" -m pip install docling` |
| `--download_pdf_assisted` / CDP | `playwright`, `undetected_chromedriver`, `setuptools<81` | `"$PY" -m pip install playwright undetected_chromedriver "setuptools<81" && "$PY" -m playwright install chromium` |

> Com a **Opção B (uv)**, `docling` e `undetected_chromedriver` já vêm do `pyproject.toml`;
> o `playwright` continua extra (`uv pip install playwright && uv run playwright install chromium`).

---

## 5. Uso com agentes

O facilitador cross-IDE usa o mesmo padrão de execução, mas detecta a fase atual, mostra o
funil e pede confirmação antes de cada comando. Peça pelo agente `slr-orchestrator`
(ex.: "continue the review" ou "start systematic review") ou pela skill `slr-status`,
conforme a IDE. Detalhes em [facilitador.md](../tecnica/facilitador.md).

## 6. Boas práticas

- **Nunca** imprima chaves de API. Elas vivem em `config/.env` (gitignored) e são lidas
  por `os.getenv`.
- **Não** commite nada sob `.data/` (saída de execução, gitignored).
- Reporte erros/timeouts do log em vez de assumir sucesso.
- Para runs de revisão completos, prefira o facilitador (`/slr-orchestrator`): ele já
  aplica este padrão e mantém os checkpoints humanos explícitos.
