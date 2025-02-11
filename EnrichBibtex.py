import requests
import json
import os
from dotenv import load_dotenv
import glob
import yaml
from BibTex import read_bibtex, write_bibtex

load_dotenv()

def filter_candidates(candidates, dict_val, get_year_fn, get_authors_fn):
    # Se houver somente 1 candidato, retorna-o
    if len(candidates) == 1:
        return candidates[0]
    # Tenta filtrar por ano
    candidates_year = [c for c in candidates if get_year_fn(c) == dict_val['year']]
    if len(candidates_year) == 1:
        return candidates_year[0]
    # Se nenhum ou mais de um candidato for encontrado por ano, filtra por autores
    candidates_to_filter = candidates_year if candidates_year else candidates
    desired_authors = [a.strip() for a in dict_val['authors'].split("and")]
    best_candidate = None
    best_match_count = -1
    for c in candidates_to_filter:
        candidate_authors = get_authors_fn(c)
        match_count = sum(1 for auth in desired_authors if auth in candidate_authors)
        if match_count > best_match_count:
            best_match_count = match_count
            best_candidate = c
    return best_candidate


def get_doi_by_title_in_openalex(dict_val):
    url = "https://api.openalex.org/works"
    params = {
        "search": f'"{dict_val['title']}"',
        "filter": "has_doi:true",  # Filtra apenas resultados com DOI
        # Atualizado: removido "author" e incluído "authorships"
        "select": "doi,title,authorships,publication_year",  
        "per-page": 10  # Tenta trazer mais opções para filtragem
    }
    
    try:
        response = requests.get(url, params=params, headers={'User-Agent': 'SeuApp/1.0'})
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                candidate = filter_candidates(
                    results,
                    dict_val,
                    get_year_fn=lambda item: item.get("publication_year"),
                    # Extrai os nomes dos autores do campo "authorships"
                    get_authors_fn=lambda item: " and ".join(
                        [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
                    )
                )
                doi = candidate.get("doi") if candidate else None
                if doi:
                    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                    doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
                return doi
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None


def get_doi_by_title_in_unpaywall(dict_val, email):
    url = "https://api.unpaywall.org/v2/search"
    params = {
        "query": f'"{dict_val['title']}"',
        "email": email,
        "rows": 10  
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                candidate = filter_candidates(
                    results,
                    dict_val,
                    get_year_fn=lambda item: item.get("response", {}).get("year"),
                    get_authors_fn=lambda item: item.get("response", {}).get("author", "")
                )
                doi = None
                if candidate and "response" in candidate:
                    doi = candidate["response"].get("doi")
                    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                    doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
                return doi
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None


def get_doi_by_title_in_crossref(dict_val):
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": f'"{dict_val['title']}"',
        "rows": 10,  # Tenta trazer mais opções
        "select": "DOI,title,issued,author"  # Campos retornados
    }
    
    try:
        response = requests.get(url, params=params, headers={'User-Agent': 'SeuApp/1.0'})
        if response.status_code == 200:
            items = response.json().get("message", {}).get("items", [])
            if items:
                candidate = filter_candidates(
                    items,
                    dict_val,
                    get_year_fn=lambda item: item.get("issued", {}).get("date-parts", [[None]])[0][0],
                    get_authors_fn=lambda item: " and ".join(
                        [f"{a.get('family','')}, {a.get('given','')}" for a in item.get("author", [])]
                    ) if item.get("author") else ""
                )
                doi = candidate.get("DOI") if candidate else None
                if doi:
                    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                    doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
                return doi
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None


def enrich_bibtex_dois(email="leandroimail@gmail.com"):
    """
    Atualiza os registros BibTeX que não possuem DOI.
    Para cada base habilitada em search_config.yaml, procura os arquivos .bib
    no diretório definido pela variável de ambiente PATH_DATA. Para cada registro
    sem DOI, utiliza os campos 'title', 'authors' (ou 'author') e 'year' para buscar
    o DOI, utilizando as funções get_doi_by_title_in_unpaywall, get_doi_by_title_in_crossref e
    get_doi_by_title_in_openalex (nessa ordem). Caso um DOI seja encontrado, o registro é atualizado
    e o arquivo BibTeX é salvo.
    """
    # Obtém o caminho base dos arquivos BibTeX a partir da variável de ambiente PATH_DATA
    path_data = os.environ.get("PATH_DATA")
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return

    # Monta o caminho para o arquivo de configuração search_config.yaml
    config_path = os.path.join(
        os.path.dirname(__file__),
        "SeachDataBases",
        "config",
        "search_config.yaml"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao ler o arquivo de configuração: {e}")
        return

    # Para cada base habilitada na configuração
    for base, enabled in search_config.items():
        if enabled:
            base_path = os.path.join(path_data, base)
            if not os.path.isdir(base_path):
                print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                continue

            # Procura recursivamente por arquivos .bib no diretório da base
            bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
            for bib_file in bib_files:
                print(f"Processando arquivo: {bib_file}")
                entries = read_bibtex(bib_file)
                updated = False

                # Verifica cada registro para atualizar o DOI se necessário
                for entry in entries:
                    doi = entry.get("doi", "").strip()
                    if not doi:
                        # Utiliza os campos 'title', 'authors' ou 'author' e 'year' para a busca
                        search_data = {
                            "title": entry.get("title", ""),
                            "authors": entry.get("authors", entry.get("author", "")),
                            "year": entry.get("year", "")
                        }
                        new_doi = get_doi_by_title_in_unpaywall(search_data, email)
                        if not new_doi:
                            new_doi = get_doi_by_title_in_crossref(search_data)
                        if not new_doi:
                            new_doi = get_doi_by_title_in_openalex(search_data)
                        if new_doi:
                            entry["doi"] = new_doi
                            updated = True
                            print(f"DOI atualizado para '{new_doi}' no registro '{search_data.get('title')}'")
                # Se houve atualização, salva o arquivo BibTeX com os registros atualizados
                if updated:
                    write_bibtex(bib_file, entries)
                    print(f"Arquivo salvo: {bib_file}")

if __name__ == "__main__":
    enrich_bibtex_dois()




# # Dicionário de exemplos mantido
# dict_doi = {
#     "ieee": {
#         "title": "In Situ Neural Relational Schema Matcher",
#         "authors": "Du, Xingyu e Yuan, Gongsheng e Wu, Sai e Chen, Gang e Lu, Peng",
#         "year": 2024
#     }, 
#     "acm": {
#         "title": "Lingua manga: A generic large language model centric system for data curation",
#         "authors": "Chen, Zui e Cao, Lei e Madden, Sam",
#         "year": 2023
#     },
#     "scopus": {
#         "title": "Semantic-similarity-based schema matching for management of building energy data",
#         "authors": "Pan, Zhiyu, Guanchen Pan, e Antonello Monti",
#         "year": 2022
#     }, 
#     "springer": {
#         "authors": "Rinaldi, Antonio Maria e Russo, Cristiano e Tommasino, Cristian",
#         "title": "A semantic approach for cultural heritage ontology matching and integration based on textual and multimedia information",
#         "year": 2025
#     },
#     "science_direct": {
#         "authors": "Hodorog, Andrei e Petri, Ioan e Rezgui, Yacine",
#         "title": "Machine learning and Natural Language Processing of social media data for event detection in smart cities",
#         "year": 2022,
#     },
#     "web_of_science": {
#         "authors": "Du, Xiaokun e Zhu, Rongbo e Li, Yanhong e Anjum, Ashiq",
#         "title": "Language model-based automatic prefix abbreviation expansion method for biomedical big data analysis",
#         "year": 2019
#     }
# }





# # Loop de teste para testar a função para cada doi
# for key, dict_doi_values in dict_doi.items():
#     print("Iniciando a busca...\n")
#     print("Resultado da busca:")
#     doi_open_alx = get_doi_by_title_in_openalex(dict_doi_values)
#     doi_unpaywall = get_doi_by_title_in_unpaywall(dict_doi_values, email="leandroimail@gmail.com")
#     doi_crossref = get_doi_by_title_in_crossref(dict_doi_values)
    
#     if doi_open_alx:
#         print(f"DOI encontrado no OpenAlex: {doi_open_alx}")
#     else:
#         print("DOI não encontrado no OpenAlex.")
#     if doi_unpaywall:
#         print(f"DOI encontrado no Unpaywall: {doi_unpaywall}")
#     else:
#         print("DOI não encontrado no Unpaywall.")
#     if doi_crossref:
#         print(f"DOI encontrado no Crossref: {doi_crossref}")
#     else:
#         print("DOI não encontrado no Crossref.")