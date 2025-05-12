import os
import shutil
import requests
import json
import re
import sys
import yaml
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = os.getenv("ELSEVIER_API_KEY", "")
BASE_URL = 'https://api.elsevier.com/content/search/sciencedirect'

# Remova QS_QUERY fixa; use "query" que será passado
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 25))
records_agregados = []

# ============================================================
# Funções auxiliares
# ============================================================
def extrai_ano(data_str):
    """
    Extrai o ano (quatro dígitos) de uma string de data.
    """
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def get_metadata(list_pii, API_KEY):
    """Obtém os metadados dos artigos via Elsevier API."""
    dois_query = " OR ".join([f'"{pii}"' for pii in list_pii])
    query = f'pii({dois_query})'
    query_encoded = quote(query)
    url = (
        f'https://api.elsevier.com/content/metadata/article'
        f'?query={query_encoded}&apiKey={API_KEY}&view=COMPLETE'
    )
    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        response.raise_for_status()  
        return response.json()
    except requests.RequestException as e:
        print("Erro na requisição:", e)
        return None

def converte_para_bibtex(record):
    """
    Converte um registro da API Elsevier para o formato BibTeX.
    Mapeia os seguintes campos do record:
      - dc:title              -> title
      - dc:description        -> abstract
      - prism:coverDate       -> year (extraído via extrai_ano)
      - prism:doi ou dc:identifier -> doi
      - prism:url             -> url_html
      - prism:isbn            -> isbn
      - prism:issn            -> issn
      - prism:volume          -> volume
      - prism:issueIdentifier -> number
      - prism:startingPage e prism:endingPage -> pages
      - prism:publicationName -> source e journal
      - authkeywords          -> author_keywords
      - openaccessArticle     -> openaccess
      - pubType               -> type_publication
    Os demais campos são preenchidos com valor vazio.
    """
    # Autores: se 'authors' for uma lista, une os nomes; se for string, utiliza diretamente.
    authors = ""
    authors_data = record.get("authors", {})
    if isinstance(authors_data, dict) and "author" in authors_data:
        authors_data = [author.get("$", "") for author in authors_data["author"]]
        authors = "; ".join(authors_data)     
    
    title = record.get("dc:title", "").strip()
    abstract = record.get("dc:description", "")
    cover_date = record.get("prism:coverDate", "")
    year = extrai_ano(cover_date)
    doi = record.get("prism:doi", "").strip() or record.get("dc:identifier", "").strip()
    uri = record.get("prism:url", "").strip()

    # Não há mapeamento específico para publisher na documentação fornecida
    publisher = ""

    isbn = record.get("prism:isbn", "").strip()
    issn = record.get("prism:issn", "").strip()
    volume = record.get("prism:volume", "").strip()
    number = record.get("prism:issueIdentifier", "").strip()
    
    first = record.get("prism:startingPage", "").strip()
    last = record.get("prism:endingPage", "").strip()
    pages = f"{first}--{last}" if first and last else first
    
    source = record.get("prism:publicationName", "").strip()
    journal = source  # Usa o mesmo valor do source para journal
    conference = ""
    keywords_api = ""  # Não há mapeamento específico para keywords de publisher ou journal
    author_keywords = record.get("authkeywords", "")
    if author_keywords:
        author_keywords = author_keywords.strip().replace("|", ";").replace(",", ";")
    cited_by_count_source = ""
    affiliations = ""
    autor_orcid = ""
    abbrev_source_title = ""
    openaccess = str(record.get("openaccessArticle", False)).lower()
    type_publication = record.get("prism:aggregationType", "")
    if type_publication:
        type_publication = type_publication.strip().lower()
    if type_publication == "journal":
        type_publication = "Article"
    elif type_publication == "book":
        type_publication = "Book"
    elif type_publication == "book series":
        type_publication = "InCollection"
    elif type_publication == "referencework":
        type_publication = "InReference"
    elif record.get("prism:aggregationType", "").strip().lower() in ('fla', 'rev', 'rpl'):
        type_publication = "Article"
    else:
        type_publication = ""
    
    # Define a chave do BibTeX utilizando o DOI (se disponível) ou parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  title = {{{title}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  year = {{{year}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{uri}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  isbn = {{{isbn}}},\n"
        f"  issn = {{{issn}}},\n"
        f"  volume = {{{volume}}},\n"
        f"  number = {{{number}}},\n"
        f"  pages = {{{pages}}},\n"
        f"  source = {{{source}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  conference = {{{conference}}},\n"
        f"  keywords = {{{keywords_api}}},\n"
        f"  author_keywords = {{{author_keywords}}},\n"
        f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
        f"  affiliations = {{{affiliations}}},\n"
        f"  autor_orcid = {{{autor_orcid}}},\n"
        f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
        f"  openaccess = {{{openaccess}}},\n"
        f"  type_publication = {{{type_publication}}}\n"
        f"}}\n"
    )
    return bibtex_entry

# ============================================================
# Função principal
# ============================================================
def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("      INICIANDO BUSCA: SCIENCE DIRECT         ")
    print("==============================================\n")
    
    if not query:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        query = config.get("search_string", config.get("search_string", None)) 
    if not query:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração Config/search_config.yaml não foi definida")
    
    query = query.strip().replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').replace('  ', ' ')
    
    out_dir = os.path.join(path_data, "science_direct")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    global records_agregados
    erro_ocorrido = False

    print("Iniciando a coleta dos registros da API Elsevier (ScienceDirect) via PUT...\n")

    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE != 0 else 0)
    print(f"Será necessário realizar até {num_requisicoes} requisições (show={PAGE_SIZE}).\n")

    # Cabeçalhos necessários para a requisição PUT
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Loop de paginação
    for i in range(num_requisicoes):
        offset = i * PAGE_SIZE

        # Corpo da requisição seguindo o schema da API v2
        body = {
            "qs": query,
            "display": {
                "offset": offset,
                "show": PAGE_SIZE,
                "view": "COMPLETE",
                "sortBy": "relevance",
                "field": "doi,pii"
            }
        }

        print(f"Requisição {i+1} iniciada para resultados a partir do offset {offset}.")
        print(f"Corpo da requisição: {json.dumps(body)}\n")

        try:
            response = requests.put(BASE_URL, json=body, headers=headers)
        except Exception as e:
            print(f"Exceção durante a requisição: {e}")
            erro_ocorrido = True
            break

        if response.status_code == 200:
            print(f"Requisição bem-sucedida (status {response.status_code}).")
            try:
                data = response.json()
            except Exception as e:
                print(f"Erro ao decodificar o JSON da resposta: {e}")
                erro_ocorrido = True
                break

            results = data.get("results", [])
            if not results:
                print("Nenhum registro retornado nesta página. Encerrando a coleta.\n")
                break

            list_pii = [item.get("pii") for item in results if item.get("pii")]
            metadata = get_metadata(list_pii, API_KEY)

            if metadata:
                records_agregados.extend(metadata.get("search-results", {}).get("entry", []))
                print(f"{len(metadata)} registros recebidos. Total acumulado: {len(records_agregados)}\n")

            # Se o número de registros retornados for menor que o tamanho da página, encerra a coleta
            if len(results) < PAGE_SIZE:
                print("Menos registros retornados que o esperado para a página. Finalizando a coleta.\n")
                break
        else:
            if response.status_code in [401, 403]:
                print("**************************************************")
                print("*               ERRO DE ACESSO                 *")
                print("**************************************************")
                print("Houve um erro de acesso;\nVerifique se você tem acesso à rede de uma instituição conveniada ou esteja na VPN da instituição.")

            print(f"Erro na requisição: código de status {response.status_code}.")
            try:
                error_info = response.json()
                print(json.dumps(error_info, indent=4, ensure_ascii=False))
            except Exception:
                print(response.text)
            erro_ocorrido = True
            break

    if erro_ocorrido:
        raise Exception("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
    elif not records_agregados:
        print("\nNenhum registro foi encontrado. Nenhum arquivo será salvo.")
        return None

    # Salvando os resultados brutos em arquivo JSON
    try:
        with open(os.path.join(out_dir, "science_direct.json"), "w", encoding="utf-8") as f_json:
            json.dump(records_agregados, f_json, ensure_ascii=False, indent=4)
        print("Todos os resultados brutos salvos em 'science_direct.json'\n")
    except Exception as e:
        raise Exception(f"Erro ao salvar o arquivo JSON: {e}")

    # Conversão dos registros para o formato BibTeX
    bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]

    try:
        with open(os.path.join(out_dir, "science_direct.bib"), "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Resultados convertidos para BibTeX salvos em 'science_direct.bib'")
    except Exception as e:
        raise Exception(f"Erro ao salvar o arquivo BibTeX: {e}")
    
    # Log final
    print("\n==============================================")
    print("     BUSCA FINALIZADA: SCIENCE DIRECT         ")
    print(f"   Artigos encontros e adicionados: {len(records_agregados)}")
    print("==============================================\n")

