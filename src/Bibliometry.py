import os
import requests
import yaml
import json
import time
from dotenv import load_dotenv
from src.BibTex import read_bibtex, write_bibtex
from src.Database import create_lancedb_instance, save_bibliographic_database, fetch_bibliographic_database

# Carregando variáveis de ambiente
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

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



def fetch_and_store_metadata(bibtex_path):
    """
    Lê um arquivo BibTeX, busca metadados no OpenAlex e Scopus para cada entrada com DOI,
    e armazena os resultados no banco de dados LanceDB.
    
    Args:
        bibtex_path (str): Caminho para o arquivo BibTeX
    """
    print(f"\nProcessando arquivo: {bibtex_path}")
    print(f"{90 * '-'}\n")
    
    # Inicializar uma lista para armazenar os erros
    error_logs = []
    
    try:
        # Lendo o arquivo BibTeX
        entries = read_bibtex(bibtex_path)
        list_entries_openalex = []
        list_entries_scopus = []
        
        if not entries:
            print(f"Nenhuma entrada encontrada no arquivo: {bibtex_path}")
            return
        
        with open(os.path.abspath("config/general_config.yaml"), "r", encoding="utf-8") as f:
            bibliometry_config = yaml.safe_load(f)
            
        use_arxiv = bibliometry_config.get("bibliometry_for_arxiv", False)
        bibliometry_openalex = bibliometry_config.get("bibliometry_using_openalex", False)
        
        
        ##### Fulll bibliometry using scopus NOT IMPLEMENTED YET #####
        ##### Setting False to avoid errors #####
        
        # TODO: Implementar bibliometria completa usando Scopus
        # bibliometry_scopus = bibliometry_config.get("bibliometry_using_scopus", False)
        bibliometry_scopus = False
        
        if not bibliometry_openalex and not bibliometry_scopus:
            raise ValueError("Nenhuma fonte de metadados habilitada. Verifique o arquivo de configuração.")
            
        for entry in entries:
            title = entry.get("title", "Título não disponível")
            doi = entry.get("doi", "").strip()
            type_publication = entry.get("type_publication", "")
            
            if not use_arxiv and ("arxiv" in type_publication.lower() or "arxiv" in doi.lower()):
                print(f"Registro '{title}': Artigo do ArXiv, não é possível buscar metadados.\n")
                # Registrar erro no log
                error_logs.append(f"ArXiv não suportado: {title} - DOI: {doi}")
                continue
            
            if not doi:
                print(f"Registro '{title}': Sem DOI, impossível buscar metadados.\n")
                # Registrar erro no log
                error_logs.append(f"DOI não encontrado: {title}")
                continue
                
            # Tratando o DOI para remover prefixos
            doi_cleaned = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
            doi_cleaned = doi_cleaned.replace("https://doi.org", "").replace("http://doi.org", "").strip()
            
            print(f"Buscando metadados para '{title}' (DOI: {doi_cleaned})...")
            
            # Buscando no OpenAlex
            if bibliometry_openalex:
                openalex_data = fetch_metadata_from_openalex(doi_cleaned)
                if openalex_data:
                    print(f"Metadados do OpenAlex obtidos com sucesso para '{title}'")
                    list_entries_openalex.append(openalex_data)
                else:
                    error_logs.append(f"Registro '{title}': Falha ao buscar metadados no OpenAlex para DOI {doi_cleaned}.")
            
            # Buscando no Scopus
            if bibliometry_scopus:
                scopus_data = fetch_metadata_from_scopus(doi_cleaned)
                if scopus_data:
                    print(f"Metadados do Scopus obtidos com sucesso para '{title}'")
                    list_entries_scopus.append(scopus_data)
                else:
                    error_logs.append(f"Registro '{title}': Falha ao buscar metadados no Scopus para DOI {doi_cleaned}.")
            
            print(f"Processamento concluído para '{title}'\n")
        
        # Salvando metadados em arquivos JSON
        if bibliometry_openalex:
            save_local_json_openalex(list_entries_openalex)
        if bibliometry_scopus:
            save_local_json_scopus(list_entries_scopus)
            
        # Salvar os erros em um arquivo de log se houver erros
        path_data = os.getenv("PATH_DATA", ".data")
        os.makedirs(os.path.join(path_data, "BIBLIOMETRY"), exist_ok=True)
        log_path = os.path.join(path_data, "BIBLIOMETRY", "error_fetch_openalex.log")
        
        if error_logs:
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write(f"Erros encontrados em {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write("-" * 50 + "\n")
                for error in error_logs:
                    log_file.write(f"{error}\n")
            
            # Exibir mensagem de erro em vermelho
            print(f"\n\n{90 * '-'}")
            print("\033[91m" + "\033[1m" + f"ERRO: Alguns artigos não puderam ser processados." + "\033[0m")
            print("\033[91m" + f"Verifique o log em: {log_path}" + "\033[0m")
            print(f"{90 * '-'} \n\n")
            
            # Esperar 3 segundos
            time.sleep(3)
        else:
            # Se não há erros e o arquivo de log existe, apaga-o
            if os.path.exists(log_path):
                os.remove(log_path)
            
        print(f"Processamento do arquivo {bibtex_path} concluído com sucesso!")
    except Exception as e:
        print(f"Erro ao processar o arquivo BibTeX ({bibtex_path}): {e}")


def fetch_metadata_from_openalex(doi):
    """
    Busca metadados de um artigo no OpenAlex usando o DOI e salva no banco de dados.
    
    Args:
        doi (str): DOI do artigo
        
    Returns:
        dict: Dados obtidos do OpenAlex ou None em caso de falha
    """
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = HEADERS.copy()
    try:
        type_source = "openalex"
        
        # Verifica se já existe no banco de dados
        try:
            data = fetch_bibliographic_database(type_source, doi, db)
            if data:
                print(f"Registro já existe no banco de dados: {type_source}, doi: {doi}")
                return data
        except Exception as e:
            print(f"Erro ao verificar registro no banco de dados: {e}")
        
        # Se não existe, busca na API
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            print(f"DOI {doi} não encontrado no OpenAlex")
            return None
            
        response.raise_for_status()
        data = response.json()
        
        if data:
            # Salva no banco de dados
            try:
                save_bibliographic_database(type_source, doi, data, db)
                print(f"Dados do OpenAlex salvos no banco para DOI: {doi}")
            except Exception as e:
                print(f"Erro ao salvar registro no banco de dados: {e}")
                
        return data
        
    except Exception as e:
        print(f"Erro ao buscar metadados do OpenAlex para DOI {doi}: {e}")
        return None


def fetch_metadata_from_scopus(doi):
    """
    Busca metadados de um artigo na API de abstract do Scopus usando o DOI e salva no banco de dados.
    
    Args:
        doi (str): DOI do artigo
        
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
            data = fetch_bibliographic_database(type_source, doi, db)
            if data:
                print(f"Registro já existe no banco de dados: {type_source}, doi: {doi}")
                return data
        except Exception as e:
            print(f"Erro ao verificar registro no banco de dados: {e}")
        
        # Se não existe, busca na API
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            print(f"DOI {doi} não encontrado no Scopus")
            return None
            
        response.raise_for_status()
        data = response.json()
        
        if data:
            # Salva no banco de dados
            try:
                save_bibliographic_database(type_source, doi, data, db)
                print(f"Dados do Scopus salvos no banco para DOI: {doi}")
            except Exception as e:
                print(f"Erro ao salvar registro no banco de dados: {e}")
                
        return data
        
    except Exception as e:
        print(f"Erro ao buscar metadados do Scopus para DOI {doi}: {e}")
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



def run_bibliometry(stage=None, bib=None):
    """
    Função principal para execução da bibliometria (síncrona / compatível com pipeline).
    Delega para BibliometryAsync com suporte a estágios (post_abstract / final) e bibtex customizado.
    """
    from src.BibliometryAsync import run_bibliometry as run_bib_async
    run_bib_async(stage=stage, bib=bib)