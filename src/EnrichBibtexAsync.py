import os
import glob
import re
import yaml
import asyncio
import aiohttp
import pandas as pd
from dotenv import load_dotenv
from src.BibTex import read_bibtex, write_bibtex
from src.Database import create_lancedb_instance, save_bibliographic_database, fetch_bibliographic_database
from typing import List, Dict, Any, Optional, Tuple

load_dotenv()
load_dotenv(os.path.abspath("Config/.env"))

db = create_lancedb_instance()
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

# Configuração global para controlar concorrência
MAX_CONCURRENT_REQUESTS = 10  # Ajuste conforme necessário
REQUEST_SEMAPHORE = None  # Será inicializado antes do uso


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


async def get_doi_by_title_from_scopus(session, dict_val) -> str:
    """
    Busca o DOI de um artigo no Scopus usando o título.
    Requer que a variável de ambiente ELSEVIER_API_KEY esteja definida.
    """
    global REQUEST_SEMAPHORE
    
    title = dict_val['title'].strip().strip('"').strip("'").strip(".")
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("ELSEVIER_API_KEY não definida.")
        return ""
    url = "https://api.elsevier.com/content/search/scopus"
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": scopus_api_key
    }
    headers = {**headers, **HEADERS}
    params = {
        "query": f"TITLE({title})"
    }
    
    try:
        async with REQUEST_SEMAPHORE:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 404:
                    return ""
                response.raise_for_status()
                data = await response.json()
                entries = data.get("search-results", {}).get("entry", [])
                if not entries:
                    return ""
                # Seleciona o primeiro resultado e extrai o DOI
                doi = entries[0].get("prism:doi", "")
                if doi:
                    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                    doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
                return doi
    except Exception as e:
        print(f"Erro ao buscar DOI pelo título no Scopus: {e}")
        return ""


async def get_doi_by_title_from_openalex(session, dict_val):
    global REQUEST_SEMAPHORE
    
    url = "https://api.openalex.org/works"
    params = {
        "search": f'"{dict_val["title"].strip().strip('"').strip("\'").strip(".")}"',
        "filter": "has_doi:true",  # Filtra apenas resultados com DOI
        "per-page": 10  # Tenta trazer mais opções para filtragem
    }
    headers = HEADERS.copy()
    
    try:
        async with REQUEST_SEMAPHORE:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 404:
                    return None
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
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


async def get_doi_by_title_from_unpaywall(session, dict_val, email):
    global REQUEST_SEMAPHORE
    
    url = "https://api.unpaywall.org/v2/search"
    params = {
        "query": f'"{dict_val["title"].strip().strip('"').strip("\'").strip(".")}"',
        "email": email,
        "rows": 10  
    }
    headers = HEADERS.copy()
    
    try:
        async with REQUEST_SEMAPHORE:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 404:
                    return None
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
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
                            if doi:
                                doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                                doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
                        return doi
        return None
    except Exception as e:
        print(f"Erro: {e}")
        return None


async def get_doi_by_title_from_crossref(session, dict_val):
    global REQUEST_SEMAPHORE
    
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": f'"{dict_val["title"].strip().strip('"').strip("\'").strip(".")}"',
        "rows": 10,  # Tenta trazer mais opções
    }
    headers = HEADERS.copy()
    
    try:
        async with REQUEST_SEMAPHORE:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 404:
                    return None
                if response.status == 200:
                    data = await response.json()
                    items = data.get("message", {}).get("items", [])
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


async def get_doi_by_title_from_datacite(session, dict_val) -> str:
    """
    Busca o DOI de um artigo no DataCite usando o título.
    """
    global REQUEST_SEMAPHORE
    
    title = dict_val['title'].strip().strip('"').strip("'").strip(".")
    url = "https://api.datacite.org/dois"
    
    params = {
        "query": f"titles.title:({title})"
    }
    headers = HEADERS.copy()
    
    try:
        async with REQUEST_SEMAPHORE:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 404:
                    return ""
                response.raise_for_status()
                data = await response.json()
                
                # Verifica se há resultados
                items = data.get("data", [])
                if not items:
                    return ""
                
                if len(items) == 1:
                    doi = items[0].get("attributes", {}).get("doi", "")
                    return doi.strip()
                
                # Filtra os candidatos usando a função existente
                def get_year(item):
                    return item.get("attributes", {}).get("publicationYear")
                    
                def get_authors(item):
                    creators = item.get("attributes", {}).get("creators", [])
                    return [f"{c.get('givenName', '')} {c.get('familyName', '')}".strip() 
                            for c in creators]
                
                best_match = filter_candidates(items, dict_val, get_year, get_authors)
                
                if best_match:
                    doi = best_match.get("attributes", {}).get("doi", "")
                    return doi.strip()
                    
                return ""
    except Exception as e:
        print(f"Erro ao buscar DOI pelo título no DataCite: {e}")
        return ""


async def fetch_db_data(type_source, doi):
    """Função assíncrona para buscar dados no banco de dados LanceDB"""
    try:
        # Como o LanceDB não é assíncrono nativo, usamos loop.run_in_executor
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_bibliographic_database, type_source, doi, db)
        return data
    except Exception as e:
        print(f"Erro ao buscar registro no banco de dados: {e}")
        return None


async def save_db_data(type_source, doi, data):
    """Função assíncrona para salvar dados no banco de dados LanceDB"""
    try:
        # Como o LanceDB não é assíncrono nativo, usamos loop.run_in_executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, save_bibliographic_database, type_source, doi, data, db)
    except Exception as e:
        print(f"Erro ao salvar registro no banco de dados: {e}")


async def enrich_doi_for_entry(session, entry, email):
    """Processa um único registro para enriquecimento de DOI"""
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
        
        # Tentar buscar em todas as fontes de forma paralela
        tasks = [
            get_doi_by_title_from_unpaywall(session, search_data, email),
            get_doi_by_title_from_crossref(session, search_data),
            get_doi_by_title_from_openalex(session, search_data),
            get_doi_by_title_from_datacite(session, search_data),
            get_doi_by_title_from_scopus(session, search_data)
        ]
        
        # Executa todas as tarefas em paralelo e pega o primeiro resultado válido
        results = await asyncio.gather(*tasks)
        sources = ["Unpaywall", "Crossref", "OpenAlex", "DataCite", "Scopus"]
        
        new_doi = None
        source_name = None
        
        for i, result in enumerate(results):
            if result:
                new_doi = result
                source_name = sources[i]
                break
                
        if new_doi:
            print(f"Registro '{title}': DOI enriquecido via {source_name} -> {new_doi}\n")
            entry["doi"] = new_doi
            return True
        else:
            print(f"Registro '{title}': Não foi possível enriquecer o DOI. \n")
            return False
    
    return False


async def get_abstract_by_doi_from_openalex(session, doi: str) -> str:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = HEADERS.copy()
    
    try:
        type_source = "openalex"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return ""
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
        abstract_inverted_index = data.get("abstract_inverted_index", {})
        if not abstract_inverted_index:
            return ""
        abstract = " ".join(abstract_inverted_index.keys()).strip()
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do OpenAlex: {e}")
        return ""


async def get_abstract_by_doi_from_semanticscholar(session, doi: str) -> str:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    try:
        type_source = "semanticscholar"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            url = f"https://api.semanticscholar.org/v1/paper/{doi}"
            async with REQUEST_SEMAPHORE:
                async with session.get(url) as response:
                    if response.status == 404:
                        return ""
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
        abstract = data.get("abstract", "")
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Semantic Scholar: {e}")
        return ""


async def get_abstract_by_doi_from_crossref(session, doi: str) -> str:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    try:
        type_source = "crossref"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            url = f"https://api.crossref.org/works/{doi}"
            headers = HEADERS.copy()
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return ""
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
        abstract = data.get("message", {}).get("abstract", "")
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Crossref: {e}")
        return ""


async def get_abstract_by_doi_from_scopus(session, doi: str) -> str:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        doi = doi.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("SCOPUS_API_KEY não definida.")
        return ""
    
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    headers = {**headers, **HEADERS}
    
    try:
        type_source = "scopus"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return ""
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
        abstract = data.get("abstracts-retrieval-response", {}).get("coredata", {}).get("dc:description", "")
        if abstract:
            return abstract
        
        abstract = data.get("abstracts-retrieval-response", {}).get("bibrecord", {}).get("head", {}).get("abstracts", "") 
        return abstract
    except Exception as e:
        print(f"Erro ao obter abstract do Scopus: {e}")
        return ""


async def enrich_abstract_for_entry(session, entry):
    """Processa um único registro para enriquecimento de abstract"""
    title = entry.get("title", "Título não disponível")
    abstract = entry.get("abstract", "")
    doi = entry.get("doi", "").strip()
    
    # Apenas tenta enriquecer se abstract não existir
    if not abstract:
        if not doi:
            print(f"Registro '{title}': Sem DOI, impossível enriquecer abstract. \n")
            return False
        else:
            print(f"Registro '{title}': Iniciando enriquecimento do abstract para DOI '{doi}'.")
            
            # Tentar buscar em todas as fontes de forma paralela
            tasks = [
                get_abstract_by_doi_from_crossref(session, doi),
                get_abstract_by_doi_from_semanticscholar(session, doi),
                get_abstract_by_doi_from_scopus(session, doi),
                get_abstract_by_doi_from_openalex(session, doi)
            ]
            
            # Executa todas as tarefas em paralelo e pega o primeiro resultado válido
            results = await asyncio.gather(*tasks)
            sources = ["Crossref", "Semantic Scholar", "Scopus", "OpenAlex"]
            
            abstract_new = None
            source_name = None
            
            for i, result in enumerate(results):
                if result:
                    abstract_new = result
                    source_name = sources[i]
                    break
                    
            if abstract_new:
                print(f"Registro '{title}': Abstract enriquecido via {source_name}. \n")
                entry["abstract"] = abstract_new
                return True
            else:
                print(f"Registro '{title}': Não foi possível enriquecer o abstract. \n")
                return False
    
    return False


async def get_keywords_by_doi_from_openalex(session, doi: str) -> dict:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = HEADERS.copy()
    
    try:
        type_source = "openalex"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return {"author_keywords": "", "keywords": ""}
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
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


async def get_keywords_by_doi_from_crossref(session, doi: str) -> dict:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    
    url = f"https://api.crossref.org/works/{doi}"
    headers = HEADERS.copy()
    
    try:
        type_source = "crossref"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return {"author_keywords": "", "keywords": ""}
                    response.raise_for_status()
                    data_response = await response.json()
                    data = data_response.get("message", {})
                    if data:
                        await save_db_data(type_source, doi, data)
        
        subjects = data.get("subject", [])
        if subjects and isinstance(subjects, list):
            pub_kw = ", ".join(subjects)
        else:
            pub_kw = ""
            
        return {"author_keywords": "", "keywords": pub_kw}
    except Exception as e:
        print(f"Erro ao obter keywords do Crossref: {e}")
        return {"author_keywords": "", "keywords": ""}


async def get_keywords_by_doi_from_scopus(session, doi: str) -> dict:
    global REQUEST_SEMAPHORE
    
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("SCOPUS_API_KEY não definida.")
        return {"author_keywords": "", "keywords": ""}
    
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    headers = {**headers, **HEADERS}
    
    try:
        type_source = "scopus"
        data = await fetch_db_data(type_source, doi)
        
        if not data:
            async with REQUEST_SEMAPHORE:
                async with session.get(url, headers=headers) as response:
                    if response.status == 404:
                        return {"author_keywords": "", "keywords": ""}
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await save_db_data(type_source, doi, data)
        
        root = data.get("abstracts-retrieval-response", {})
        
        # Extração de author_keywords
        auth_keywords = ""
        ak = root.get("authkeywords", {})
        if ak is None:
            ak = []
        elif not isinstance(ak, dict):
            ak = ak.get("author-keyword", [])
        if isinstance(ak, list):
            auth_keywords = ", ".join([item.get("$", "") for item in ak if item.get("$", {})])
        elif isinstance(ak, dict):
            auth_keywords = ak.get("$", "")
            
        # Extração de keywords a partir de idxterms.mainterm
        keywords = ""
        mt = root.get("idxterms", {})
        if mt is None:
            mt = []
        elif not isinstance(mt, dict):
            mt = mt.get("mainterm", [])
        terms_list = []
        if isinstance(mt, list):
            for term in mt:
                score = term.get("score")
                if score is None or float(score) > 0.10:
                    term_text = ""
                    if isinstance(term, dict):                    
                        term_text = term.get("$", "")
                    elif isinstance(term, str):
                        term_text = term
                    if term_text:
                        terms_list.append(term_text)
        elif isinstance(mt, dict):
            score = mt.get("score")
            if score is None or float(score) > 0.10:
                term_text = ""
                if isinstance(mt, dict):
                    term_text = mt.get("$", "")
                elif isinstance(mt, str):
                    term_text = mt
                if term_text:
                    terms_list.append(term_text)
        keywords = ", ".join(terms_list)

        return {"author_keywords": auth_keywords, "keywords": keywords}
    except Exception as e:
        print(f"Erro ao obter keywords do Scopus: {e}")
        return {"author_keywords": "", "keywords": ""}


async def enrich_keywords_for_entry(session, entry):
    """Processa um único registro para enriquecimento de keywords"""
    title = entry.get("title", "Título não disponível")
    doi = entry.get("doi", "").strip()
    
    result = {
        "author_keywords": entry.get("author_keywords", "").strip(), 
        "keywords": entry.get("keywords", "").strip()
    }    

    # Verifica se precisa enriquecer
    if not doi:
        print(f"Registro '{title}': Sem DOI, impossível enriquecer keywords.\n")
        return False
    if entry.get("author_keywords"):
        return False

    print(f"Registro '{title}': Iniciando enriquecimento para DOI '{doi}'.")
    doi_tratado = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()

    res_keywords_enrich = await get_keywords_by_doi_from_openalex(session, doi_tratado)
    if res_keywords_enrich.get("author_keywords"):
        result["author_keywords"] = res_keywords_enrich.get("author_keywords")
        print(f"Registro '{title}': author_keywords enriquecidas via OpenAlex.")
    if res_keywords_enrich.get("keywords"):
        result["keywords"] = res_keywords_enrich.get("keywords")
        print(f"Registro '{title}': keywords enriquecidas via OpenAlex.")
    
    if not result.get("author_keywords") or not result.get("keywords"):
        res_keywords_enrich = await get_keywords_by_doi_from_scopus(session, doi_tratado)
        if not result.get("author_keywords") and res_keywords_enrich.get("author_keywords"):
            result["author_keywords"] = res_keywords_enrich.get("author_keywords")
            print(f"Registro '{title}': author_keywords enriquecidas via Scopus.")
        if not result.get("keywords") and res_keywords_enrich.get("keywords"):
            result["keywords"] = res_keywords_enrich.get("keywords")
            print(f"Registro '{title}': keywords enriquecidas via Scopus.")
    
    if result.get("author_keywords"):
        entry["author_keywords"] = result.get("author_keywords")
    if result.get("keywords"):
        entry["keywords"] = result.get("keywords")
    if res_keywords_enrich.get("author_keywords") or res_keywords_enrich.get("keywords"):
        print(f"\n")
    
    if not res_keywords_enrich.get("author_keywords"):
        print(f"Registro '{title}': Não foi possível enriquecer author_keywords.") 
    if not res_keywords_enrich.get("keywords"):
        print(f"Registro '{title}': Não foi possível enriquecer keywords.")
    if not res_keywords_enrich.get("author_keywords") and not res_keywords_enrich.get("keywords"):
        print(f"\n")
    
    return True


async def enrich_bibtex_dois(email="leandroimail@gmail.com"):
    """
    Atualiza os registros BibTeX que não possuem DOI.
    Para cada base habilitada em search_config.yaml, procura os arquivos .bib
    no diretório definido pela variável de ambiente PATH_DATA. Para cada registro
    sem DOI, utiliza os campos 'title', 'authors' (ou 'author') e 'year' para buscar
    o DOI.
    """
    path_data = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return
    path_data = os.path.join(path_data, ".bibs")
    try:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo de configuração: {e}")
    
    async with aiohttp.ClientSession() as session:
        for base, enabled in search_config.items():
            if "arxiv" in base.lower() and os.environ.get("ENRICH_ARXIV", "False").lower() != "true":
                print(f"\n\nBase '{base}' não suportada para busca de DOIs.")
                continue
            if enabled:
                base_path = os.path.join(path_data, base)
                if not os.path.isdir(base_path):
                    print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                    continue
                bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
                for bib_file in bib_files:
                    print(f"\n\nProcessando arquivo: {bib_file}")
                    print(f"{90 * '-'}\n\n")
                    entries = read_bibtex(bib_file)
                    updated_file = False
                    tasks = [enrich_doi_for_entry(session, entry, email) for entry in entries]
                    results = await asyncio.gather(*tasks)
                    if any(results):
                        updated_file = True
                    if updated_file:
                        write_bibtex(bib_file, entries)
                        print(f"Arquivo salvo: {bib_file}")
                    else:
                        print(f"Arquivo {bib_file} não sofreu alterações no DOI. \n\n")


async def enrich_bibtex_abstract():
    """
    Atualiza os registros BibTeX que não possuem abstract.
    Para cada base habilitada em search_config.yaml, procura os arquivos .bib
    no diretório definido pela variável de ambiente PATH_DATA. Para cada registro
    com DOI mas sem abstract, utiliza o DOI para buscar o abstract nas APIs do
    Crossref, Semantic Scholar, Scopus e OpenAlex (nessa ordem).
    """
    path_data = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return
    path_data = os.path.join(path_data, ".bibs")
    
    try:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo de configuração: {e}")

    async with aiohttp.ClientSession() as session:
        for base, enabled in search_config.items():
            if "arxiv" in base.lower() and os.environ.get("ENRICH_ARXIV", "False").lower() != "true":
                print(f"\n\nBase '{base}' não suportada para busca de DOIs.")
                continue
            if enabled:
                base_path = os.path.join(path_data, base)
                if not os.path.isdir(base_path):
                    print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                    continue
                
                bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
                for bib_file in bib_files:
                    print(f"\n\nProcessando arquivo: {bib_file}")
                    print(f"{90 * '-'}\n\n")
                    entries = read_bibtex(bib_file)
                    updated_file = False
                    tasks = [enrich_abstract_for_entry(session, entry) for entry in entries]
                    results = await asyncio.gather(*tasks)
                    if any(results):
                        updated_file = True
                    if updated_file:
                        write_bibtex(bib_file, entries)
                        print(f"Arquivo salvo: {bib_file}")
                    else:
                        print(f"Arquivo {bib_file} não sofreu alterações no abstract.")


async def enrich_bibtex_keywords(email="leandroimail@gmail.com"):
    """
    Atualiza os registros BibTeX que não possuem author_keywords preenchidas.
    - Se o registro não possui author_keywords e keywords também, ambos serão enriquecidos.
    - Se o registro não possui author_keywords mas já possui keywords preenchidas, apenas author_keywords será enriquecido e keywords não será sobrescrito.
    """
    path_data = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return
    path_data = os.path.join(path_data, ".bibs")
    
    try:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo de configuração: {e}")
    
    async with aiohttp.ClientSession() as session:
        for base, enabled in search_config.items():
            if "arxiv" in base.lower() and os.environ.get("ENRICH_ARXIV", "False").lower() != "true":
                print(f"\n\nBase '{base}' não suportada para busca de DOIs.")
                continue
            if enabled:
                base_path = os.path.join(path_data, base)
                if not os.path.isdir(base_path):
                    print(f"Diretório para a base '{base}' não encontrado: {base_path}")
                    continue
                bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
                for bib_file in bib_files:
                    print(f"\n\nProcessando arquivo: {bib_file}")
                    print(f"{90 * '-'}\n\n")
                    entries = read_bibtex(bib_file)
                    updated_file = False
                    tasks = [enrich_keywords_for_entry(session, entry) for entry in entries]
                    results = await asyncio.gather(*tasks)
                    if any(results):
                        updated_file = True
                    if updated_file:
                        write_bibtex(bib_file, entries)
                        print(f"Arquivo salvo: {bib_file}")
                    else:
                        print(f"Arquivo {bib_file} não sofreu alterações nas keywords.")


def read_csv_data(path_csv):
    """Lê o CSV e aplica a função de limpeza."""
    try:
        df = pd.read_csv(path_csv)
        return df
    except Exception as e:
        print(f"Erro ao ler o CSV ({path_csv}): {e}")
        return None


def preprocess_df(df):
    """Pré-processa o DataFrame adicionando colunas com os valores já limpos."""
    if "ISSN" in df.columns:
        df["ISSN_lower"] = df["ISSN"].str.replace("-", "").str.lower()
    if "Full Journal Title" in df.columns:
        df["Full Journal Title_lower"] = (
            df["Full Journal Title"]
            .str.lower()
            .apply(lambda x: re.sub(r"[^a-z0-9 ]", " ", x))
        )
    if "Abbreviated Title" in df.columns:
        df["Abbreviated Title_lower"] = (
            df["Abbreviated Title"]
            .str.lower()
            .apply(lambda x: re.sub(r"[^a-z0-9 ]", " ", x))
        )
    return df


def get_metric_from_df(df, publication, issn, abbrev, metric_column):
    """
    Busca o valor da métrica usando as colunas pré-limpa.
    Prioriza: ISSN, Full Journal Title e Abbreviated Title.
    """
    if issn and "ISSN_lower" in df.columns:
        match = df[df["ISSN_lower"] == issn.replace("-", "").lower()]
        if not match.empty:
            return match.iloc[0].get(metric_column, None)
    
    cleaned_publication = re.sub(r"[^a-z0-9 ]", " ", publication.lower()) if publication else ""
    if publication and "Full Journal Title_lower" in df.columns:
        match = df[df["Full Journal Title_lower"] == cleaned_publication]
        if not match.empty:
            return match.iloc[0].get(metric_column, None)
    
    if abbrev and "Abbreviated Title_lower" in df.columns:
        cleaned_abbrev = re.sub(r"[^a-z0-9 ]", " ", abbrev.lower())
        match = df[df["Abbreviated Title_lower"] == cleaned_abbrev]
        if not match.empty:
            return match.iloc[0].get(metric_column, None)
    
    return None


def enrich_bibtex_file(bibtex_path, df_jcr, df_scimago, output_path):
    """
    Lê um arquivo BibTeX utilizando read_bibtex, insere os campos de JCR e Scimago
    usando os DataFrames e salva o resultado no arquivo de saída utilizando write_bibtex.
    Os campos dos BibTeX são: publication, issn e abbrev_source_title.
    
    Para o CSV do JCR, usamos a coluna "Journal Impact Factor" e para o Scimago, a coluna "Total Cites".
    Após o enriquecimento, imprime o DOI e o título do artigo, informando com qual métrica foi enriquecido.
    Caso não haja enriquecimento, insere jcr e scimago vazios.
    """
    try:
        # Lê o arquivo BibTeX e retorna um JSON (lista de dicionários)
        bib_data = read_bibtex(bibtex_path)
    except Exception as e:
        print(f"Erro ao ler o arquivo BibTeX ({bibtex_path}): {e}")
        return

    # Percorre cada entrada e insere os campos de métrica se disponíveis
    for entry in bib_data:
        
        if entry.get("jcr") or entry.get("scimago"):
            # print(f"Registro já enriquecido com JCR e Scimago. Pulando.")
            continue
        
        # Preparando dados para a mensagem informativa
        doi_val = entry.get("doi", "N/A")
        # Assume que o título do artigo esteja no campo 'title'; se não, utiliza publication
        title_val = entry.get("title", "")
        
        print(f"Enriquecendo JCR e SCIMA no artigo '{title_val}' (DOI: {doi_val})...")
        
        publication_val = entry.get("publication", "")
        issn_val = entry.get("issn", "").replace("-", "")
        abbrev_val = entry.get("abbrev_source_title", "")

        jcr_metric = get_metric_from_df(df_jcr, publication_val, issn_val, abbrev_val, "Journal Impact Factor")
        scimago_metric = get_metric_from_df(df_scimago, publication_val, issn_val, abbrev_val, "Journal Impact Factor")

        # Define os campos de enriquecimento ou insere string vazia caso não encontrado
        if jcr_metric is not None:
            entry["jcr"] = str(jcr_metric)
        else:
            entry["jcr"] = ""

        if scimago_metric is not None:
            entry["scimago"] = str(scimago_metric)
        else:
            entry["scimago"] = ""

        if entry["jcr"] or entry["scimago"]:
            print(f"Artigo '{title_val}' (DOI: {doi_val}) enriquecido com: {', '.join([str(entry["jcr"]), str(entry["scimago"])])} \n")
    try:
        # Escreve o arquivo enriquecido utilizando write_bibtex que recebe path e entries
        write_bibtex(output_path, bib_data)
        print(f"Arquivo BibTeX enriquecido salvo em: {output_path}")
    except Exception as e:
        print(f"Erro ao escrever o arquivo enriquecido ({output_path}): {e}")


def enrich_bibtex_jcr_scimago():
    """
    Percorre as bases configuradas em config/general_config.yaml (chave: nome da base, valor: booleano habilitado)
    e enriquece todos os arquivos BibTeX encontrados (no diretório definido por PATH_DATA) com os dados de JCR e Scimago.
    """
    path_data = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    if not path_data:
        print("Variável de ambiente PATH_DATA não definida.")
        return
    path_data = os.path.join(path_data, ".bibs")
    try:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            search_config = yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo de configuração: {e}")

    # Obtém os caminhos dos CSVs a partir das variáveis de ambiente
    path_jcr = os.environ.get("PATH_JCR")
    path_scimago = os.environ.get("PATH_SCIMAGO")
    if not path_jcr or not path_scimago:
        print("Erro: As variáveis de ambiente PATH_JCR e PATH_SCIMAGO precisam estar definidas.")
        return

    df_jcr = read_csv_data(path_jcr)
    df_scimago = read_csv_data(path_scimago)
    if df_jcr is None or df_scimago is None:
        print("Erro ao ler os arquivos CSV do JCR ou Scimago.")
        return

    df_jcr = preprocess_df(df_jcr)
    df_scimago = preprocess_df(df_scimago)
    
    # Itera sobre as bases configuradas
    for base, enabled in search_config.items():
        if not enabled:
            print(f"Base '{base}' desabilitada. Pulando.")
            continue

        base_path = os.path.join(path_data, base)
        if not os.path.isdir(base_path):
            print(f"Diretório para a base '{base}' não encontrado: {base_path}")
            continue

        # Procura recursivamente por arquivos .bib dentro do diretório da base
        bib_files = glob.glob(os.path.join(base_path, "**", "*.bib"), recursive=True)
        if not bib_files:
            print(f"Nenhum arquivo .bib encontrado na base '{base}'.")
            continue

        for bib_file in bib_files:
            print(f"\nProcessando arquivo: {bib_file}")
            print(f"{90 * '-'}\n\n")
            # Neste exemplo, o arquivo enriquecido sobrescreve o original.
            enrich_bibtex_file(bib_file, df_jcr, df_scimago, bib_file)


async def enrich_bibtex():
    try:
        with open(os.path.abspath("Config/general_config.yaml"), "r", encoding="utf-8") as f:
            enrich_config = yaml.safe_load(f)
            os.environ["ENRICH_ARXIV"] = str(enrich_config.get("enrich_arxiv", False))
            
    except Exception as e:
        raise Exception(f"Erro ao ler o arquivo de configuração: {e}")
    
    # Inicializa o semáforo para controle de requisições
    global REQUEST_SEMAPHORE
    REQUEST_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    run_enrich = False
    
    if enrich_config.get("enrich_bibtex_doi"):
        print("\n\n\n==============================================")
        print("EnrichBibtex DOIS Started!")
        print("==============================================\n\n")
        
        # Executa o enriquecimento de DOIs de forma assíncrona
        await enrich_bibtex_dois()
        
        # Aguarda meio segundo para melhor visualização dos prints
        await asyncio.sleep(0.5)
        
        run_enrich = True
    
    if enrich_config.get("enrich_bibtex_abstract"):
        print("\n\n\n==============================================")
        print("EnrichBibtex abstract Started!")
        print("==============================================\n\n")
        
        # Executa o enriquecimento de abstracts de forma assíncrona
        await enrich_bibtex_abstract()
        
        # Aguarda meio segundo para melhor visualização dos prints
        await asyncio.sleep(0.5)
        
        run_enrich = True
    
    if enrich_config.get("enrich_bibtex_keywords"):
        print("\n\n\n==============================================")
        print("EnrichBibtex keywords Started!")
        print("==============================================\n\n")
        
        # Executa o enriquecimento de keywords de forma assíncrona
        await enrich_bibtex_keywords()
        
        # Aguarda meio segundo para melhor visualização dos prints
        await asyncio.sleep(0.5)
        
        run_enrich = True
    
    if enrich_config.get("enrich_bibtex_jcr_scimago"):
        print("\n\n\n==============================================")
        print("EnrichBibtex JCR e SCIMAGO Started!")
        print("==============================================\n\n")
        
        # Como enrich_bibtex_jcr_scimago é uma função síncrona,
        # executamos ela em um executor para não bloquear
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, enrich_bibtex_jcr_scimago)
        
        # Aguarda meio segundo para melhor visualização dos prints
        await asyncio.sleep(0.5)
        
        run_enrich = True
    
    if run_enrich:
        print("\n\n++++++++++++++++++++++++++++++++++++++++++++++")
        print("EnrichBibtex completed successfully!")
        print("++++++++++++++++++++++++++++++++++++++++++++++\n\n")

