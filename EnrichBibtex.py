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


def get_doi_by_title_from_openalex(dict_val):
    url = "https://api.openalex.org/works"
    params = {
        "search": f'"{dict_val['title']}"',
        "filter": "has_doi:true",  # Filtra apenas resultados com DOI
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


def get_doi_by_title_from_unpaywall(dict_val, email):
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


def get_doi_by_title_from_crossref(dict_val):
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": f'"{dict_val['title']}"',
        "rows": 10,  # Tenta trazer mais opções
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
    o DOI.
    """
    path_data = os.environ.get("PATH_DATA")
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return

    try:
        with open(os.path.join(os.path.dirname(__file__), "config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao ler o arquivo de configuração: {e}")
        return

    for base, enabled in search_config.items():
        if enabled:
            base_path = os.path.join(path_data, base)
            if not os.path.isdir(base_path):
                print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                continue

            bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
            for bib_file in bib_files:
                print(f"\nProcessando arquivo: {bib_file}")
                entries = read_bibtex(bib_file)
                updated_file = False

                for entry in entries:
                    title = entry.get("title", "Título não disponível")
                    doi = entry.get("doi", "").strip()
                    # Apenas tenta enriquecer se não houver DOI
                    if not doi:
                        print(f"Registro '{title}': Sem DOI, iniciando enriquecimento.")
                        search_data = {
                            "title": entry.get("title", ""),
                            "authors": entry.get("authors", entry.get("author", "")),
                            "year": entry.get("year", "")
                        }
                        new_doi = get_doi_by_title_from_unpaywall(search_data, email)
                        if new_doi:
                            print(f"Registro '{title}': DOI enriquecido via Unpaywall -> {new_doi}\n")
                        else:
                            new_doi = get_doi_by_title_from_crossref(search_data)
                            if new_doi:
                                print(f"Registro '{title}': DOI enriquecido via Crossref -> {new_doi}\n")
                            else:
                                new_doi = get_doi_by_title_from_openalex(search_data)
                                if new_doi:
                                    print(f"Registro '{title}': DOI enriquecido via OpenAlex -> {new_doi}\n")
                                else:
                                    print(f"Registro '{title}': Não foi possível enriquecer o DOI. \n")
                        if new_doi:
                            entry["doi"] = new_doi
                            updated_file = True

                if updated_file:
                    write_bibtex(bib_file, entries)
                    print(f"Arquivo salvo: {bib_file}")
                else:
                    print(f"Arquivo {bib_file} não sofreu alterações no DOI.")


def get_abstract_by_doi_from_openalex(doi: str) -> str:
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        abstract_inverted_index = data.get("abstract_inverted_index", {})
        if not abstract_inverted_index:
            return ""
        abstract = " ".join(abstract_inverted_index.keys()).strip()
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do OpenAlex: {e}")
        return ""

def get_abstract_by_doi_from_semanticscholar(doi: str) -> str:
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    try:
        url = f"https://api.semanticscholar.org/v1/paper/{doi}"
        response = requests.get(url).json()
        abstract = response.get("abstract", "")
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Semantic Scholar: {e}")
        return ""

def get_abstract_by_doi_from_crossref(doi: str) -> str:
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    try:
        url = f"https://api.crossref.org/works/{doi}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        abstract = data.get("message", {}).get("abstract", "")
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Crossref: {e}")
        return ""

def get_abstract_by_doi_from_scopus(doi: str) -> str:
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("SCOPUS_API_KEY não definida.")
        return ""
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Extrai o abstract do campo indicado pela API
        abstract = data.get("dc:description", "")
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Scopus: {e}")
        return ""

def enrich_bibtex_abstract():
    """
    Atualiza os registros BibTeX que não possuem abstract.
    Para cada base habilitada em search_config.yaml, procura os arquivos .bib
    no diretório definido pela variável de ambiente PATH_DATA. Para cada registro
    com DOI mas sem abstract, utiliza o DOI para buscar o abstract nas APIs do
    Crossref, Semantic Scholar, Scopus e OpenAlex (nessa ordem).
    """
    path_data = os.environ.get("PATH_DATA")
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return

    try:
        with open(os.path.join(os.path.dirname(__file__), "config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao ler o arquivo de configuração: {e}")
        return

    for base, enabled in search_config.items():
        if enabled:
            base_path = os.path.join(path_data, base)
            if not os.path.isdir(base_path):
                print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                continue

            bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
            for bib_file in bib_files:
                print(f"\nProcessando arquivo: {bib_file}")
                entries = read_bibtex(bib_file)
                updated_file = False

                for entry in entries:
                    title = entry.get("title", "Título não disponível")
                    abstract = entry.get("abstract", "")
                    doi = entry.get("doi", "").strip()
                    # Apenas tenta enriquecer se abstract não existir
                    if not abstract:
                        if not doi:
                            print(f"Registro '{title}': Sem DOI, impossível enriquecer abstract. \n")
                        else:
                            print(f"Registro '{title}': Iniciando enriquecimento do abstract para DOI '{doi}'.")
                            abstract_new = get_abstract_by_doi_from_crossref(doi)
                            if abstract_new:
                                print(f"Registro '{title}': Abstract enriquecido via Crossref. \n")
                            else:
                                abstract_new = get_abstract_by_doi_from_semanticscholar(doi)
                                if abstract_new:
                                    print(f"Registro '{title}': Abstract enriquecido via Semantic Scholar. \n")
                                else:
                                    abstract_new = get_abstract_by_doi_from_scopus(doi)
                                    if abstract_new:
                                        print(f"Registro '{title}': Abstract enriquecido via Scopus. \n")
                                    else:
                                        abstract_new = get_abstract_by_doi_from_openalex(doi)
                                        if abstract_new:
                                            print(f"Registro '{title}': Abstract enriquecido via OpenAlex. \n")
                                        else:
                                            print(f"Registro '{title}': Não foi possível enriquecer o abstract. \n")
                            if abstract_new:
                                entry["abstract"] = abstract_new
                                updated_file = True

                if updated_file:
                    write_bibtex(bib_file, entries)
                    print(f"Arquivo salvo: {bib_file}")
                else:
                    print(f"Arquivo {bib_file} não sofreu alterações no abstract.")



def get_keywords_by_doi_from_openalex(doi: str) -> dict:
    """
    Retorna as keywords a partir do OpenAlex.

    Mapeamentos:
    - author_keywords: mapeado de response["keywords"], extraindo o campo "display_name".
    - keywords: mapeado de response["concepts"], ordenando por score decrescente e selecionando os 10 primeiros.
    """
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Extração de author_keywords a partir de "keywords"
        openalex_keywords = data.get("keywords", [])
        author_keywords = ", ".join(
            [kw.get("display_name", "") for kw in openalex_keywords if kw.get("display_name", "")]
        )

        # Extração de keywords a partir de "concepts" (apenas os 10 com maiores score)
        concepts = data.get("concepts", [])
        sorted_concepts = sorted(concepts, key=lambda c: c.get("score", 0), reverse=True)
        top_concepts = sorted_concepts[:10]
        keywords = ", ".join(
            [c.get("display_name", "") for c in top_concepts if c.get("display_name", "")]
        )

        return {"author_keywords": author_keywords, "keywords": keywords}
    except Exception as e:
        print(f"Erro ao obter keywords do OpenAlex: {e}")
        return {"author_keywords": "", "keywords": ""}


def get_keywords_by_doi_from_crossref(doi: str) -> dict:
    """
    Retorna keywords do Crossref, utilizando o campo "subject"
    que normalmente contém os conceitos, assuntos ou áreas da pesquisa.
    """
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    url = f"https://api.crossref.org/works/{doi}"
    try:
        response = requests.get(url, headers={'User-Agent': 'SeuApp/1.0'})
        if response.status_code == 200:
            data = response.json().get("message", {})
            subjects = data.get("subject", [])
            if subjects and isinstance(subjects, list):
                pub_kw = ", ".join(subjects)
            else:
                pub_kw = ""
            return {"author_keywords": "", "keywords": pub_kw}
        return {"author_keywords": "", "keywords": ""}
    except Exception as e:
        print(f"Erro ao obter keywords do Crossref: {e}")
        return {"author_keywords": "", "keywords": ""}


def get_keywords_by_doi_from_scopus(doi: str) -> dict:
    """
    Retorna as keywords a partir do Scopus.

    Mapeamentos:
    - author_keywords: de response["authkeywords"]["author-keyword"], extraindo o valor em "$".
    - keywords: de response["idxterms"]["mainterm"], extraindo o valor em "$" dos termos cujo score (se informado) seja > 0.10.
    """
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("SCOPUS_API_KEY não definida.")
        return {"author_keywords": "", "keywords": ""}
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Extração de author_keywords
        auth_keywords = ""
        if "authkeywords" in data:
            ak = data["authkeywords"].get("author-keyword", [])
            if isinstance(ak, list):
                auth_keywords = ", ".join([item.get("$", "") for item in ak if item.get("$", "")])
            elif isinstance(ak, dict):
                auth_keywords = ak.get("$", "")

        # Extração de keywords a partir de idxterms.mainterm
        keywords = ""
        if "idxterms" in data:
            main_terms = data["idxterms"].get("mainterm", [])
            terms_list = []
            if isinstance(main_terms, list):
                for term in main_terms:
                    # Se existir um campo "score", utiliza-o para filtrar; caso contrário, inclui o termo
                    score = term.get("score")
                    if score is None or float(score) > 0.10:
                        term_text = term.get("$", "")
                        if term_text:
                            terms_list.append(term_text)
            elif isinstance(main_terms, dict):
                score = main_terms.get("score")
                if score is None or float(score) > 0.10:
                    term_text = main_terms.get("$", "")
                    if term_text:
                        terms_list.append(term_text)
            keywords = ", ".join(terms_list)

        return {"author_keywords": auth_keywords, "keywords": keywords}
    except Exception as e:
        print(f"Erro ao obter keywords do Scopus: {e}")
        return {"author_keywords": "", "keywords": ""}


def enrich_bibtex_keywords(email="leandroimail@gmail.com"):
    """
    Atualiza os registros BibTeX que não possuem author_keywords preenchidas.

    - Se o registro não possui author_keywords e keywords também, ambos serão enriquecidos.
    - Se o registro não possui author_keywords mas já possui keywords preenchidas, apenas author_keywords será enriquecido e keywords não será sobrescrito.
    """
    path_data = os.environ.get("PATH_DATA")
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return

    try:
        with open(os.path.join(os.path.dirname(__file__), "config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao ler o arquivo de configuração: {e}")
        return

    for base, enabled in search_config.items():
        if enabled:
            base_path = os.path.join(path_data, base)
            if not os.path.isdir(base_path):
                print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                continue

            bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
            for bib_file in bib_files:
                print(f"\nProcessando arquivo: {bib_file}")
                entries = read_bibtex(bib_file)
                updated_file = False

                for entry in entries:
                    title = entry.get("title", "Título não disponível")
                    doi = entry.get("doi", "").strip()

                    if not doi:
                        print(f"Registro '{title}': Sem DOI, impossível enriquecer keywords.\n")
                        continue

                    # Apenas enriquece se author_keywords estiver vazio
                    if entry.get("author_keywords"):
                        print(f"Registro '{title}': author_keywords já preenchido, pulando enriquecimento.")
                        continue

                    print(f"Registro '{title}': Iniciando enriquecimento para DOI '{doi}'.")
                    # Remoção de prefixos do DOI
                    doi_tratado = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()

                    # Primeiro tenta via OpenAlex
                    res = get_keywords_by_doi_from_openalex(doi_tratado)
                    result = {"author_keywords": "", "keywords": ""}
                    if res["author_keywords"]:
                        result["author_keywords"] = res["author_keywords"]
                    if res["keywords"]:
                        result["keywords"] = res["keywords"]

                    # Se necessário, tenta via Scopus
                    if not result["author_keywords"] or (not result["keywords"] and not entry.get("keywords")):
                        res_scopus = get_keywords_by_doi_from_scopus(doi_tratado)
                        if not result["author_keywords"] and res_scopus["author_keywords"]:
                            result["author_keywords"] = res_scopus["author_keywords"]
                        if not result["keywords"] and not entry.get("keywords") and res_scopus["keywords"]:
                            result["keywords"] = res_scopus["keywords"]

                    # Atualiza entry
                    if result["author_keywords"]:
                        entry["author_keywords"] = result["author_keywords"]
                        print(f"Registro '{title}': author_keywords enriquecidas.")
                        updated_file = True
                    if result["keywords"]:
                        entry["keywords"] = result["keywords"]
                        print(f"Registro '{title}': keywords enriquecidas.")
                        updated_file = True
                    if result["author_keywords"] or result["keywords"]:
                        print(f"\n")

                if updated_file:
                    write_bibtex(bib_file, entries)
                    print(f"Arquivo salvo: {bib_file}")
                else:
                    print(f"Arquivo {bib_file} não sofreu alterações nas keywords.")





if __name__ == "__main__":
    print("\n\n==============================================")
    print("EnrichBibtex DOIS Started!")
    enrich_bibtex_dois()
    
    print("\n\n==============================================")
    print("EnrichBibtex abstract  Started!")
    enrich_bibtex_abstract()
    
    print("\n\n==============================================")
    print("EnrichBibtex completed successfully!")
    print("============================================== \n\n")
    
    
    print("\n\n==============================================")
    print("EnrichBibtex keywords Started!")
    enrich_bibtex_keywords()
    
    
    
    
    
    # TODO: Verificar a busca de abstract via Scopus, ver se tá pegando certo
    # TODO: Verificar a buscas de keywords, ver se tah pegando via crossref
    # TODOS: Verificar a busca de keywords, retirar print desnecessários (keywords que já existem)