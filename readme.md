# ASRL - Automated Systematic Review Library

Biblioteca Python para automação de revisões sistemáticas da literatura científica.

## Facilitador agênico (agentes e skills)

O repositório traz um **facilitador de IA** que conduz o pipeline de SLR passo a passo,
**confirmando cada comando com você** (human-in-the-loop), com detecção de fase e retomada.
Funciona em **Claude Code**, **OpenCode** e **OpenAI Codex** a partir de um conjunto único de
agentes e skills (definições canônicas em `.agents/`, espelhadas em `.claude/`, `.codex/` e
`.opencode/`):

- **Orquestrador**: `.agents/agents/slr-orchestrator.md` — comece por ele: peça pelo agente
  `slr-orchestrator` na sua IDE ("start systematic review", "continue the review") ou pela
  skill `slr-status` ("onde estamos?").
- **Agentes de fase**: `slr-setup` → `slr-search` → `slr-abstract-screening` →
  `slr-acquisition` → `slr-fulltext-screening` → `slr-reporting`.
- **Skills**: `aneta-runner` (como executar o `aneta.py`), `slr-status` (funil/retomada) e as
  skills de autoria da metodologia (`slr-protocol`, `slr-search-strategy`,
  `slr-inclusion-criteria`, `slr-llm-config`, `slr-project-config`), além de
  `slr-pdf-acquisition` e `slr-decision-review`.
- **Documentação**: `docs/como-fazer/` (executar, aquisição de PDFs) e `docs/tecnica/`
  (arquitetura, pipeline, busca-dsl, triagem-llm, configuração, facilitador, pi-fast,
  saídas do funil). Visão geral do facilitador: `docs/tecnica/facilitador.md`.
  *Obs.:* `docs/tutorial.md`, `pipeline.md`, `busca-dsl.md`, `saidas-funil.md` e
  `aquisicao-pdfs.md` estão em sincronização pendente do OneDrive — ver
  `docs/tecnica/pendencias-onedrive.md`.

Sem agentes, o resultado é o mesmo: rode `aneta.py` diretamente (ver
`docs/como-fazer/executar.md`).

## Conceitos Básicos

### PDF Processing with Async Batch Support

O módulo `PDFReader` fornece processamento assíncrono de PDFs usando a biblioteca `docling` com controle de concorrência e otimização de processamento.

**Principais Recursos:**
- ⚡ **10-20x mais rápido**: Processamento paralelo vs sequencial
- 💾 **Eficiência de memória**: Dados retornados em memória, sem I/O desnecessário
- 🔄 **Otimização inteligente**: Evita reprocessamento de PDFs duplicados
- ⚙️ **Configurável**: Controle de concorrência via `.conf`

#### Uso Básico

**Via linha de comando:**
```bash
# Processar PDFs usando configuração padrão do .conf
python aneta.py --read_pdfs
```

**Via código Python:**
```python
from src.PDFReader import process_pdfs

# Processar ambas as pastas (PRE e POST) com deduplicação
results = process_pdfs()

# Processar apenas a pasta PRE
results = process_pdfs(mode="pre")

# Processar apenas a pasta POST
results = process_pdfs(mode="post")

# Acessar resultados
pre_pdfs = results["pre"]
post_pdfs = results["post"]

for pdf in pre_pdfs:
    if pdf["success"]:
        print(f"✓ {pdf['filename']}: {pdf['page_count']} páginas")
        print(pdf["markdown"][:100])  # Primeiros 100 caracteres
    else:
        print(f"✗ {pdf['filename']}: {pdf['error']}")
```

#### Configuração (.conf)

```bash
# Controle de concorrência (número de PDFs processados simultaneamente)
PDF_MAX_CONCURRENT=5

# Timeout por PDF em segundos
PDF_TIMEOUT_SECONDS=60

# Modo de processamento: "pre", "post", ou "both"
PDF_PROCESSING_MODE="both"

# Pastas de dados
PATH_DATA="./Data"
PDF_PRE_SELECTION_FOLDER="PDFs_PreSelection"
PDF_POST_SELECTION_FOLDER="PDFs"
```

#### Funções Principais

**1. `read_single_pdf(pdf_path: str)`**
- Processa um único PDF e retorna dados estruturados
- Inclui markdown, metadados e tratamento de erros

**2. `read_pdfs_batch(folder_path: str, max_concurrent: int)`**
- Processamento assíncrono em lote com controle de concorrência
- Continua processando mesmo se alguns PDFs falharem

**3. `process_pdfs(mode: Optional[str])`**
- Função orquestradora principal
- Lê configuração do `.conf`
- Otimiza por deduplicação de PDFs
- Retorna resultados estruturados: `{"pre": [...], "post": [...]}`

#### Otimização de Desempenho

**Valores recomendados de `PDF_MAX_CONCURRENT`:**
- **5-10**: Uso geral, bom equilíbrio entre velocidade e recursos
- **10-20**: Sistemas com 8+ CPU cores e boa velocidade de disco
- **1-3**: Sistemas com recursos limitados

**Benchmarks (com mocks):**
- 10 PDFs: < 5 segundos
- 50 PDFs: < 30 segundos
- 100 PDFs: < 5 minutos
- Memória: < 2GB para 100 PDFs

#### Estrutura de Retorno

```python
{
    "pre": [
        {
            "markdown": str,          # Conteúdo em formato markdown
            "filename": str,          # Nome do arquivo PDF
            "page_count": int,        # Número de páginas
            "processing_time": float, # Tempo de processamento em segundos
            "file_size_mb": float,    # Tamanho do arquivo em MB
            "success": bool,          # True se processado com sucesso
            "error": Optional[str]    # Mensagem de erro, se houver
        },
        # ... mais PDFs
    ],
    "post": [
        # Apenas PDFs que NÃO estão na pasta PRE (deduplicação automática)
    ]
}
```

#### Tratamento de Erros

- **Falha única**: Retorna `{"success": False, "error": "..."}` e continua
- **Falha total**: Lança `RuntimeError` com todos os detalhes de erro
- **Falhas parciais**: Retorna todos os resultados (sucesso + falha)

#### Migração da Função Antiga

Se você estava usando `read_pdfs_with_docling()`:

**Antes:**
```python
from src.PDFReader import read_pdfs_with_docling

read_pdfs_with_docling(
    folder_path="./PDFs",
    generate_markdown=True,
    markdown_output_folder="./markdown_outputs"
)
```

**Agora (mais rápido e eficiente):**
```python
from src.PDFReader import process_pdfs

# A nova função retorna dados em memória (sem arquivos markdown)
results = process_pdfs(mode="post")

# Se precisar salvar markdown:
for pdf_data in results["post"]:
    if pdf_data["success"]:
        filename = pdf_data["filename"].replace(".pdf", ".md")
        with open(f"./markdown_outputs/{filename}", "w") as f:
            f.write(pdf_data["markdown"])
```

#### Troubleshooting

**Problema**: "PATH_DATA not found in configuration"
- **Solução**: Verifique se a variável `PATH_DATA` está definida no arquivo `.conf`

**Problema**: Todos os PDFs falharam com "Memory error"
- **Solução**: Reduza `PDF_MAX_CONCURRENT` para um valor menor (ex: 3)

**Problema**: Processamento muito lento
- **Solução**: Aumente `PDF_MAX_CONCURRENT` (teste valores entre 5-20)

**Problema**: "Folder does not exist"
- **Solução**: Certifique-se que as pastas `PDF_PRE_SELECTION_FOLDER` e `PDF_POST_SELECTION_FOLDER` existem em `PATH_DATA`

# Regras básicas

## Enriquecimento

diretórios precisam estar com os nomes:

arxiv
ieee
science_direct
scopus
spring_nature
web_of_science
acm


### Bibtex estão na pastas
PATH_DATA + ".bibs"
precisa .bibs no final


# Configs



### impacts files
    Dados atualizados em Fevereiro de 2025 
        JCR referente a 2023
        SCIMAGO referente a 2025






Bibliometria

https://www.bibliometrix.org/vignettes/Introduction_to_bibliometrix.html

https://bibliometrix.org/documents/bibliometrix_Report.html

https://rforanalytics.com/06-method3.html

https://www.sciencedirect.com/science/article/pii/S1751157717300500

https://bibliometrix.org/biblioshiny/biblioshiny1.html

https://bibliometrix.org/biblioshiny/biblioshiny2.html



https://pt.slideshare.net/MassimoAria/bibliometrix-phd-seminar#2

https://github.com/NLeSC/litstudy/blob/master/notebooks/example.ipynb

https://colab.research.google.com/drive/1yHiMMZIKa-RrarXbPB9ca0gLN9YvvtPU?usp=sharing

https://www.vosviewer.com/features/screenshots

https://openalex.org/Visualizing_Science_Using_OpenAlex_and_VOSviewer.pdf

https://www.oaepublish.com/articles/jsegc.2022.09



Grafos:

https://github.com/medialab/ipysigma

exemplo: https://medium.com/@msdatashift/ipysigma-easily-visualize-networks-with-thousands-of-nodes-and-edges-in-python-3ecdbe0321de




instalar Python (colocar via linha de comando UV)
Instalar UV
Instalar R (via linha de comando)


usar R -> 
    R -e ' options(repos = c(CRAN = "https://cloud.r-project.org"));
           if (!require("devtools")) install.packages("devtools", repos = "https://cloud.r-project.org");
           if (!require("remotes")) install.packages("remotes", repos = "https://cloud.r-project.org");
           if (!require("bibliometrix")) install.packages("bibliometrix", repos = "https://cloud.r-project.org");
           if (!require("openalexR")) install.packages("openalexR", repos = "https://cloud.r-project.org");
           if (!require("gridExtra")) install.packages("gridExtra", repos = "https://cloud.r-project.org");
           if (!require("pander")) install.packages("pander", repos = "https://cloud.r-project.org");
          '

R -e 'options(repos = c(CRAN = "https://cloud.r-project.org"));
packages <- c(
  "bibliometrix",
  "openalexR",
  "gridExtra",
  "pander",
  "knitr",
  "reshape2",
  "ggplot2",
  "jsonlite",
  "openxlsx",
  "magrittr",
  "maps",
  "htmlwidgets",
  "wordcloud2",
  "RColorBrewer",
  "pandoc"
);


for (pkg in packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg, dependencies = TRUE)
  }
  library(pkg, character.only = TRUE)
};'


Linux: Use package manager (e.g., sudo apt-get install pandoc).
Macbook: Use package manager (e.g.,brew install pandoc).
Windows: Acesse o site oficial: https://pandoc.org/installing.html.
          choco install pandoc
          winget install --source winget --exact --id JohnMacFarlane.Pandoc

rum biblioshiny 
R -e 'library(bibliometrix); biblioshiny();'





## TODO: Implementar Bibliometria via Scopus, não apenas em OpenAlex
## TODO: Implementar download de pdf de forma assincrona


## TODO: Adicionar bibliometria e download de arquivos para final.bib além de select.bib
## todo: Adicionar bibliometria e download de arquivos para final.bib além de select.bib

## TODO: Implementar LLM Abstract assincrono
## TODO: Implementar parada e retomada por id do bibtex no one:one





## TODO: uv pip install docling