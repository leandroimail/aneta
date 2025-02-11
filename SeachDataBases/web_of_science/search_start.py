from dotenv import load_dotenv
import os
import requests
import json
import re
import sys

load_dotenv()

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = os.getenv("WEB_OF_SCIENCE_KEY", "")
BASE_URL = 'https://api.clarivate.com/apis/wos-starter/v1/documents'

RESULTS_DESEJADOS = 500
PAGE_SIZE = 25  # WoS permite até 50 por página, mas usaremos 25 para consistência
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
    Converte um registro da API WoS para formato BibTeX.
    
    Campos mapeados:
    - authors: Lista de autores (campo 'names.authors')
    - title: title
    - year: source.publishYear
    - publication: source.sourceTitle
    - doi: identifiers.doi
    - url_html: links.record
    - abstract: Não disponível na API WoS Starter
    - keywords: keywords.authorKeywords
    - type_publication: types
    """
    # Autores
    authors_list = entry.get('names', {}).get('authors', [])
    authors = "; ".join([
        author.get('displayName', '').strip()
        for author in authors_list
    ])
    
    # Título
    title = entry.get('title', '').strip().replace('\n', ' ')
    
    # Data e ano
    publication_year = entry.get('source', {}).get('publishYear', '')
    year = publication_year if publication_year else ""
    
    # Fonte de publicação
    publication = entry.get('source', {}).get('sourceTitle', '').strip()
    
    # Identificadores
    doi = entry.get('identifiers', {}).get('doi', '').strip()
    
    # URL
    url = entry.get('links', {}).get('record', '').strip()
    
    # Campos adicionais
    abstract = ""  # Não disponível na API WoS Starter
    keywords = '; '.join(entry.get('keywords', {}).get('authorKeywords', []))
    type_publication = entry.get('types', [])
    if type_publication:
        type_publication = type_publication[0]
    publisher = ""  # Não disponível na resposta WoS Starter
    
    # Gera chave BibTeX
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  keywords = {{{keywords}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  type_publication = {{{type_publication}}},\n"
        f"  publication = {{{publication}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{url}}}\n"
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
        query = os.getenv("SEARCH_QUERY", "")
        
    # Cria a pasta específica para Web of Science dentro do path_data
    out_dir = os.path.join(path_data, "web_of_science")
    os.makedirs(out_dir, exist_ok=True)
    
    global records_agregados
    headers = {
        'X-ApiKey': API_KEY,
        'Accept': 'application/json'
    }
    
    print("Query:", query)
    print("Path Data:", path_data)
    
    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE else 0)
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
            sys.exit(1)
        except Exception as e:
            print(f"Erro na requisição: {e}")
            sys.exit(1)
    
    # Salvando resultados brutos no diretório criado
    if records_agregados:
        try:
            with open(os.path.join(out_dir, 'wos.json'), 'w', encoding='utf-8') as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'wos.json'")
        except Exception as e:
            print(f"Erro ao salvar JSON: {e}")
            sys.exit(1)
        
        # Convertendo para BibTeX e salvando no diretório criado
        try:
            with open(os.path.join(out_dir, 'wos.bib'), 'w', encoding='utf-8') as f:
                bibtex_entries = [converte_para_bibtex(r) for r in records_agregados]
                f.write('\n'.join(bibtex_entries))
            print("Arquivo BibTeX gerado: 'wos.bib'")
        except Exception as e:
            print(f"Erro ao gerar BibTeX: {e}")
            sys.exit(1)
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")
    
    # Log final com total de artigos encontros e adicionados:
    print("\n==============================================")
    print("     BUSCA FINALIZADA: WEB OF SCIENCE         ")
    print(f"   Artigos encontros e adicionados: {len(records_agregados)}")
    print("==============================================\n")

# ============================================================
# Execução principal
# ============================================================
if __name__ == "__main__":
    QUERY = sys.argv[1] if len(sys.argv) > 1 else ""
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else ""
    main(QUERY, PATH_DATA)