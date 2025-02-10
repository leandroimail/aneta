import requests
import json
import re
import sys
import os
import shutil
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
    # Pasta de saída para Spring Nature
    out_dir = os.path.join(path_data, "spring_nature")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    
    print("\n==============================================")
    print("      INICIANDO BUSCA: SPRING NATURE            ")
    print("==============================================\n")
    # ...lógica de busca a ser implementada...
    print("Busca Spring Nature não implementada.")
    
if __name__ == "__main__":
    import sys
    QUERY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEARCH_QUERY", "")
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATH_DATA", "/Users/leandro.ferreira/Library/CloudStorage/OneDrive-Pessoal/Projects/python/asrl/Sandbox/Data")
    main(QUERY, PATH_DATA)
