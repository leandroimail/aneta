import os
import argparse
from dotenv import load_dotenv

def setup_environment():
    load_dotenv()
    load_dotenv(os.path.abspath("Config/.env"))
    global PROJECT_PATH
    PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
    os.environ["PROJECT_PATH"] = PROJECT_PATH

def run_search():
    from src.Search import run_search
    run_search()
    return True

def run_enrich():
    from src.EnrichBibtex import enrich_bibtex
    enrich_bibtex()
    return True

def run_analyse():
    from src.Analyse import get_analyse
    get_analyse()
    return True

def run_bibliometry_function():
    from src.Bibliometry import run_bibliometry
    run_bibliometry()
    return True

def run_download():
    from src.DonwloadPapers import download_all_papers
    from src.Config import path_directory_bibs
    
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
    doi_file = os.environ.get("DOI_FILE", ".OUTPUTS/DOIs.txt")
    folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "PDFs")
    
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    
    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    path_directory_file_doi = path_data.replace(".bibs", doi_file)
    folder_save_pdf = path_data.replace(".bibs", folder_save_pdf)
    download_all_papers(path_directory_file_bib, folder_save_pdf, path_directory_file_doi)
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

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Executa diferentes funcionalidades do projeto ASRL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos de uso:
  python aneta.py --search
  python aneta.py --enrich
  python aneta.py --download
''')
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--search', action='store_true', help='Executa a busca no banco de dados acadêmicos')
    group.add_argument('--enrich', action='store_true', help='Executa o enriquecimento dos bibtex')
    group.add_argument('--analyse', action='store_true', help='Executa a análise dos bibtex')
    group.add_argument('--bibliometry', action='store_true', help='Executa a bibliometria completa dos bibtex')
    group.add_argument('--download', action='store_true', help='Executa o download dos papers')
    group.add_argument('--deprecated_abstract', action='store_true', help='Executa a leitura do abstract (Depreciado)')
    
    return parser.parse_args(), parser

if __name__ == "__main__":
    ###################  Variáveis de configuração (modo script)
    run_search_database = False
    run_enrich_bibtex = False
    run_analyse_bibtex = False
    run_bibliometry = False
    run_download_papers = False
    run_deprecated_abstract = False

    setup_environment()
    
    # Verifica se há argumentos de linha de comando
    args, parser = parse_arguments()
    
    # Prioriza argumentos de linha de comando sobre as variáveis do script
    if args.search or run_search_database:
        run_search()
    elif args.enrich or run_enrich_bibtex:
        run_enrich()
    elif args.analyse or run_analyse_bibtex:
        run_analyse()
    elif args.bibliometry or run_bibliometry:
        run_bibliometry_function()
    elif args.download or run_download_papers:
        run_download()
    elif args.deprecated_abstract or run_deprecated_abstract:
        deprecated_abstract()
    else:
        parser.print_help()
        # Opcional: para sair com código de erro
        import sys
        sys.exit(1)




