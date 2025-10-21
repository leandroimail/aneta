import shutil
from dotenv import load_dotenv
import os
import requests
import json
import re
import sys
import yaml

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = os.getenv("WEB_OF_SCIENCE_KEY", "")
BASE_URL = 'https://api.clarivate.com/apis/wos-starter/v1/documents'

MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))  
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 25))
records_agregados = []

# ============================================================
# Funções auxiliares
# ============================================================
def extrai_ano(data_str):
    """Extrai o ano de uma data no formato WoS (YYYY-MM-DD)"""
    if data_str:
        match = re.search(r'^(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def converte_para_bibtex(entry):
    """
    Converte um registro da API WoS para formato BibTeX, incluindo novas tags.
    
    Campos mapeados:
    - authors: Lista de autores (campo 'names.authors')
    - title: Título
    - year: source.publishYear
    - type_publication: types
    - publication: source.sourceTitle
    - doi: identifiers.doi
    - url_html: links.record
    - abstract: Não disponível na API WoS Starter
    - publisher, isbn, issn, volume, number, pages, source,
      journal, conference, keywords (publisher ou journal),
      author_keywords, cited_by_count_source, affiliations,
      autor_orcid, abbrev_source_title, openaccess
    """
    # Autores
    authors_list = entry.get('names', {}).get('authors', [])
    authors = "; ".join([
        author.get('displayName', '').strip()
        for author in authors_list
    ])
    
    # Título
    title = entry.get('title', '').strip().replace('\n', ' ')
    
    # Ano de publicação
    publication_year = entry.get('source', {}).get('publishYear', '')
    year = publication_year if publication_year else ""
    
    # Fonte de publicação (sourceTitle)
    source_title = entry.get('source', {}).get('sourceTitle', '').strip()
    publication = source_title
    
    # Identificadores
    doi = entry.get('identifiers', {}).get('doi', '').strip()
    
    # URL do registro
    url = entry.get('links', {}).get('record', '').strip()
    
    # Campo já existente
    abstract = ""  # Não disponível na API WoS Starter
    keywords_original = entry.get('keywords', {}).get('authorKeywords', [])
    author_keywords = '; '.join(keywords_original)
    
    # Novas tags adicionais
    publisher = entry.get('source', {}).get('publisher', '')
    
    isbn = entry.get('identifiers', {}).get('isbn', '')
    if not isbn:
        isbn = entry.get('identifiers', {}).get('eisbn', '')
    issn = entry.get('identifiers', {}).get('issn', '')
    
    volume = entry.get('source', {}).get('volume', '')
    number = entry.get('source', {}).get('issue', '')
    
    pages_data = entry.get('source', {}).get('pages', {})
    pages = pages_data.get('range', '') if 'range' in pages_data else ""
    
    # Determina o tipo de publicação e atribui journal ou conference
    type_publication_list = entry.get('sourceTypes', [])
    type_publication = type_publication_list[0] if type_publication_list else ""
    
    if type_publication == "Article":
        journal = source_title
        conference = ""
    elif type_publication in ["Meeting", "Proceedings Paper", "Proceedings Paper"]:
        conference = source_title
        journal = ""
    else:
        journal = ""
        conference = ""
    
    # Keywords referentes ao publisher ou journal (não disponível na API; deixado em branco)
    key_words_publisher = ""
    
    # Valor padrão para tags não disponíveis
    cited_by_count_source = 0  # Valor padrão, pois não há informação
    affiliations = ""  # Não disponível na API WoS Starter
    autor_orcid = ""   # Não disponível na API WoS Starter
    
    # Abreviação do título da fonte
    abbrev_source_title = ''.join([word[0].upper() for word in source_title.split()]) if source_title else ""
    
    # Openaccess, valor padrão
    openaccess = "false"
    
    # Gera chave BibTeX
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  author_keywords = {{{author_keywords}}},\n"
        f"  keywords = {{{key_words_publisher}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  type_publication = {{{type_publication}}},\n"
        f"  publication = {{{publication}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{url}}},\n"
        f"  isbn = {{{isbn}}},\n"
        f"  issn = {{{issn}}},\n"
        f"  volume = {{{volume}}},\n"
        f"  number = {{{number}}},\n"
        f"  pages = {{{pages}}},\n"
        f"  source = {{{source_title}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  conference = {{{conference}}},\n"
        f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
        f"  affiliations = {{{affiliations}}},\n"
        f"  autor_orcid = {{{autor_orcid}}},\n"
        f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
        f"  openaccess = {{{openaccess}}}\n"
        f"}}\n"
    )
    return bibtex_entry

# ============================================================
# Função principal
# ============================================================
def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("        INICIANDO BUSCA: WEB OF SCIENCE       ")
    print("==============================================\n")
    
    # Se não houver query, utiliza a variável de ambiente SEARCH_QUERY
    if not query:
        with open(os.path.abspath("config/search_config.yaml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        query = config.get("search_string", config.get("search_string", None)) 
        
    if not query:
        raise ValueError("A string de busca que deve ser declarada em 'search_string' no arquivo de configuração config/search_config.yaml não foi definida")
    
    # Cria a pasta específica para Web of Science dentro do path_data
    out_dir = os.path.join(path_data, "web_of_science")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    
    global records_agregados
    headers = {
        'X-ApiKey': API_KEY,
        'Accept': 'application/json'
    }
    
    query = query.strip().replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').replace('  ', ' ')
    
    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE else 0)
    print(f"Total de páginas estimado: {num_requisicoes} (tamanho da página: {PAGE_SIZE})\n")
    
    # Utiliza a query passada como parâmetro na composição da consulta
    query = f"TS=({query})"  # TS = Topic Search
    for pagina in range(num_requisicoes):
        start = pagina * PAGE_SIZE
        params = {
            'q': query,
            'limit': PAGE_SIZE,
            'page': pagina + 1,
            'db': 'WOS'  # Web of Science Core Collection
        }
        
        print(f"Requisitando página {pagina+1} (start={start})...")
        
        try:
            response = requests.get(BASE_URL, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('hits', [])
            
            if not results:
                print("Nenhum resultado encontrado. Encerrando...")
                break
                
            records_agregados.extend(results)
            print(f"Página {pagina+1}: {len(results)} registros recebidos. Total acumulado: {len(records_agregados)}\n")
            
            if len(results) < PAGE_SIZE:
                print("Última página alcançada. Encerrando coleta...")
                break
                
        except requests.exceptions.HTTPError as errh:
            print(f"Erro HTTP: {errh}")
            print(f"Resposta: {response.text}")
            raise Exception(f"Erro HTTP: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Erro de conexão: {errc}")
            raise Exception(f"Erro de conexão: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout: {errt}")
            raise Exception(f"Timeout   : {errt}")
        except Exception as e:
            raise Exception(f"Erro na requisição: {e}")
    
    # Salvando resultados brutos no diretório criado
    if records_agregados:
        try:
            with open(os.path.join(out_dir, 'wos.json'), 'w', encoding='utf-8') as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'wos.json'")
        except Exception as e:
            raise Exception(f"Erro ao salvar JSON: {e}")
        
        # Convertendo para BibTeX e salvando no diretório criado
        try:
            with open(os.path.join(out_dir, 'wos.bib'), 'w', encoding='utf-8') as f:
                bibtex_entries = [converte_para_bibtex(r) for r in records_agregados]
                f.write('\n'.join(bibtex_entries))
            print("Arquivo BibTeX gerado: 'wos.bib'")
        except Exception as e:
            raise Exception(f"Erro ao gerar BibTeX: {e}")
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")
    
    # Log final com total de artigos encontros e adicionados:
    print("\n==============================================")
    print("     BUSCA FINALIZADA: WEB OF SCIENCE         ")
    print(f"   Artigos encontros e adicionados: {len(records_agregados)}")
    print("==============================================\n")

