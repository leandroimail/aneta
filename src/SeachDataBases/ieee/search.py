import os
import random
import shutil
import requests
import json
import re
import sys
import yaml
import time  # Adicione esta importação no topo do arquivo
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.abspath("Config/.env"))

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = os.getenv("IEEE_API_KEY", "")
BASE_URL = 'https://ieeexploreapi.ieee.org/api/v1/search/articles'

# Query de pesquisa ajustada para sintaxe IEEE
# QS_QUERY = '("Schema Matching" AND ("Language Model" OR "LLM" OR "Generative AI" OR "GenAI" OR "RAG" OR "Retrieval-Augmented Generation" OR "Retrieval Augmented Generation"))'



MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 50)) 

if PAGE_SIZE < 50:
    PAGE_SIZE = 50

records_agregados = []

# ============================================================
# Funções auxiliares
# ============================== ===============================
def extrai_ano(data_str):
    """Extrai o ano de uma string de data"""
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def converte_para_bibtex(entry):
    """
    Converte um registro da API IEEE para formato BibTeX.
    
    Campos mapeados:
    - authors: Lista de autores (campo 'authors')
    - title: title
    - year: publication_year
    - publication: publication_title
    - doi: doi
    - url: html_url
    - abstract: abstract
    - keywords: index_terms > ieee_terms
    - author_keywords: index_terms > author_terms
    - publisher, isbn, issn, volume, number, pages, source, journal, conference,
      cited_by_count_source, affiliations, autor_orcid, abbrev_source_title, openaccess
    """
    # Autores com verificação do tipo
    authors_list = entry.get('authors', {}).get('authors', [])
    authors = "; ".join([
        (autor.get('full_name', '').strip() if isinstance(autor, dict) else str(autor).strip())
        for autor in authors_list
    ])
    
    # Título
    title = entry.get('title', '').strip().replace('\n', ' ')
    
    # Ano
    year = entry.get('publication_year', '')
    
    # Fonte de publicação
    publication = entry.get('publication_title', '').strip()
    
    # Identificadores e URLs
    doi = entry.get('doi', '').strip()
    url_html = entry.get('html_url', '')
    url_pdf = entry.get('pdf_url', '')
    
    # Campos adicionais
    abstract = entry.get('abstract', '').strip().replace('\n', ' ')
    
    # Palavras-chave
    keywords_old = '; '.join(entry.get('author_terms', {}).get('terms', []) 
                             or [])  # mantido o código antigo se houver
    # Novas tags derivadas de index_terms
    keywords = '; '.join(entry.get('index_terms', {}).get('ieee_terms', {}).get('terms', []))
    author_keywords = '; '.join(entry.get('index_terms', {}).get('author_terms', {}).get('terms', []))
    
    # Outras tags
    publisher = entry.get('publisher', 'IEEE').strip()
    isbn = entry.get('isbn', '').strip()
    issn = entry.get('issn', '').strip()
    volume = entry.get('volume', '').strip()
    number = entry.get('number', '').strip()
    
    # Combina páginas se disponíveis
    start_page = entry.get('start_page', '').strip()
    end_page = entry.get('end_page', '').strip()
    pages = f"{start_page}--{end_page}" if start_page and end_page else ""
    
    source = publication
    journal = entry.get('journal', '').strip()
    conference = entry.get('conference_location', '').strip()
    cited_by_count_source = str(entry.get('citing_paper_count', ''))
    
    # Extrai as afiliações únicas dos autores
    affiliations_list = []
    for autor in authors_list:
        if isinstance(autor, dict):
            aff = autor.get('affiliation', '').strip()
            if aff and aff not in affiliations_list:
                affiliations_list.append(aff)
    affiliations = '; '.join(affiliations_list)
    
    # Outros campos
    autor_orcid = entry.get('orcid', '').strip()  # se disponível
    abbrev_source_title = entry.get('abbrev_source_title', '').strip()
    openaccess = "true" if entry.get('openaccess', False) else "false"
    
    # Gera chave BibTeX
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
        
    type_publication = entry.get('content_type', '').strip()
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  publication = {{{publication}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{url_html}}},\n"
        f"  url_pdf = {{{url_pdf}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  type_publication = {{{type_publication}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  isbn = {{{isbn}}},\n"
        f"  issn = {{{issn}}},\n"
        f"  volume = {{{volume}}},\n"
        f"  number = {{{number}}},\n"
        f"  pages = {{{pages}}},\n"
        f"  source = {{{source}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  conference = {{{conference}}},\n"
        f"  keywords = {{{keywords}}},\n"
        f"  author_keywords = {{{author_keywords}}},\n"
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
    global records_agregados
    
    if int(os.getenv("PAGE_SIZE", 50)) < 50:
        print("Tamanho da página ajustado para 50")
    
    # Log inicial melhorado
    print("\n==============================================")
    print("         INICIANDO BUSCA: IEEE Xplore         ")
    print("==============================================\n")
    
    if not query:
        with open(os.path.abspath("Config/search_config.yaml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        query = config.get("search_string", config.get("search_string", None)) 
    if not query:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração Config/search_config.yaml não foi definida")
    
    query = query.strip().replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').replace('  ', ' ')
    
    out_dir = os.path.join(path_data, "ieee")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    
    print("Iniciando coleta de registros da API IEEE Xplore...\n")
    
    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE else 0)
    print(f"Total de páginas estimado: {num_requisicoes} (tamanho da página: {PAGE_SIZE})\n")
    
    pagina = 0
    ultima_pagina_alcancada = False
    
    while pagina < num_requisicoes and not ultima_pagina_alcancada:
        start_record = (pagina * PAGE_SIZE) + 1
        
        params = {
            'querytext': query,
            'start_record': start_record,
            'max_records': PAGE_SIZE,
            'apikey': API_KEY
        }
        
        max_retries = 3
        retry_delay = 5  # segundos
        
        for tentativa in range(max_retries):
            print(f"Requisitando página {pagina+1} (start_record={start_record})... Tentativa {tentativa + 1}")
            
            try:
                # Adiciona delay entre requisições
                if pagina > 0 or tentativa > 0:
                    random_retry_delay = random.randint(5, 10)
                    print(f"Aguardando {random_retry_delay} segundos antes da próxima requisição...")
                    time.sleep(random_retry_delay)
                
                response = requests.get(BASE_URL, params=params)
                
                # Verifica se é erro 418 ou outro erro
                if response.status_code == 418:
                    if tentativa < max_retries - 1:
                        print("Servidor detectou muitas requisições. Aguardando antes de tentar novamente...")
                        time.sleep(retry_delay * 2)  # Aguarda mais tempo para erro 418
                        retry_delay += 1  # Aumenta o delay para a próxima tentativa
                        continue
                
                response.raise_for_status()
                data = response.json()
                
                if not data.get('articles'):
                    print("Nenhum resultado encontrado. Encerrando...")
                    ultima_pagina_alcancada = True
                    break
                    
                results = data['articles']
                records_agregados.extend(results)
                print(f"Página {pagina+1}: {len(results)} registros recebidos. Total acumulado: {len(records_agregados)}\n")
                
                if len(results) < PAGE_SIZE:
                    print("Última página alcançada. Encerrando coleta...")
                    ultima_pagina_alcancada = True
                
                # Se chegou aqui, a requisição foi bem sucedida
                break
                
            except requests.exceptions.HTTPError as errh:
                print(f"Erro HTTP: {errh}")
                print(f"Resposta: {response.text}")
                if tentativa == max_retries - 1:
                    raise Exception("Máximo de tentativas excedido para IEEE. Encerrando...")
            except requests.exceptions.ConnectionError as errc:
                print(f"Erro de conexão: {errc}")
                if tentativa == max_retries - 1:
                    raise Exception("Máximo de tentativas excedido para IEEE. Encerrando...")
            except requests.exceptions.Timeout as errt:
                print(f"Tempo de requisição esgotado: {errt}")
                if tentativa == max_retries - 1:
                    raise Exception("Máximo de tentativas excedido para IEEE. Encerrando...")
            except Exception as e:
                if tentativa == max_retries - 1:
                    raise Exception(f"Erro na requisição: {e}")

        # Incrementa o contador de página após cada requisição bem-sucedida
        pagina += 1

    # Salvando resultados brutos
    if records_agregados:
        try:
            with open(os.path.join(out_dir, 'ieee.json'), 'w', encoding='utf-8') as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'ieee.json'")
        except Exception as e:
            raise Exception(f"Erro ao salvar JSON: {e}")
        
        # Convertendo para BibTeX
        try:
            with open(os.path.join(out_dir, 'ieee.bib'), 'w', encoding='utf-8') as f:
                bibtex_entries = [converte_para_bibtex(r) for r in records_agregados]
                f.write('\n'.join(bibtex_entries))
            print("Arquivo BibTeX gerado: 'ieee.bib'")
        except Exception as e:
            raise Exception(f"Erro ao gerar BibTeX: {e}")
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")
    
    # Log final
    print("\n==============================================")
    print("         BUSCA FINALIZADA: IEEE Xplore          ")
    print(f"      Artigos encontrados e adicionados: {len(records_agregados)}")
    print("==============================================\n")
