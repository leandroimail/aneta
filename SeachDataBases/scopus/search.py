import requests
import json
import re
import sys

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = "e795e9dbd2edeb1081126a218f52f693"
BASE_URL = 'https://api.elsevier.com/content/search/scopus'

# Query de pesquisa (ajustada para sintaxe Scopus)
QS_QUERY = '"Schema Matching" AND ("Language Model" OR "LLM" OR "Generative AI" OR "GenAI" OR "RAG" OR "Retrieval-Augmented Generation" OR "Retrieval Augmented Generation")'

RESULTS_DESEJADOS = 500
PAGE_SIZE = 25  # Scopus geralmente permite até 25 por página
records_agregados = []

# ============================================================
# Funções auxiliares
# ============================================================
def extrai_ano(data_str):
    """Extrai o ano de uma data no formato Scopus (YYYY-MM-DD)"""
    if data_str:
        match = re.search(r'^(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def converte_para_bibtex(entry):
    """
    Converte um registro da API Scopus para formato BibTeX.
    
    Campos mapeados:
    - authors: Lista de autores (campo 'author')
    - title: dc:title
    - year: prism:coverDate
    - publication: prism:publicationName
    - doi: prism:doi
    - url: link com @ref='scopus'
    - abstract: dc:description
    - keywords: authkeywords (separados por |)
    - type_publication: subtypeDescription
    """
    # Autores
    authors_list = entry.get('author', [])
    authors = "; ".join([
        f"{autor.get('given-name', '')} {autor.get('surname', '')}".strip()
        for autor in authors_list
        if autor.get('given-name') or autor.get('surname')
    ])
    
    # Título
    title = entry.get('dc:title', '').strip().replace('\n', ' ')
    
    # Data e ano
    publication_date = entry.get('prism:coverDate', '')
    year = extrai_ano(publication_date)
    
    # Fonte de publicação
    publication = entry.get('prism:publicationName', '').strip()
    
    # Identificadores
    doi = entry.get('prism:doi', '').strip()
    
    # URL
    url = next((link['@href'] for link in entry.get('link', []) 
               if link.get('@ref') == 'scopus'), '')
    
    # Campos adicionais
    abstract = entry.get('dc:description', '').strip().replace('\n', ' ')
    keywords = '; '.join(entry.get('authkeywords', '').strip().split('|'))
    type_publication = entry.get('subtypeDescription', 'Article').strip()
    publisher = ""  # Não disponível na resposta Scopus
    
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
def main():
    global records_agregados
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }
    
    print("Iniciando coleta de registros da API Scopus...\n")
    
    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE else 0)
    print(f"Total de páginas estimado: {num_requisicoes} (tamanho da página: {PAGE_SIZE})\n")
    
    query = f"TITLE-ABS-KEY({QS_QUERY})"
    
    for pagina in range(num_requisicoes):
        start = pagina * PAGE_SIZE
        params = {
            'query': query,
            'start': start,
            'count': PAGE_SIZE,
            'view': 'COMPLETE',  # Para obter todos os campos necessários
            'httpAccept': 'application/json'
        }
        
        print(f"Requisitando página {pagina+1} (start={start})...")
        
        try:
            response = requests.get(BASE_URL, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('search-results', {}).get('entry', [])
            
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
    
    # Salvando resultados brutos
    if records_agregados:
        try:
            with open('scopus.json', 'w', encoding='utf-8') as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'scopus.json'")
        except Exception as e:
            print(f"Erro ao salvar JSON: {e}")
            sys.exit(1)
        
        # Convertendo para BibTeX
        try:
            with open('scopus.bib', 'w', encoding='utf-8') as f:
                bibtex_entries = [converte_para_bibtex(r) for r in records_agregados]
                f.write('\n'.join(bibtex_entries))
            print("Arquivo BibTeX gerado: 'scopus.bib'")
        except Exception as e:
            print(f"Erro ao gerar BibTeX: {e}")
            sys.exit(1)
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")

# ============================================================
# Execução principal
# ============================================================
if __name__ == "__main__":
    main()