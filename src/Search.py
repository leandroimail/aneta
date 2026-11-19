import os
import yaml
from src.SearchCache import cached_search
from dotenv import load_dotenv
from src.SeachDataBases.arxiv import search as arxiv_search
from src.SeachDataBases.ieee import search as ieee_search
from src.SeachDataBases.science_direct import search_metadata as sd_search
from src.SeachDataBases.spring_nature import search as spring_search
from src.SeachDataBases.web_of_science import search_start as wos_search
from src.SeachDataBases.scopus import search_get as scopus_search

# Carrega as variáveis do .env
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

def run_search():
    # Parâmetros principais
    PATH_DATA = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    PATH_DATA = os.path.join(PATH_DATA, ".bibs")

    # Lê config YAML para definir quais buscas executar
    with open(os.path.abspath("config/search_config.yaml"), "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    SEARCH_STRING = config.get("search_string")

    if not SEARCH_STRING:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração config/search_config.yaml não foi definida")

    # Orquestração das buscas conforme flags do YAML
    providers = {
        "arxiv": arxiv_search, "science_direct": sd_search, "scopus": scopus_search,
        "spring_nature": spring_search, "web_of_science": wos_search, "ieee": ieee_search,
    }
    for source, provider in providers.items():
        if config.get(source, False):
            cached_search(source, provider, SEARCH_STRING, PATH_DATA)

    print("\n\n++++++++++++++++++++++++++++++++++++++++++++++")
    print("     Search process completed successfully!")
    print("++++++++++++++++++++++++++++++++++++++++++++++ \n\n")