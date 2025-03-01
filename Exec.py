import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.abspath("Config/.env"))

###################  Informe se deve-se rodar a leitura do abstract (Depreciado)
run_deprecated_abstract = False

###################  Informe se deve-se rodar a busca no banco de dados academicos
run_search_database = True

###################  Informe se deve-se rodar a enriquecimento dos bibtex
run_enrich_bibtex = False

###################  Informe se deve-se rodar a análise dos bibtex
run_analyse_bibtex = False

###################  Informe se deve-se rodar o download dos papers
run_download_papers = False


if __name__ == "__main__":
    if run_deprecated_abstract:
        if not os.getenv("RUN_DEPRECATED_JOBS", 0):
            print("A variável de ambiente RUN_DEPRECATED_JOBS não foi definida como 1")
            print("Por favor, defina a variável de ambiente RUN_DEPRECATED_JOBS=1 para rodar a função de leitura do abstract")
            exit(1)
        if not os.getenv("PATH_SPRINGER") and not os.getenv("PATH_ACM"):
            print("A variável de ambiente PATH_SPRINGER ou PATH_ACM não foi definida")
            print("Por favor, defina a variável de ambiente PATH_SPRINGER ou PATH_ACM para rodar a função de leitura do abstract")
            exit(1)
        from src.Deprecated.Abstract import get_abstract
        from src.Config import path_SPRINGER, path_ACM
        if path_SPRINGER:
            get_abstract(path_SPRINGER, "SPRINGER")
        if path_ACM:
            get_abstract(path_ACM, "ACM")
    elif run_download_papers:
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
    elif run_search_database:
        from src.Search import run_search
        run_search()       
    elif run_enrich_bibtex:
        from src.EnrichBibtex import enrich_bibtex
        enrich_bibtex()
    elif run_analyse_bibtex:
        from src.Analyse import get_analyse
        get_analyse()
    else:
        print("Nenhuma opção foi selecionada para execução")
        print("Por favor, selecione uma das opções para execução")




