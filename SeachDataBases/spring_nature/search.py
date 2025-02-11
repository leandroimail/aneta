import requests
import json
import re
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Obtém a chave e removemos a constante fixa
API_KEY = os.getenv("SPRINGER_API_KEY", "")
BASE_URL = 'https://api.springernature.com/meta/v2/json'
# Remova a constante QUERY fixa; será recebida como parâmetro
# QUERY = '("Schema Matching" AND (...))'
RESULTS_DESEJADOS = 500
PAGE_SIZE = 25
records_agregados = []

def extrai_ano(data_str):
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def converte_para_bibtex(record):
    # Obtém autores
    authors_list = record.get('creators', [])
    authors = "; ".join([creator['creator'] for creator in authors_list])

    keywords = record.get('keyword', '')
    if isinstance(keywords, list):
        keywords = "; ".join(keywords)
    elif isinstance(keywords, str):
        keywords = keywords.strip()
    else:
        keywords = ""

    abstract = record.get('abstract', '').strip()
    title = record.get('title', '').strip()
    cover_date = record.get('publicationDate', '')
    year = extrai_ano(cover_date)
    type_publication = record.get('contentType', '').strip()
    publication = record.get('publicationName', '').strip()
    publisher = record.get('publisherName', '').strip()  # Nome da editora responsável pela publicação
    doi = record.get('doi', '').strip()

    # Extrai as URLs para PDF e HTML, se disponíveis
    url_pdf = ""
    url_html = ""
    urls = record.get("url", [])
    if isinstance(urls, list):
        for link in urls:
            if isinstance(link, dict):
                fmt = link.get("format", "").lower()
                if fmt == "pdf":
                    url_pdf = link.get("value", "")
                elif fmt == "html":
                    url_html = link.get("value", "")

    # Cria uma chave única para o BibTeX; utiliza o DOI se disponível, senão utiliza parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"

    # Constrói a entrada BibTeX com os novos campos url_pdf e url_html
    if type_publication == "Chapter ConferencePaper":
        bibtex_entry = (
            f"@inproceedings{{{bibtex_key},\n"
            f"  authors = {{{authors}}},\n"
            f"  keywords = {{{keywords}}},\n"
            f"  abstract = {{{abstract}}},\n"
            f"  title = {{{title}}},\n"
            f"  year = {{{year}}},\n"
            f"  type_publication = {{{type_publication}}},\n"
            f"  publication = {{{publication}}},\n"
            f"  publisher = {{{publisher}}},\n"
            f"  doi = {{{doi}}},\n"
            f"  url_pdf = {{{url_pdf}}},\n"
            f"  url_html = {{{url_html}}}\n"
            f"}}\n"
        )
    else:  # Default para tipo "Article"
        bibtex_entry = (
            f"@article{{{bibtex_key},\n"
            f"  authors = {{{authors}}},\n"
            f"  keywords = {{{keywords}}},\n"
            f"  abstract = {{{abstract}}},\n"
            f"  title = {{{title}}},\n"
            f"  year = {{{year}}},\n"
            f"  type_publication = {{{type_publication}}},\n"
            f"  publication = {{{publication}}},\n"
            f"  publisher = {{{publisher}}},\n"
            f"  doi = {{{doi}}},\n"
            f"  url_pdf = {{{url_pdf}}},\n"
            f"  url_html = {{{url_html}}}\n"
            f"}}\n"
        )
    return bibtex_entry

def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("       INICIANDO BUSCA: SPRING NATURE           ")
    print("==============================================\n")
    
    out_dir = os.path.join(path_data, "spring_nature")
    if os.path.exists(out_dir):
        import shutil
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    global records_agregados
    erro_ocorrido = False

    print("Iniciando a coleta dos registros da API Springer Nature...\n")

    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE else 0)
    print(f"Será necessário realizar até {num_requisicoes} requisições (p={PAGE_SIZE}).\n")

    for i in range(num_requisicoes):
        start = 1 + i * PAGE_SIZE
        params = {
            'api_key': API_KEY,
            'q': query,
            's': start,
            'p': PAGE_SIZE
        }

        url_debug = requests.Request('GET', BASE_URL, params=params).prepare().url
        print(f"Requisição {i+1} iniciada para resultados a partir do registro {start}:")
        print(f"URL: {url_debug}\n")

        try:
            response = requests.get(BASE_URL, params=params)
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

            records = data.get('records', [])
            if not records:
                print("Nenhum registro retornado nesta página. Encerrando a coleta.\n")
                break

            records_agregados.extend(records)
            print(f"{len(records)} registros recebidos. Total acumulado: {len(records_agregados)}\n")

            if len(records) < PAGE_SIZE:
                print("Menos registros retornados que o esperado para a página. Finalizando a coleta.\n")
                break
        else:
            print(f"Erro na requisição: código de status {response.status_code}.")
            try:
                error_info = response.json()
                print(json.dumps(error_info, indent=4, ensure_ascii=False))
            except Exception:
                print(response.text)
            erro_ocorrido = True
            break

    if erro_ocorrido or not records_agregados:
        print("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
        sys.exit(1)

    try:
        with open(os.path.join(out_dir, "springer.json"), "w", encoding="utf-8") as f_json:
            json.dump(records_agregados, f_json, ensure_ascii=False, indent=4)
        print("Todos os resultados brutos salvos em 'springer.json'\n")
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        sys.exit(1)

    registros_filtrados = [rec for rec in records_agregados if rec.get('contentType', '') in ["Article", "Chapter ConferencePaper"]]
    print(f"Após filtragem, foram mantidos {len(registros_filtrados)} registros dos tipos desejados.\n")

    if not registros_filtrados:
        print("Nenhum registro do tipo desejado foi encontrado após a filtragem. Nenhum arquivo será salvo.")
        sys.exit(1)

    bibtex_entries = [converte_para_bibtex(record) for record in registros_filtrados]

    try:
        with open(os.path.join(out_dir, "springer.bib"), "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Resultados convertidos para BibTeX salvos em 'springer.bib'")
    except Exception as e:
        print(f"Erro ao salvar o arquivo BibTeX: {e}")
        sys.exit(1)

    total = len(records_agregados)
    # Log final
    print("\n==============================================")
    print("     BUSCA FINALIZADA: SPRING NATURE            ")
    print(f"      Artigos encontros e adicionados: {total}")
    print("==============================================\n")

if __name__ == "__main__":
    import sys
    QUERY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEARCH_QUERY", "")
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATH_DATA", "../Sandbox/Data")
    main(QUERY, PATH_DATA)