import os
import yaml
import json
import asyncio
import aiohttp
import shutil
from typing import Optional, List, Dict, Any, Tuple
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from src.BibTex import read_bibtex, write_bibtex
from src.Database import create_lancedb_instance, save_bibliographic_database, fetch_bibliographic_database
from src.BibliometryAnalysis import generate_bibliometry_report_and_plots

# Carregando variáveis de ambiente
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

# Criando instância do banco
db = create_lancedb_instance()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def save_local_json_openalex(list_entries: List[Dict[str, Any]], suffix: str = ""):
    """Salva a lista de registros do OpenAlex em JSON (geral e por estágio)."""
    PATH_DATA = os.getenv("PATH_DATA", ".data")
    outputs_dir = os.path.abspath(f"{PATH_DATA}/OUTPUTS")
    os.makedirs(outputs_dir, exist_ok=True)
    
    # Sempre mantém openalex_metadata.json na raiz de OUTPUTS (compatibilidade com R Bibliometrix)
    main_path = os.path.join(outputs_dir, "openalex_metadata.json")
    with open(main_path, "w", encoding="utf-8") as f:
        json.dump(list_entries, f, indent=0, ensure_ascii=False)
        
    # Salva versão com sufixo do estágio
    if suffix:
        stage_path = os.path.join(outputs_dir, f"openalex_metadata_{suffix}.json")
        with open(stage_path, "w", encoding="utf-8") as f:
            json.dump(list_entries, f, indent=0, ensure_ascii=False)
            
    print(f"Metadados do OpenAlex salvos em: {main_path}")


def save_local_json_scopus(list_entries):
    ##### Full bibliometry using scopus NOT IMPLEMENTED YET #####
    return


import time
_db_lock = asyncio.Lock()
_sem = asyncio.Semaphore(4)
_last_request_time = 0.0
_time_lock = asyncio.Lock()

async def _rate_limit_delay(min_interval: float = 0.25):
    global _last_request_time
    async with _time_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_request_time = time.time()

# Funções auxiliares para operações do banco de dados assíncronas
async def async_fetch_from_db(type_source, doi, db):
    """Wrapper assíncrono para a operação de busca no banco de dados"""
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fetch_bibliographic_database, type_source, doi, db)
    except Exception:
        return None


async def async_save_to_db(type_source, doi, data, db):
    """Wrapper assíncrono para a operação de salvamento no banco de dados com lock"""
    async with _db_lock:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, save_bibliographic_database, type_source, doi, data, db)
        except Exception as e:
            print(f"Erro ao salvar no banco: {e}")
            return None


async def fetch_metadata_from_crossref(doi: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """
    Busca metadados bibliográficos no Crossref como fallback resiliente e gratuito.
    Retorna estrutura normalizada e compatível com o schema esperado pelo OpenAlex.
    """
    url = f"https://api.crossref.org/works/{doi}"
    headers = HEADERS.copy()
    mailto = os.getenv("CROSSREF_EMAIL") or os.getenv("OPENALEX_EMAIL") or os.getenv("UNPAYWALL_EMAIL")
    params = {"mailto": mailto} if mailto else None
    
    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            msg = data.get("message") or {}
            
            # Extração de título
            titles = msg.get("title") or []
            title = titles[0] if titles else "Sem título"
            
            # Extração do ano de publicação
            year = None
            for date_key in ("published-print", "published-online", "created", "issued"):
                dp = (msg.get(date_key) or {}).get("date-parts")
                if dp and len(dp) > 0 and len(dp[0]) > 0:
                    year = dp[0][0]
                    break
                    
            # Venue / Journal / Conferência
            containers = msg.get("container-title") or []
            venue = containers[0] if containers else (msg.get("publisher") or "Outro / Crossref")
            
            # Citações
            cited_by = msg.get("is-referenced-by-count", 0) or 0
            
            # Autores e afiliações
            authorships = []
            for auth in msg.get("author") or []:
                family = auth.get("family", "")
                given = auth.get("given", "")
                name = f"{given} {family}".strip() or family or "Desconhecido"
                affils = auth.get("affiliation") or []
                insts = [{"display_name": a.get("name", "")} for a in affils if a.get("name")]
                authorships.append({
                    "author": {"display_name": name},
                    "institutions": insts
                })
                
            openalex_compat = {
                "id": f"crossref:{doi}",
                "doi": f"https://doi.org/{doi}",
                "title": title,
                "publication_year": year,
                "cited_by_count": cited_by,
                "primary_location": {
                    "source": {"display_name": venue}
                },
                "open_access": {
                    "is_oa": msg.get("is-oa", False) or ("open-access" in str(msg).lower())
                },
                "authorships": authorships,
                "concepts": [
                    {"display_name": s, "score": 1.0} for s in (msg.get("subject") or [])
                ],
                "_source": "crossref_fallback"
            }
            return openalex_compat
    except Exception as e:
        return None


async def fetch_metadata_from_openalex(doi: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """
    Busca metadados de um artigo no OpenAlex usando o DOI e salva no banco de dados.
    Utiliza mailto polido, controle de taxa com semáforo, retry inteligente em 429
    e fallback automático para Crossref caso a cota do OpenAlex esteja esgotada.
    """
    # 1. Verifica cache no banco de dados
    try:
        data = await async_fetch_from_db("openalex", doi, db)
        if data:
            return data
    except Exception:
        pass

    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = HEADERS.copy()
    mailto = os.getenv("OPENALEX_EMAIL") or os.getenv("UNPAYWALL_EMAIL")
    params = {}
    if mailto:
        params["mailto"] = mailto
    api_key = os.getenv("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key

    # 2. Busca no OpenAlex com rate limiting
    async with _sem:
        for attempt in range(2):
            await _rate_limit_delay(0.25)
            try:
                async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 404:
                        break
                    if response.status == 429:
                        try:
                            body = await response.json()
                            retry_after = body.get("retryAfter") or int(response.headers.get("Retry-After", 5))
                        except Exception:
                            retry_after = 5
                            
                        if retry_after <= 60 and attempt == 0:
                            print(f"[OpenAlex] Limite temporário atingido ({doi}). Aguardando {retry_after}s...")
                            await asyncio.sleep(retry_after + 1)
                            continue
                        else:
                            # Cota diária esgotada ou espera muito longa -> usa Crossref
                            break
                            
                    response.raise_for_status()
                    data = await response.json()
                    if data:
                        await async_save_to_db("openalex", doi, data, db)
                        return data
            except Exception:
                pass

    # 3. Fallback resiliente para Crossref se o OpenAlex falhar ou exceder limite
    crossref_data = await fetch_metadata_from_crossref(doi, session)
    if crossref_data:
        print(f"[Crossref Fallback] Metadados obtidos para DOI: {doi}")
        await async_save_to_db("openalex", doi, crossref_data, db)
        return crossref_data

    return None



async def fetch_metadata_from_scopus(doi, session):
    """
    Busca metadados de um artigo na API de abstract do Scopus usando o DOI.
    """
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        return None
        
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    headers.update(HEADERS)
    
    try:
        type_source = "scopus"
        try:
            data = await async_fetch_from_db(type_source, doi, db)
            if data:
                print(f"Registro já existe no banco de dados: {type_source}, doi: {doi}")
                return data
        except Exception as e:
            print(f"Erro ao verificar registro no banco de dados: {e}")
        
        async with session.get(url, headers=headers) as response:
            if response.status == 404:
                return None
                
            response.raise_for_status()
            data = await response.json()
            
            if data:
                try:
                    await async_save_to_db(type_source, doi, data, db)
                    print(f"Dados do Scopus salvos no banco para DOI: {doi}")
                except Exception as e:
                    print(f"Erro ao salvar registro no banco de dados: {e}")
                    
            return data
            
    except Exception as e:
        print(f"Erro ao buscar metadados do Scopus para DOI {doi}: {e}")
        return None


async def async_process_entry(entry, session, use_arxiv, bibliometry_openalex, bibliometry_scopus):
    """Processa uma entrada BibTeX de forma assíncrona."""
    title = entry.get("title", "Título não disponível")
    doi = entry.get("doi", "").strip()
    type_publication = entry.get("type_publication", "")
    
    error_msg = None
    if not use_arxiv and ("arxiv" in type_publication.lower() or "arxiv" in doi.lower()):
        error_msg = f"Registro '{title}': Artigo do ArXiv, não é possível buscar metadados."
        return None, None, error_msg
    
    if not doi:
        error_msg = f"Registro '{title}': Sem DOI, impossível buscar metadados."
        return None, None, error_msg
    
    # Normalização do DOI
    doi_cleaned = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    doi_cleaned = doi_cleaned.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    openalex_data = None
    scopus_data = None
    
    if bibliometry_openalex:
        openalex_data = await fetch_metadata_from_openalex(doi_cleaned, session)
        if not openalex_data:
            error_msg = f"Registro '{title}': Falha ao buscar metadados no OpenAlex para DOI {doi_cleaned}."
    
    if bibliometry_scopus:
        scopus_data = await fetch_metadata_from_scopus(doi_cleaned, session)
    
    return openalex_data, scopus_data, error_msg


def save_openalex_fetch_errors(errors: List[str]) -> str:
    """Salva os erros de busca no OpenAlex em um arquivo de log."""
    path_data = os.getenv("PATH_DATA", ".data")
    log_dir = os.path.join(path_data, "BIBLIOMETRY")
    os.makedirs(log_dir, exist_ok=True)
    error_file = os.path.join(log_dir, "error_fetch_openalex.log")
    
    with open(error_file, "w", encoding="utf-8") as f:
        for error in errors:
            f.write(f"{error}\n")
    
    return error_file


async def fetch_and_store_metadata_async(bibtex_path: str, stage: str = "final") -> Tuple[List[Dict], List[str], List[Dict]]:
    """
    Lê um arquivo BibTeX, busca metadados no OpenAlex/Scopus para cada entrada e armazena.
    
    Returns:
        Tupla contendo (entries, errors, list_entries_openalex)
    """
    print(f"\nProcessando arquivo para bibliometria: {bibtex_path}")
    print(f"{90 * '-'}\n")
    
    errors = []
    entries = []
    list_entries_openalex = []
    
    try:
        entries = read_bibtex(bibtex_path)
        list_entries_scopus = []
        
        if not entries:
            print(f"Nenhuma entrada encontrada no arquivo: {bibtex_path}")
            return entries, errors, list_entries_openalex
        
        with open(os.path.abspath("config/general_config.yaml"), "r", encoding="utf-8") as f:
            bibliometry_config = yaml.safe_load(f) or {}
            
        use_arxiv = bibliometry_config.get("bibliometry_for_arxiv", False)
        bibliometry_openalex = bibliometry_config.get("bibliometry_using_openalex", True)
        bibliometry_scopus = bibliometry_config.get("bibliometry_using_scopus", False)
        
        if not bibliometry_openalex and not bibliometry_scopus:
            raise ValueError("Nenhuma fonte de metadados habilitada em config/general_config.yaml.")
            
        # Conexão assíncrona HTTP
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                async_process_entry(entry, session, use_arxiv, bibliometry_openalex, bibliometry_scopus)
                for entry in entries
            ]
            results = await asyncio.gather(*tasks)
            
            for openalex_data, scopus_data, error in results:
                if error:
                    errors.append(error)
                if openalex_data:
                    list_entries_openalex.append(openalex_data)
                if scopus_data:
                    list_entries_scopus.append(scopus_data)
        
        # Salva os metadados em disco
        if bibliometry_openalex and list_entries_openalex:
            save_local_json_openalex(list_entries_openalex, suffix=stage)
        if bibliometry_scopus and list_entries_scopus:
            save_local_json_scopus(list_entries_scopus)
            
        print(f"✓ Metadados de {len(list_entries_openalex)}/{len(entries)} artigos recuperados no OpenAlex.")
    except Exception as e:
        print(f"Erro ao processar o arquivo BibTeX ({bibtex_path}): {e}")
        errors.append(f"Erro geral: {e}")
        
    return entries, errors, list_entries_openalex


def fetch_and_store_metadata(bibtex_path: str, stage: str = "final") -> Tuple[List[Dict], Optional[str], List[Dict]]:
    """Wrapper síncrono para fetch_and_store_metadata_async."""
    entries, errors, list_openalex = asyncio.run(fetch_and_store_metadata_async(bibtex_path, stage=stage))
    error_file = None
    if errors:
        error_file = save_openalex_fetch_errors(errors)
    else:
        path_data = os.getenv("PATH_DATA", ".data")
        err_p = os.path.join(path_data, "BIBLIOMETRY", "error_fetch_openalex.log")
        if os.path.exists(err_p):
            try:
                os.remove(err_p)
            except Exception:
                pass
    return entries, error_file, list_openalex


def run_R_bibliometrix(rscript_bin: Optional[str] = None, stage: str = "final") -> bool:
    """Executa o script em linguagem R com o pacote Bibliometrix se Rscript estiver disponível."""
    path = os.path.abspath("src/Bibliometry/RunBibliometrix.r")
    r_exec = rscript_bin or shutil.which("Rscript") or ("/opt/homebrew/bin/Rscript" if os.path.exists("/opt/homebrew/bin/Rscript") else None)
    if not r_exec:
        print("Rscript não encontrado. Pulando execução do script R.")
        return False
        
    print(f"Executando {r_exec} {path}...")
    ret = os.system(f"{r_exec} {path}")
    
    path_data = os.getenv("PATH_DATA", ".data")
    path_error = os.path.join(path_data, "BIBLIOMETRY", "error.log")
    path_execution = os.path.join(path_data, "BIBLIOMETRY", "execution.log")
    has_error = False
    
    if os.path.exists(path_error):
        with open(path_error, "r", encoding="utf-8") as f:
            error_log = f.read().strip()
            if error_log:
                has_error = True
                print("Aviso na execução do script R (Bibliometrix):")
                for line in error_log.split("\n")[:10]:
                    print(f"  {line}")
    
    if not has_error and ret == 0:
        print(f"\n{90 * '-'}\nScript R (Bibliometrix) executado com sucesso!\nVerifique os gráficos e logs em: {path_data}/BIBLIOMETRY\n{90 * '-'}")
        return True
    else:
        print(f"Aviso no Bibliometrix R. Logs disponíveis em: {path_data}/BIBLIOMETRY")
        return False


def run_bibliometry(stage: Optional[str] = None, bibtex_path: Optional[str] = None, bib: Optional[str] = None):
    """
    Ponto de entrada principal para a execução parametrizada da bibliometria.
    
    Args:
        stage: 'final' (default), 'post_abstract' ou 'both'.
        bibtex_path / bib: Caminho opcional direto para o arquivo BibTeX.
    """
    bibtex_path = bibtex_path or bib
    path_data = os.getenv("PATH_DATA", ".data")
    
    # Carregar configurações
    config_path = os.path.abspath("config/general_config.yaml")
    gen_cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            gen_cfg = yaml.safe_load(f) or {}
            
    stage = stage or gen_cfg.get("bibliometry_stage", "final")
    
    if stage == "both":
        print("\n=== Executando Bibliometria Parametrizada para AMBOS os estágios (post_abstract + final) ===")
        run_bibliometry(stage="post_abstract")
        run_bibliometry(stage="final")
        return True
        
    # Resolução dinâmica do arquivo de entrada BibTeX
    if not bibtex_path:
        if stage == "post_abstract":
            candidates = [
                os.path.join(path_data, "OUTPUTS", "relevant_abstract_papers.bib"),
                os.path.join(path_data, "OUTPUTS", "select_bibs.bib"),
            ]
        else: # final
            candidates = [
                os.path.join(path_data, "OUTPUTS", "final_papers.bib"),
                os.path.join(path_data, "OUTPUTS", "final_results", "final_papers.bib"),
                os.path.join(path_data, "OUTPUTS", "relevant_abstract_papers.bib"),
            ]
        for c in candidates:
            if os.path.exists(c):
                bibtex_path = c
                break
        if not bibtex_path:
            bibtex_path = os.path.join(path_data, "OUTPUTS", "select_bibs.bib")
            
    full_path_bibtex = os.path.abspath(bibtex_path)
    print("\n" + "=" * 70)
    print(f"=== BIBLIOMETRIA PARAMETRIZADA (Estágio: {stage.upper()}) ===")
    print("=" * 70)
    print(f"Arquivo BibTeX: {full_path_bibtex}")
    
    # 1. Recuperar metadados OpenAlex
    entries, error_file, list_openalex = fetch_and_store_metadata(full_path_bibtex, stage=stage)
    
    # 2. Gerar relatórios, métricas e gráficos em Python
    if gen_cfg.get("bibliometry_generate_py_charts", True) and list_openalex:
        print(f"\n{'-'*70}\nGerando análises, tabelas e gráficos em Python...\n{'-'*70}")
        out_dir = os.path.join(path_data, "OUTPUTS", "BIBLIOMETRY", stage)
        generate_bibliometry_report_and_plots(list_openalex, stage=stage, output_dir=out_dir)
        
    # 3. Executar script R (Bibliometrix) se habilitado e disponível
    if gen_cfg.get("bibliometry_generate_r_plots", True):
        rscript_bin = shutil.which("Rscript") or ("/opt/homebrew/bin/Rscript" if os.path.exists("/opt/homebrew/bin/Rscript") else None)
        if rscript_bin:
            print(f"\n{'-'*70}\nExecutando script R (Bibliometrix)...\n{'-'*70}")
            run_R_bibliometrix(rscript_bin=rscript_bin, stage=stage)
        else:
            print(f"\nℹ Rscript não detectado no sistema no momento. As análises bibliométricas, métricas e gráficos foram gerados nativamente em Python.")
            
    print("\n" + "=" * 70)
    print(f"✓ Bibliometria ({stage.upper()}) concluída com sucesso!")
    print("=" * 70 + "\n")
    return True