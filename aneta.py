import __init__
import os
import sys
import argparse
import asyncio
from dotenv import load_dotenv

from src.Search import run_search as search_run
from src.EnrichBibtex import enrich_bibtex as enrich_bibtex_sync
from src.EnrichBibtexAsync import enrich_bibtex as enrich_bibtex_async
from src.Selection import get_analyse
from src.Bibliometry import run_bibliometry as run_bibliometry_func
from src.BibliometryAsync import run_bibliometry as run_bibliometry_async_func
from src.DonwloadPapers import download_all_papers
from GenerativeAI.LLMUtils import run_prepare_base_prompt


def setup_environment():
    load_dotenv(os.path.abspath(".conf"))
    load_dotenv(os.path.abspath("Config/.env"))
    global PROJECT_PATH
    PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
    os.environ["PROJECT_PATH"] = PROJECT_PATH

def run_search():
    search_run()
    return True

def run_enrich():
    enrich_bibtex_sync()
    return True

def run_enrich_async():
    asyncio.run(enrich_bibtex_async())
    return True

def run_selection():
    get_analyse()
    return True

def run_bibliometry_function():
    run_bibliometry_func()
    return True

def run_bibliometry_async():
    run_bibliometry_async_func()
    return True

def run_download():
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
    folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "PDFs")
    
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    
    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    folder_save_pdf = path_data.replace(".bibs", folder_save_pdf)
    download_all_papers(path_directory_file_bib, folder_save_pdf)
    return True

def deprecated_abstract():
    if not os.getenv("RUN_DEPRECATED_JOBS", 0):
        print("A variável de ambiente RUN_DEPRECATED_JOBS não foi definida como 1")
        print("Por favor, defina a variável de ambiente RUN_DEPRECATED_JOBS=1 para rodar a função de leitura do abstract")
        return False
    if not os.getenv("PATH_SPRINGER") and not os.getenv("PATH_ACM"):
        print("A variável de ambiente PATH_SPRINGER ou PATH_ACM não foi definida")
        print("Por favor, defina a variável de ambiente PATH_SPRINGER ou PATH_ACM para rodar a função de leitura do abstract")
        return False
        
    from src.Deprecated.Abstract import get_abstract
    from src.Config import path_SPRINGER, path_ACM
    if path_SPRINGER:
        get_abstract(path_SPRINGER, "SPRINGER")
    if path_ACM:
        get_abstract(path_ACM, "ACM")
    return True

def run_abstract_classifier_llm():
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
    
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    
    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    
    # Chamando a função com um caminho único de arquivo BibTeX
    run_prepare_base_prompt(path_directory_file_bib)
    return True

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Executa diferentes funcionalidades do projeto ASRL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Exemplos de uso:
                        python aneta.py --search
                        python aneta.py --enrich
                        python aneta.py --selection
        ''')
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--search', action='store_true', help='Executa a busca no banco de dados acadêmicos')
    group.add_argument('--enrich', action='store_true', help='Executa o enriquecimento dos bibtex')
    group.add_argument('--enrich_async', action='store_true', help='Executa o enriquecimento dos bibtex de forma assíncrona')
    group.add_argument('--selection', action='store_true', help='Executa a seleção dos bibtex')
    group.add_argument('--bibliometry', action='store_true', help='Executa a bibliometria completa do bibtex selecionado')
    group.add_argument('--bibliometry_async', action='store_true', help='Executa de forma assíncrona a bibliometria completa do bibtex selecionado')
    group.add_argument('--download_pdf', action='store_true', help='Executa o download dos papers')
    group.add_argument('--deprecated_abstract', action='store_true', help='Executa a leitura do abstract para ACM ou Spring via Web Scraping (Depreciado)')
    group.add_argument('--abstract_classifier_llm', action='store_true', help='Realiza a classificação de abstracts usando LLM')

    return parser.parse_args(), parser

if __name__ == "__main__":
    ###################  Variáveis de configuração (modo script)
    run_search_database = False
    run_enrich_bibtex = False
    run_enrich_bibtex_async = False
    run_selection_bibtex = False
    run_bibliometry_async_var = False
    run_bibliometry = False
    run_download_papers = False
    run_deprecated_abstract = False
    run_abstract_llm = True

    setup_environment()
    
    # Verifica se há argumentos de linha de comando
    args, parser = parse_arguments()
    
    # Prioriza argumentos de linha de comando sobre as variáveis do script
    if args.search:
        run_search()
    elif args.enrich:
        run_enrich()
    elif args.enrich_async:
        run_enrich_async()
    elif args.bibliometry_async:
        run_bibliometry_async()
    elif args.selection:
        run_selection()
    elif args.bibliometry:
        run_bibliometry_function()
    elif args.download_pdf:
        run_download()
    elif args.deprecated_abstract:
        deprecated_abstract()
    elif args.abstract_classifier_llm:
        run_abstract_classifier_llm()
    elif run_search_database:
        run_search()
    elif run_enrich_bibtex:
        run_enrich()
    elif run_enrich_bibtex_async:
        run_enrich_async()
    elif run_bibliometry_async_var:
        run_bibliometry_async()
    elif run_selection_bibtex:
        run_selection()
    elif run_bibliometry:
        run_bibliometry_function()
    elif run_download_papers:
        run_download()
    elif run_deprecated_abstract:
        deprecated_abstract()
    elif run_abstract_llm:
        run_abstract_classifier_llm()
    else:
        parser.print_help()
        sys.exit(1)




