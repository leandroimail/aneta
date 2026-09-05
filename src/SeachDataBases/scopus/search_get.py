import os
import time
import requests
import json
import re
import sys
import yaml
from dotenv import load_dotenv
import shutil

from src.SeachDataBases.query_language import translate

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

API_KEY = os.getenv("ELSEVIER_API_KEY", "")
BASE_URL = 'https://api.elsevier.com/content/search/scopus'

MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 25))

# View da busca Scopus:
# - STANDARD (padrão): robusta e com paginação profunda, mas NÃO retorna
#   abstract nem author keywords. Tudo bem: o estágio de enriquecimento
#   (--enrich) preenche o abstract por DOI (OpenAlex/Crossref/etc.) antes do
#   filtro/seleção.
# - COMPLETE: retorna abstract e author keywords direto da busca, porém é
#   liberada apenas para as primeiras centenas de resultados (depois retorna
#   401) e tem quota própria menor. Use SCOPUS_VIEW=COMPLETE só se sua
#   assinatura permitir; o loop faz downgrade automático para STANDARD quando
#   a COMPLETE deixa de ser autorizada.
SCOPUS_VIEW = os.getenv("SCOPUS_VIEW", "STANDARD").strip().upper()
if SCOPUS_VIEW not in ("STANDARD", "COMPLETE"):
    SCOPUS_VIEW = "STANDARD"
# O 'count' máximo por página depende do nível de serviço da chave: count>25
# retorna HTTP 400 "Exceeds the maximum number allowed for the service level"
# em chaves comuns (e a view COMPLETE também limita a 25). 25 é o valor
# universalmente seguro, então limitamos a ele.
if PAGE_SIZE > 25:
    PAGE_SIZE = 25
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
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    
    global records_agregados
    
    query = query.strip().replace('\n', ' ').replace('\t', ' ')
    while '  ' in query:
        query = query.replace('  ', ' ')
        
    if not query:
        with open(os.path.abspath("config/search_config.yaml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        query = config.get("search_string", config.get("search_string", None))
        
    if not query:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração config/search_config.yaml não foi definida")
    
    print("Iniciando coleta de registros da API Scopus...\n")

    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json'
    }

    # Traduz a linguagem padrão para TITLE-ABS-KEY(...): título, resumo e
    # palavras-chave. all(...) buscaria também em referências citadas,
    # afiliações, editora etc., inflando os resultados.
    resultado = translate(query, "scopus")
    for aviso in resultado.warnings:
        print(f"[AVISO Scopus] {aviso}")
    query_param = resultado.query
    print(f"Query traduzida para a API Scopus: {query_param}\n")

    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE else 0)
    print(f"Total de páginas estimado: {num_requisicoes} (tamanho da página: {PAGE_SIZE})\n")

    # Quando SCOPUS_VIEW=COMPLETE, a view (abstract + author keywords) costuma
    # ser autorizada só nas primeiras centenas de resultados; ao receber 401
    # na paginação profunda, fazemos downgrade automático para STANDARD e
    # seguimos coletando, em vez de abortar e perder tudo.
    current_view = SCOPUS_VIEW
    view_downgraded = False
    encerrar = False

    for pagina in range(num_requisicoes):
        if encerrar:
            break
        start = pagina * PAGE_SIZE

        max_retries = 3
        sucesso_pagina = False
        for tentativa in range(max_retries):
            params = {
                'query': query_param,
                'start': start,
                'count': PAGE_SIZE,
                'view': current_view,
            }
            print(f"Requisitando página {pagina+1} (start={start}, view={current_view})...")
            try:
                response = requests.get(BASE_URL, headers=headers, params=params, timeout=60)
            except requests.exceptions.RequestException as e:
                print(f"Erro de rede na página {pagina+1}: {e}")
                time.sleep(3 * (tentativa + 1))
                continue

            status = response.status_code

            if status == 200:
                results = response.json().get('search-results', {}).get('entry', [])
                if not results:
                    print("Nenhum resultado encontrado. Encerrando...")
                    encerrar = True
                    sucesso_pagina = True
                    break
                records_agregados.extend(results)
                print(f"Página {pagina+1}: {len(results)} registros recebidos "
                      f"(view={current_view}). Total acumulado: {len(records_agregados)}\n")
                if len(results) < PAGE_SIZE:
                    print("Última página alcançada. Encerrando coleta...")
                    encerrar = True
                sucesso_pagina = True
                break

            if status == 401 and current_view == "COMPLETE":
                # Entitlement da COMPLETE esgotou na paginação profunda:
                # baixa para STANDARD e refaz a MESMA página.
                if not view_downgraded:
                    print("[AVISO Scopus] A view COMPLETE (com abstract) não está "
                          "autorizada além deste ponto; alternando para STANDARD "
                          "(sem abstract) para coletar o restante.\n")
                    view_downgraded = True
                current_view = "STANDARD"
                continue

            if status in (429, 500, 502, 503):
                espera = 5 * (tentativa + 1)
                print(f"Erro temporário {status} na página {pagina+1}. "
                      f"Aguardando {espera}s e tentando novamente...")
                time.sleep(espera)
                continue

            # 401/403 mesmo em STANDARD, ou outro erro não recuperável
            if status in (401, 403):
                print("**************************************************")
                print("*                ERRO DE ACESSO                  *")
                print("**************************************************")
                print("Houve um erro de acesso;\nVerifique se você tem acesso à rede de "
                      "uma instituição conveniada ou esteja na VPN da instituição.")
            print(f"Erro HTTP {status} na página {pagina+1}. Resposta: {response.text[:300]}")
            encerrar = True
            break

        if not sucesso_pagina and not encerrar:
            print(f"Página {pagina+1} falhou após {max_retries} tentativas. "
                  f"Encerrando a coleta e preservando os {len(records_agregados)} "
                  f"registros já obtidos.")
            break

    # Salvando resultados brutos
    if records_agregados:
        try:
            with open(os.path.join(out_dir, "scopus.json"), "w", encoding="utf-8") as f:
                json.dump(records_agregados, f, indent=4, ensure_ascii=False)
            print("Dados brutos salvos em 'scopus.json'\n")
        except Exception as e:
            raise Exception(f"Erro ao salvar JSON: {e}")
        
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
            raise Exception(f"Erro ao gerar BibTeX: {e}")
    else:
        print("Nenhum registro encontrado. Nenhum arquivo gerado.")
    
    # Log final
    total = len(records_agregados)
    print("\n==============================================")
    print("         BUSCA FINALIZADA: SCOPUS             ")
    print(f"       Artigos encontros e adicionados: {total}")
    print("==============================================\n")
