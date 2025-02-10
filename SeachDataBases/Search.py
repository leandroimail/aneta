import os
import yaml
from dotenv import load_dotenv
from config.api_config import *

# Carrega as variáveis do .env
load_dotenv()

# Parâmetros principais
PATH_DATA = os.getenv("PATH_DATA", "/Users/leandro.ferreira/Library/CloudStorage/OneDrive-Pessoal/Projects/python/asrl/Sandbox/Data")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", '("Schema Matching" AND ("Language Model" OR "LLM" OR "Generative AI" OR "GenAI" OR "RAG" OR "Retrieval-Augmented Generation" OR "Retrieval Augmented Generation"))')

# Lê config YAML para definir quais buscas executar
with open(os.path.join(os.path.dirname(__file__), "config/search_config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Orquestração das buscas conforme flags do YAML
if config.get("arxiv", False):
    from arxiv import search as arxiv_search
    arxiv_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("ieee", False):
    from ieee import search as ieee_search
    ieee_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("science_direct", False):
    from science_direct import search as sd_search
    sd_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("scopus", False):
    from scopus import search as scopus_search
    scopus_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("spring_nature", False):
    from spring_nature import search as spring_search
    spring_search.main(SEARCH_QUERY, PATH_DATA)

if config.get("web_of_science", False):
    from web_of_science import search_start as wos_search
    wos_search.main(SEARCH_QUERY, PATH_DATA)

