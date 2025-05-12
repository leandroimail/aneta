import os
import yaml
import json
import asyncio
import aiohttp
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from src.BibTex import read_bibtex, write_bibtex
from src.Database import create_lancedb_instance, save_bibliographic_database, fetch_bibliographic_database

# Carregando variáveis de ambiente
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))

# Criando instância do banco
db = create_lancedb_instance()
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}


def save_local_json_openalex(list_entries):
    PATH_DATA = os.getenv("PATH_DATA", ".data")
    os.makedirs(os.path.abspath(f"{PATH_DATA}/OUTPUTS"), exist_ok=True)    
    with open(os.path.abspath(f"{PATH_DATA}/OUTPUTS/openalex_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(list_entries, f, indent=0, ensure_ascii=False)
        
    print(f"Metadados do OpenAlex salvos em: {os.path.abspath(f'{PATH_DATA}/OUTPUTS/openalex_metadata.json')}")
        

def save_local_json_scopus(list_entries):
    ##### Fulll bibliometry using scopus NOT IMPLEMENTED YET #####
    # TODO: Implementar salvamento de metadados do Scopus em arquivo JSON
    return


# Funções auxiliares para operações do banco de dados assíncronas
async def async_fetch_from_db(type_source, doi, db):
    """Wrapper assíncrono para a operação de busca no banco de dados"""
    with ThreadPoolExecutor() as executor:
        return await asyncio.get_event_loop().run_in_executor(
            executor, partial(fetch_bibliographic_database, type_source, doi, db)
        )


async def async_save_to_db(type_source, doi, data, db):
    """Wrapper assíncrono para a operação de salvamento no banco de dados"""
    with ThreadPoolExecutor() as executor:
        return await asyncio.get_event_loop().run_in_executor(
            executor, partial(save_bibliographic_database, type_source, doi, data, db)
        )


async def fetch_metadata_from_openalex(doi, session):
    """
    Busca metadados de um artigo no OpenAlex usando o DOI e salva no banco de dados (versão assíncrona).
    
    Args:
        doi (str): DOI do artigo
        session (aiohttp.ClientSession): Sessão HTTP para requisições assíncronas
        
    Returns:
        dict: Dados obtidos do OpenAlex ou None em caso de falha
    """
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = HEADERS.copy()
    try:
        type_source = "openalex"
        
        # Verifica se já existe no banco de dados
        try:
            data = await async_fetch_from_db(type_source, doi, db)
            if data:
                print(f"Registro já existe no banco de dados: {type_source}, doi: {doi}")
                return data
        except Exception as e:
            print(f"Erro ao verificar registro no banco de dados: {e}")
        
        # Se não existe, busca na API
        async with session.get(url, headers=headers) as response:
            if response.status == 404:
                print(f"DOI {doi} não encontrado no OpenAlex")
                return None
                
            response.raise_for_status()
            data = await response.json()
            
            if data:
                # Salva no banco de dados
                try:
                    await async_save_to_db(type_source, doi, data, db)
                    print(f"Dados do OpenAlex salvos no banco para DOI: {doi}")
                except Exception as e:
                    print(f"Erro ao salvar registro no banco de dados: {e}")
                    
            return data
            
    except Exception as e:
        print(f"Erro ao buscar metadados do OpenAlex para DOI {doi}: {e}")
        return None


async def fetch_metadata_from_scopus(doi, session):
    """
    Busca metadados de um artigo na API de abstract do Scopus usando o DOI e salva no banco de dados (versão assíncrona).
    
    Args:
        doi (str): DOI do artigo
        session (aiohttp.ClientSession): Sessão HTTP para requisições assíncronas
        
    Returns:
        dict: Dados obtidos do Scopus ou None em caso de falha
    """
    scopus_api_key = os.environ.get("ELSEVIER_API_KEY")
    if not scopus_api_key:
        print("ELSEVIER_API_KEY não definida.")
        return None
        
    url = f"https://api.elsevier.com/content/abstract/doi/{doi}?apiKey={scopus_api_key}"
    headers = {"Accept": "application/json"}
    headers.update(HEADERS)
    
    try:
        type_source = "scopus"
        
        # Verifica se já existe no banco de dados
        try:
            data = await async_fetch_from_db(type_source, doi, db)
            if data:
                print(f"Registro já existe no banco de dados: {type_source}, doi: {doi}")
                return data
        except Exception as e:
            print(f"Erro ao verificar registro no banco de dados: {e}")
        
        # Se não existe, busca na API
        async with session.get(url, headers=headers) as response:
            if response.status == 404:
                print(f"DOI {doi} não encontrado no Scopus")
                return None
                
            response.raise_for_status()
            data = await response.json()
            
            if data:
                # Salva no banco de dados
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
    """Processa uma entrada BibTeX de forma assíncrona"""
    title = entry.get("title", "Título não disponível")
    doi = entry.get("doi", "").strip()
    type_publication = entry.get("type_publication", "")
    
    error_msg = None
    if not use_arxiv and ("arxiv" in type_publication.lower() or "arxiv" in doi.lower()):
        error_msg = f"Registro '{title}': Artigo do ArXiv, não é possível buscar metadados."
        print(f"{error_msg}\n")
        return None, None, error_msg
    
    if not doi:
        error_msg = f"Registro '{title}': Sem DOI, impossível buscar metadados."
        print(f"{error_msg}\n")
        return None, None, error_msg
    
    # Tratando o DOI para remover prefixos
    doi_cleaned = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    doi_cleaned = doi_cleaned.replace("https://doi.org", "").replace("http://doi.org", "").strip()
    
    print(f"Buscando metadados para '{title}' (DOI: {doi_cleaned})...")
    
    openalex_data = None
    scopus_data = None
    
    # Buscando no OpenAlex
    if bibliometry_openalex:
        openalex_data = await fetch_metadata_from_openalex(doi_cleaned, session)
        if openalex_data:
            print(f"Metadados do OpenAlex obtidos com sucesso para '{title}'")
        else:
            print(f"Não foi possível obter metadados do OpenAlex para '{title}'")
            error_msg = f"Registro '{title}': Falha ao buscar metadados no OpenAlex para DOI {doi_cleaned}."
    
    # Buscando no Scopus
    if bibliometry_scopus:
        scopus_data = await fetch_metadata_from_scopus(doi_cleaned, session)
        if scopus_data:
            print(f"Metadados do Scopus obtidos com sucesso para '{title}'")
        else:
            print(f"Não foi possível obter metadados do Scopus para '{title}'")
    
    print(f"Processamento concluído para '{title}'\n")
    return openalex_data, scopus_data, error_msg


def save_openalex_fetch_errors(errors):
    """Salva os erros de busca no OpenAlex em um arquivo de log"""
    path_data = os.getenv("PATH_DATA", ".data")
    os.makedirs(os.path.join(path_data, "BIBLIOMETRY"), exist_ok=True)
    error_file = os.path.join(path_data, "BIBLIOMETRY", "error_fetch_openalex.log")
    
    with open(error_file, "w", encoding="utf-8") as f:
        for error in errors:
            f.write(f"{error}\n")
    
    return error_file


async def fetch_and_store_metadata_async(bibtex_path):
    """
    Lê um arquivo BibTeX, busca metadados no OpenAlex e Scopus para cada entrada com DOI,
    e armazena os resultados no banco de dados LanceDB (versão assíncrona).
    
    Args:
        bibtex_path (str): Caminho para o arquivo BibTeX
    """
    print(f"\nProcessando arquivo: {bibtex_path}")
    print(f"{90 * '-'}\n")
    
    errors = []
    
    try:
        # Lendo o arquivo BibTeX
        entries = read_bibtex(bibtex_path)
        list_entries_openalex = []
        list_entries_scopus = []
        
        if not entries:
            print(f"Nenhuma entrada encontrada no arquivo: {bibtex_path}")
            return errors
        
        with open(os.path.abspath("Config/general_config.yaml"), "r", encoding="utf-8") as f:
            bibliometry_config = yaml.safe_load(f)
            
        use_arxiv = bibliometry_config.get("bibliometry_for_arxiv", False)
        bibliometry_openalex = bibliometry_config.get("bibliometry_using_openalex", False)
        
        # TODO: Implementar bibliometria completa usando Scopus
        bibliometry_scopus = False
        
        if not bibliometry_openalex and not bibliometry_scopus:
            raise ValueError("Nenhuma fonte de metadados habilitada. Verifique o arquivo de configuração.")
            
        # Usando aiohttp para sessões HTTP assíncronas
        async with aiohttp.ClientSession() as session:
            tasks = []
            for entry in entries:
                task = async_process_entry(entry, session, use_arxiv, bibliometry_openalex, bibliometry_scopus)
                tasks.append(task)
            
            # Executa todas as tarefas em paralelo
            results = await asyncio.gather(*tasks)
            
            # Processa os resultados
            for openalex_data, scopus_data, error in results:
                if error:
                    errors.append(error)
                if openalex_data:
                    list_entries_openalex.append(openalex_data)
                if scopus_data:
                    list_entries_scopus.append(scopus_data)
        
        # Salvando metadados em arquivos JSON
        if bibliometry_openalex and list_entries_openalex:
            save_local_json_openalex(list_entries_openalex)
        if bibliometry_scopus and list_entries_scopus:
            save_local_json_scopus(list_entries_scopus)
            
        print(f"Processamento do arquivo {bibtex_path} concluído com sucesso!")
    except Exception as e:
        print(f"Erro ao processar o arquivo BibTeX ({bibtex_path}): {e}")
        errors.append(f"Erro geral: {e}")
        
    return errors


def fetch_and_store_metadata(bibtex_path):
    """
    Wrapper síncrono para a função assíncrona fetch_and_store_metadata_async.
    Mantém a mesma interface da função original.
    
    Args:
        bibtex_path (str): Caminho para o arquivo BibTeX
    """
    errors = asyncio.run(fetch_and_store_metadata_async(bibtex_path))
    if errors:
        return save_openalex_fetch_errors(errors)
    else:
        # If no errors occurred, remove any existing error log file
        path_data = os.getenv("PATH_DATA", ".data")
        error_file = os.path.join(path_data, "BIBLIOMETRY", "error_fetch_openalex.log")
        if os.path.exists(error_file):
            os.remove(error_file)
    return None


def run_R_bibliometrix():
    path = os.path.abspath("src/Bibliometry/RunBibliometrix.r")
    os.system(f"Rscript {path}")
    
    path_data = os.getenv("PATH_DATA", ".data")
    path_error = os.path.join(path_data, "BIBLIOMETRY", "error.log")
    path_executation = os.path.join(path_data, "BIBLIOMETRY", "execution.log")
    has_error = False
    
    if os.path.exists(path_error):
        has_error = True
        with open(path_error, "r", encoding="utf-8") as f:
            error_log = f.read()
            print(f"Erro ao executar o script R (Bibliometry)")
            
            for line in error_log.split("\n"):
                print(line)
                

    
    if not has_error:
        print("\n\n\n")
        print(f"{90 * '-'}")
        print("Script R (Bibliometrix) executado com sucesso!")
        print(f"Verifique o log de execução em  {path_executation}")
        print(f"{90 * '-'}")
    else:
        print("Script R (Bibliometrix) executado! Entretanto houve erros na sua execução")
        # Exibir erro em vermelho e com letra grande
        print("\n\n\n")
        print(f"{90 * '-'}")
        print("\033[91m" + "\033[1m" + f"ERRO NO BIBLIOMETRIX R! Verifique o log em: {path_error}" + "\033[0m")
        print(f"{90 * '-'}")



def run_bibliometry():
    """
    Função principal para execução da bibliometria.
    """
    path_data = os.getenv("PATH_DATA", ".data")
    bibtex_file = os.getenv("BIB_FILE", ".data/OUTPUTS/select_bibs.bib")
    full_path_bibtex = os.path.join(path_data, bibtex_file)
    full_path_bibtex = os.path.abspath(full_path_bibtex)
    
    error_file = fetch_and_store_metadata(full_path_bibtex)
    
    # Verificar se houve erros na busca
    if error_file:
        print("\n\n\n")
        print(f"{90 * '-'}")
        print("\033[91m" + "\033[1m" + f"ERRO: Alguns artigos não puderam ser processados." + "\033[0m")
        print("\033[91m" + f"Verifique o log em: {error_file}" + "\033[0m")
        print(f"{90 * '-'} \n\n")
        import time
        time.sleep(3)
    
    print("\n\n\n")
    print(f"{90 * '-'}")
    print("Executando script R (Bibliometrix)...")
    print(f"{90 * '-'}")
    
    run_R_bibliometrix()
    
    print("\n\n\n")
    print(f"{90 * '-'}")
    print("Bibliometria concluída com sucesso!")
    print(f"{90 * '-'} \n\n\n")