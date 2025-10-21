em ./.conf foram setadas alguas variáveis (que virarão variaveis de sistemas)

BIB_FILE="OUTPUTS/select_bibs.bib"
PATH_DATA=".data"

FILTER_LLM_RESPONSES_ABSTRACT_PATH="OUTPUTS/processed_responses/combined_responses_consolidated.json"
RELEVANT_ABSTRACT_PAPERS_OUTPUT="OUTPUTS/relevant_papers.json"
RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT="OUTPUTS/relevant_abstract_papers.bib"
FILTER_LLM_CONFIG_PATH="config/filter_accept_results_llm.yaml"


os valores são mutaveis, de acordo com a configuração desejada.

Leia ./conf para entender como funciona o arquivo.


além disso existe um arquivo de filtragem, no caso leia config/filter_accept_results_llm.yaml como exemplo.

Esse arquivo de filtragem possui sempre uma key chamada filter, a string dessa key é uma clausula sql where aplicada a um banco de dados em memória duckdb.

esse banco de dados deve ser originário dos dados em FILTER_LLM_RESPONSES_ABSTRACT_PATH

de acordo com os dados filtrados devem ser gerados dois arquivos. RELEVANT_ABSTRACT_PAPERS_OUTPUT, um json com exatamente os mesmo dados de FILTER_LLM_RESPONSES_ABSTRACT_PATH mas depois de filtrados
e um arquivo .bib em RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT que devem ser os bibtex filtrados provenientes de da váriavel BIB_FILE filtrados de acordo com o filtro aplicado.

Para gerar o bibtex os arquivos FILTER_LLM_RESPONSES_ABSTRACT_PATH e RELEVANT_ABSTRACT_PAPERS_OUTPUT possuem os seguintes campos: doi e id (id é o id do bibtex), além disso o campo title. Deve procurar primeiro como match o campo doi, seguido depois por title e por fim id para gerar o bibtex filtrado.

detalhe, os diretorios OUTPUTS saõ precedidos do caminho em PATH_DATA, as variáveis FILTER_LLM_RESPONSES_ABSTRACT_PATH, RELEVANT_ABSTRACT_PAPERS_OUTPUT e RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT devem sem composta com o caminho base PATH_DATA. Entenda como isso é contruido de forma parecida no script aneta.py


entenda como funciona os arquivos OUTPUTS/processed_responses/combined_responses_consolidated.json e o exemplo de um arquivo bib em OUTPUTS/select_bibs.bib
além disso entenda como exemplo operação de filtragem em duckdb advinda de arquivos de configuração em um código que tem funções parecida em src/Selection.py

use bibliotecas padrões e uteis como src/BibTex.py

abaixo uma solicitação um pouco mais refinada do que deve ser feito:

Create a Python script that performs bibliographic entry filtering based on configuration files using DuckDB queries. The script should:

1. Read system variables from `.conf`:
- `BIB_FILE`: Path to source BibTeX file
- `PATH_DATA`: Base path for data operations
- `FILTER_LLM_RESPONSES_ABSTRACT_PATH`: Path to JSON with paper metadata
- `RELEVANT_ABSTRACT_PAPERS_OUTPUT`: Path for filtered JSON output
- `RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT`: Path for filtered BibTeX output
- `FILTER_LLM_CONFIG_PATH`: Path to filtering configuration YAML

2. Process the filter configuration:
- Read YAML file from `config/filter_accept_results_llm.yaml`
- Extract SQL WHERE clause from 'filter' key
- Apply filtering to in-memory DuckDB database

3. Generate filtered outputs:
- Create filtered JSON matching source structure
- Generate filtered BibTeX entries by matching papers using:
  1. DOI
  2. Title
  3. BibTeX ID

4. File path handling:
- Prepend `PATH_DATA` to output paths
- Follow existing path construction pattern from aneta.py

Required functionality:
- Load and parse BibTeX files (use src/BibTex.py)
- Execute DuckDB queries on JSON data
- Maintain source file structure
- Handle file paths consistently

Input file examples:
- Configuration: config/filter_accept_results_llm.yaml
- Source data: OUTPUTS/processed_responses/combined_responses_consolidated.json
- BibTeX data: OUTPUTS/select_bibs.bib
- Reference implementation: src/Selection.py

Please provide Python implementation focusing on:
- Standard library usage
- Existing utility code reuse
- Proper file path handling
- Efficient database operations
- Robust entry matching logic