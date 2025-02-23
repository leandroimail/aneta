import os
import yaml
from dotenv import load_dotenv
from SeachDataBases.arxiv import search as arxiv_search
from SeachDataBases.ieee import search as ieee_search
from SeachDataBases.science_direct import search_metadata as sd_search
from SeachDataBases.scopus import search as scopus_search
from SeachDataBases.spring_nature import search as spring_search
from SeachDataBases.web_of_science import search_start as wos_search

# Carrega as variáveis do .env
load_dotenv()

# Parâmetros principais
PATH_DATA = os.getenv("PATH_DATA", "./Sandbox/Data")
PATH_DATA = os.path.join(PATH_DATA, ".bibs")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", '')

if not SEARCH_QUERY:
    raise ValueError("SEARCH_QUERY não foi definido no .env.")

# Lê config YAML para definir quais buscas executar
with open(os.path.join(os.path.dirname(__file__), "config/search_config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Orquestração das buscas conforme flags do YAML
if config.get("arxiv", False):
    arxiv_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("science_direct", False):    
    sd_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("scopus", False):    
    scopus_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("ieee", False):    
    ieee_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("spring_nature", False):    
    spring_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("web_of_science", False):    
    wos_search.main(SEARCH_QUERY, PATH_DATA)

print("\n\n++++++++++++++++++++++++++++++++++++++++++++++")
print("     Search process completed successfully!")
print("++++++++++++++++++++++++++++++++++++++++++++++ \n\n")