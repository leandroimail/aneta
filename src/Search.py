import os
import yaml
from dotenv import load_dotenv
from src.SeachDataBases.arxiv import search as arxiv_search
from src.SeachDataBases.ieee import search as ieee_search
from src.SeachDataBases.science_direct import search_metadata as sd_search
from src.SeachDataBases.spring_nature import search as spring_search
from src.SeachDataBases.web_of_science import search_start as wos_search
from SeachDataBases.scopus import search_get as scopus_search
# from SeachDataBases.scopus import search as scopus_search

# Carrega as variáveis do .env
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))

def run_search():
    # Parâmetros principais
    PATH_DATA = os.path.abspath(os.getenv("PATH_DATA", "Data"))
    PATH_DATA = os.path.join(PATH_DATA, ".bibs")

    # Lê config YAML para definir quais buscas executar
    with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    SEARCH_STRING = config.get("search_string", config.get("search_string", None))    

    if not SEARCH_STRING:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração Config/search_config.yaml não foi definida")

    # Orquestração das buscas conforme flags do YAML
    if config.get("arxiv", False):
        arxiv_search.main(SEARCH_STRING, PATH_DATA)

    if config.get("science_direct", False):    
        sd_search.main(SEARCH_STRING, PATH_DATA)

    if config.get("scopus", False):    
        scopus_search.main(SEARCH_STRING, PATH_DATA)

    if config.get("spring_nature", False):    
        spring_search.main(SEARCH_STRING, PATH_DATA)

    if config.get("web_of_science", False):    
        wos_search.main(SEARCH_STRING, PATH_DATA)

    if config.get("ieee", False):    
        ieee_search.main(SEARCH_STRING, PATH_DATA)

    print("\n\n++++++++++++++++++++++++++++++++++++++++++++++")
    print("     Search process completed successfully!")
    print("++++++++++++++++++++++++++++++++++++++++++++++ \n\n")