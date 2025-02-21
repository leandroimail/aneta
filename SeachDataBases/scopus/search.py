import os
import requests
import json
import re
import sys
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELSEVIER_API_KEY", "")
BASE_URL = 'https://api.elsevier.com/content/search/scopus'

MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 25))
records_agregados = []

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
    - authors, title, year, publication, doi, url, abstract, etc.
    Novas tags:
      publisher, isbn, issn, volume, number, pages, source, journal, conference,
      keywords (de publisher ou journal), author_keywords, cited_by_count_source,
      affiliations, autor_orcid, abbrev_source_title, openaccess
    """
    # Autores
    authors_list = entry.get('author', [])
    authors = "; ".join([
        f"{autor.get('given-name', '')} {autor.get('surname', '')}".strip()
        for autor in authors_list
        if autor.get('given-name') or autor.get('surname')
    ])
    
    # Título e data
    title = entry.get('dc:title', '').strip().replace('\n', ' ')
    publication_date = entry.get('prism:coverDate', '')
    year = extrai_ano(publication_date)
    
    # Publicação
    publication = entry.get('prism:publicationName', '').strip()
    
    # Identificadores e URL
    doi = entry.get('prism:doi', '').strip()
    url = next((link['@href'] for link in entry.get('link', []) 
                if link.get('@ref') == 'scopus'), '')
    
    # Campos adicionais
    abstract = entry.get('dc:description', '').strip().replace('\n', ' ')
    keywords_auth = '; '.join(entry.get('authkeywords', '').strip().split('|'))
    type_publication = entry.get('subtypeDescription', '').strip()
    
    # Novas tags extraídas do JSON
    publisher = entry.get('publisher', '')
    isbn = entry.get('prism:isbn', [""])[0]
    if isbn:
        isbn =  str(isbn.get('$', [""])).replace("'", "").replace("[", "").replace("]", "")
    issn = entry.get('prism:issn', '') or entry.get('prism:eIssn', '')
    volume = entry.get('prism:volume', '')
    number = entry.get('prism:issueIdentifier', '')
    pages = entry.get('prism:pageRange', '')
    source = entry.get('source-id', '')
    journal = publication if entry.get('prism:aggregationType', '').lower() == 'journal' else ''
    conference = publication if (entry.get('prism:aggregationType', '').lower() == 'conference proceeding' or 
                                 entry.get('subtypeDescription', '').lower() == 'conference paper') else ''
    keywords_pub = entry.get('prism:keyword', '')
    cited_by_count_source = entry.get('citedby-count', '')
    affiliations = "; ".join(
        ", ".join(filter(None, [aff.get("affilname", ""), aff.get("affiliation-city", ""), aff.get("affiliation-country", "")]))
        for aff in entry.get("affiliation", [])
        if any([aff.get("affilname", ""), aff.get("affiliation-city", ""), aff.get("affiliation-country", "")])
    )
    autor_orcid = entry.get('orcid', '')
    abbrev_source_title = ""
    openaccess = "true" if entry.get('openaccessFlag', False) or entry.get('openaccess', '0') == "1" else "false"
    
    # Gera chave BibTeX
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  author_keywords = {{{keywords_auth}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  type_publication = {{{type_publication}}},\n"
        f"  publication = {{{publication}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  isbn = {{{isbn}}},\n"
        f"  issn = {{{issn}}},\n"
        f"  volume = {{{volume}}},\n"
        f"  number = {{{number}}},\n"
        f"  pages = {{{pages}}},\n"
        f"  source = {{{source}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  conference = {{{conference}}},\n"
        f"  keywords = {{{keywords_pub}}},\n"
        f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
        f"  affiliations = {{{affiliations}}},\n"
        f"  autor_orcid = {{{autor_orcid}}},\n"
        f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
        f"  openaccess = {{{openaccess}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{url}}}\n"
        f"}}\n"
    )
    return bibtex_entry

def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("         INICIANDO BUSCA: SCOPUS              ")
    print("==============================================\n")
    
    out_dir = os.path.join(path_data, "scopus")
    os.makedirs(out_dir, exist_ok=True)
    global records_agregados
    
    print("Iniciando coleta de registros da API Scopus...\n")
    # Use o parâmetro "query" para construir a requisição, por exemplo:
    query_param = f"TITLE-ABS-KEY({query})"
    
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }
    
    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE else 0)
    print(f"Total de páginas estimado: {num_requisicoes} (tamanho da página: {PAGE_SIZE})\n")
    
    for pagina in range(num_requisicoes):
        start = pagina * PAGE_SIZE
        params = {
            'query': query_param,
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
                if response.status_code in [401, 403]:
                    print("**************************************************")
                    print("*                ERRO DE ACESSO                  *")
                    print("**************************************************")
                    print("Houve um erro de acesso;\nVerifique se você tem acesso à rede de uma instituição conveniada ou esteja na VPN da instituição.")
                    break
                print("Nenhum resultado encontrado. Encerrando...")
                break
                
            records_agregados.extend(results)
            print(f"Página {pagina+1}: {len(results)} registros recebidos. Total acumulado: {len(records_agregados)}\n")
            
            if len(results) < PAGE_SIZE:
                print("Última página alcançada. Encerrando coleta...")
                break
                
        except requests.exceptions.HTTPError as errh:
            if errh.response is not None and errh.response.status_code in [401, 403]:
                print("**************************************************")
                print("*                ERRO DE ACESSO                  *")
                print("**************************************************")
                print("Houve um erro de acesso;\nVerifique se você tem acesso à rede de uma instituição conveniada ou esteja na VPN da instituição.")
            print(f"Erro HTTP: {errh}")
            print(f"Resposta: {response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"Erro na requisição: {e}")
            sys.exit(1)
    
    # Salvando resultados brutos
    if records_agregados:
        try:
            with open(os.path.join(out_dir, "scopus.json"), "w", encoding="utf-8") as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'scopus.json'\n")
        except Exception as e:
            print(f"Erro ao salvar JSON: {e}")
            sys.exit(1)
        
        # Convertendo para BibTeX
        try:
            with open(os.path.join(out_dir, "scopus.bib"), "w", encoding="utf-8") as f:
                bibtex_entries = []
                for r in records_agregados:
                    if isinstance(r, dict):
                        entry = converte_para_bibtex(r)
                        # Garante entrada string
                        bibtex_entries.append(entry if isinstance(entry, str) else str(entry))
                    else:
                        bibtex_entries.append(str(r))
                f.write('\n'.join(bibtex_entries))
            print("Arquivo BibTeX gerado: 'scopus.bib'")
        except Exception as e:
            print(f"Erro ao gerar BibTeX: {e}")
            sys.exit(1)
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")
    
    # Log final
    total = len(records_agregados)
    print("\n==============================================")
    print("         BUSCA FINALIZADA: SCOPUS             ")
    print(f"       Artigos encontros e adicionados: {total}")
    print("==============================================\n")

if __name__ == "__main__":
    import sys
    QUERY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEARCH_QUERY", "")
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATH_DATA", "../Sandbox/Data")
    PATH_DATA = os.path.join(PATH_DATA, ".bibs")
    main(QUERY, PATH_DATA)