import os
import requests
import json
import re
import sys
from dotenv import load_dotenv

load_dotenv()

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


def converte_para_bibtex(record):
    """
    Converte um registro retornado pela API Elsevier para o formato BibTeX,
    adicionando as novas tags:
        - publisher
        - isbn
        - issn
        - volume
        - number
        - pages
        - source
        - journal
        - conference
        - keywords : key words of the publisher or journal
        - author_keywords : key words of authors
        - cited_by_count_source : cited in this search file
        - affiliations
        - autor_orcid
        - abbrev_source_title : short container title
        - openaccess : true or false
    """
    # Autores
    authors_list = record.get("authors", [])
    authors = "; ".join([autor.get("name", "").strip() for autor in authors_list if autor.get("name")])
    
    # Campos principais
    title = record.get("title", "").strip()
    publication_date = record.get("publicationDate", "")
    year = extrai_ano(publication_date)
    doi = record.get("doi", "").strip()
    uri = record.get("uri", "").strip()
    
    # Campos adicionais
    publisher = record.get("publisher", "").strip()
    isbn = record.get("isbn", "").strip()
    issn = record.get("issn", "").strip()
    
    # Para volume, tenta primeiro o campo "volume" se existir, senão utiliza "volumeIssue"
    volume = record.get("volume", record.get("volumeIssue", "")).strip()
    number = record.get("number", "").strip()
    
    # Processa o campo pages: verifica se há "first" e "last" ou só "first"
    pages_info = record.get("pages", {})
    if isinstance(pages_info, dict):
        first = pages_info.get("first", "").strip()
        last = pages_info.get("last", "").strip()
        pages = f"{first}--{last}" if first and last else first
    else:
        pages = str(pages_info).strip()
    
    # Outros campos
    source = record.get("source", record.get("sourceTitle", "")).strip()
    journal = record.get("journal", "").strip()
    conference = record.get("conference", "").strip()
    keywords_api = record.get("keywords", "").strip()  # key words of publisher or journal
    author_keywords = record.get("author_keywords", "").strip()
    cited_by_count_source = record.get("cited_by_count_source", "")
    # Se "cited_by_count_source" for numérico, converte para string
    cited_by_count_source = str(cited_by_count_source).strip() if cited_by_count_source is not None else ""
    
    # Affiliations: se for lista, junta por "; "
    affiliations_data = record.get("affiliations", [])
    if isinstance(affiliations_data, list):
        affiliations = "; ".join([aff.strip() for aff in affiliations_data if aff])
    else:
        affiliations = str(affiliations_data).strip()
    
    autor_orcid = record.get("autor_orcid", "").strip()
    abbrev_source_title = record.get("abbrev_source_title", "").strip()
    openaccess = str(record.get("openAccess", False)).lower()
    abstract = record.get("abstract", "").strip()
    
    # Define a chave do BibTeX utilizando o DOI (se disponível) ou parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    # Define o tipo de publicação (default: "Article")
    type_publication = "Article"
    
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
    
    out_dir = os.path.join(path_data, "science_direct")
    os.makedirs(out_dir, exist_ok=True)
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
                "sortBy": "relevance"
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

            records_agregados.extend(results)
            print(f"{len(results)} registros recebidos. Total acumulado: {len(records_agregados)}\n")

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
        print("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
        sys.exit(1)
    elif not records_agregados:
        print("\nNenhum registro foi encontrado. Nenhum arquivo será salvo.")
        return None

    # Salvando os resultados brutos em arquivo JSON
    try:
        with open(os.path.join(out_dir, "science_direct.json"), "w", encoding="utf-8") as f_json:
            json.dump(records_agregados, f_json, ensure_ascii=False, indent=4)
        print("Todos os resultados brutos salvos em 'science_direct.json'\n")
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        sys.exit(1)

    # Conversão dos registros para o formato BibTeX
    bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]

    try:
        with open(os.path.join(out_dir, "science_direct.bib"), "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Resultados convertidos para BibTeX salvos em 'science_direct.bib'")
    except Exception as e:
        print(f"Erro ao salvar o arquivo BibTeX: {e}")
        sys.exit(1)
    
    # Log final
    print("\n==============================================")
    print("     BUSCA FINALIZADA: SCIENCE DIRECT         ")
    print(f"   Artigos encontros e adicionados: {len(records_agregados)}")
    print("==============================================\n")


# ============================================================
# Execução principal
# ============================================================
if __name__ == "__main__":
    QUERY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEARCH_QUERY", "")
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATH_DATA", "../Sandbox/Data")
    PATH_DATA = os.path.join(PATH_DATA, ".bibs")
    main(QUERY, PATH_DATA)
