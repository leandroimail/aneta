from Config import path_SPRINGER, path_ACM, path_directory_bibs
from DonwloadPapers import download_all_papers
import os
from dotenv import load_dotenv
load_dotenv()


bib_file = os.getenv("BIB_FILE", "OUTPUTS/select_bibs.bib")
doi_file = os.environ.get("DOI_FILE", "OUTPUTS/DOIs.txt")
folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "OUTPUTS/PDFs")
path_data = os.getenv("PATH_DATA", "./Sandbox/Data")
path_data = os.path.join(path_data, ".bibs")

bib_file = os.path.join(path_data, bib_file)
doi_file = os.path.join(path_data, doi_file)
folder_save_pdf = os.path.join(path_data, folder_save_pdf)


###################  Informe se deve-se rodar a leitura do abstract (Depreciado)
###################  run_abstract seja falso, rodará a Análise dos Bibtex
run_deprecated_abstract = False

###################  Informe se deve-se rodar o download dos papers
###################  run_download_papers seja falso, rodará a Análise dos Bibtex
run_download_papers = True



if __name__ == "__main__":
    if run_deprecated_abstract:
        from Deprecated.Abstract import get_abstract

        if path_SPRINGER:
            get_abstract(path_SPRINGER, "SPRINGER")
        if path_ACM:
            get_abstract(path_ACM, "ACM")
    elif run_download_papers:
        path_directory_file_bib = os.path.join(path_directory_bibs, bib_file)
        path_directory_file_doi = os.path.join(path_directory_bibs, doi_file)
        folder_save_pdf = os.path.join(path_directory_bibs, folder_save_pdf)
        download_all_papers(path_directory_file_bib, folder_save_pdf, path_directory_file_doi)
    else:
        from Analyse import get_analyse
        get_analyse()




