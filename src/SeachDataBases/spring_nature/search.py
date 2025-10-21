import requests
import json
import re
import sys
import os
import yaml
from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

# Obtém a chave e removemos a constante fixa
API_KEY = os.getenv("SPRINGER_API_KEY", "")
BASE_URL = 'https://api.springernature.com/meta/v2/json'

MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 500))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", 25))
if PAGE_SIZE > 25:
    PAGE_SIZE = 25


records_agregados = []

def extrai_ano(data_str):
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""

def converte_para_bibtex(record):
    # Obtém autores
    authors_list = record.get('creators', [])
    authors = "; ".join([creator['creator'] for creator in authors_list])
    
    # Processa as keywords já existentes
    keywords_original = record.get('subjects', '')
    if isinstance(keywords_original, list):
        journal_keywords = "; ".join(keywords_original)
    elif isinstance(keywords_original, str):
        journal_keywords = keywords_original.strip()
    else:
        journal_keywords = ""
    
    # Novas tags: tenta obter do record ou deixa vazio se não existir
    isbn = record.get("isbn", record.get("printIsbn", ""))
    issn = record.get("issn", "")
    volume = record.get("volume", "")
    number = record.get("number", "")
    starting_page = record.get("startingPage", "")
    ending_page = record.get("endingPage", "")
    pages = f"{starting_page}--{ending_page}" if starting_page and ending_page else ""
    source = record.get("source", "")
    author_keywords = record.get('keyword', '')
    if isinstance(author_keywords, list):
        author_keywords = "; ".join(author_keywords)
    
    cited_by_count_source = record.get("cited_by_count_source", "")
    affiliations = record.get("affiliations", "")
    autor_orcid = record.get("autor_orcid", "")
    abbrev_source_title = record.get("abbrev_source_title", "")
    openaccess = record.get("openaccess", "").lower()
    
    abstract = record.get('abstract', '').strip()
    title = record.get('title', '').strip()
    cover_date = record.get('publicationDate', '')
    year = extrai_ano(cover_date)
    type_publication = record.get('contentType', '').strip()

    journal = ""
    if "article" in  type_publication.lower():
        journal = record.get("publicationName", "")

    conference = record.get("conferenceInfo", [])
    if conference:
        conference = conference[0].get("confSeriesName", "")
    else:
        conference = ""
    conf_abrev = record.get("conferenceInfo", [])
    if conf_abrev:
        conf_abrev = conf_abrev[0].get("confEventAbbreviation", "")
    else:
        conf_abrev = ""
        
    if conference and conf_abrev:
        conference = f"{conference} - {conf_abrev}"

    publication = record.get('publicationName', '').strip()
    publisher = record.get('publisherName', '').strip()  # Nome da editora responsável pela publicação
    doi = record.get('doi', '').strip()

    # Extrai as URLs para PDF e HTML, se disponíveis
    url_pdf = ""
    url_html = ""
    urls = record.get("url", [])
    if isinstance(urls, list):
        for link in urls:
            if isinstance(link, dict):
                fmt = link.get("format", "").lower()
                if fmt == "pdf":
                    url_pdf = link.get("value", "")
                elif fmt == "html":
                    url_html = link.get("value", "")
    
    # Cria uma chave única para o BibTeX; utiliza o DOI se disponível, senão utiliza parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    # Cria a entrada BibTeX com as novas tags
    if type_publication == "Chapter ConferencePaper":
        bibtex_entry = (
            f"@inproceedings{{{bibtex_key},\n"
            f"  authors = {{{authors}}},\n"
            f"  keywords = {{}},\n"
            f"  author_keywords = {{{journal_keywords}}},\n"
            f"  abstract = {{{abstract}}},\n"
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
            f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
            f"  affiliations = {{{affiliations}}},\n"
            f"  autor_orcid = {{{autor_orcid}}},\n"
            f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
            f"  doi = {{{doi}}},\n"
            f"  url_pdf = {{{url_pdf}}},\n"
            f"  url_html = {{{url_html}}},\n"
            f"  openaccess = {{{openaccess}}}\n"
            f"}}\n"
        )
    else:  # Default para tipo "Article"
        bibtex_entry = (
            f"@article{{{bibtex_key},\n"
            f"  authors = {{{authors}}},\n"
            f"  keywords = {{{journal_keywords}}},\n"
            f"  author_keywords = {{{author_keywords}}},\n"
            f"  abstract = {{{abstract}}},\n"
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
            f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
            f"  affiliations = {{{affiliations}}},\n"
            f"  autor_orcid = {{{autor_orcid}}},\n"
            f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
            f"  doi = {{{doi}}},\n"
            f"  url_pdf = {{{url_pdf}}},\n"
            f"  url_html = {{{url_html}}},\n"
            f"  openaccess = {{{openaccess}}}\n"
            f"}}\n"
        )
    return bibtex_entry

def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("       INICIANDO BUSCA: SPRING NATURE           ")
    print("==============================================\n")
    
    if int(os.getenv("PAGE_SIZE", 25)) > 25:
        print("Aviso: o tamanho da página para a API Springer Nature é limitado a 25 resultados.")
    
    if not query:
        with open(os.path.abspath("config/search_config.yaml"), "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        query = config.get("search_string", config.get("search_string", None)) 
    
    if not query:
        raise ValueError("A string de busca que deve ser declarada em'search_string' no arquivo de configuração config/search_config.yaml não foi definida")
    
    query = query.strip().replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').replace('  ', ' ')
    
    out_dir = os.path.join(path_data, "spring_nature")
    if os.path.exists(out_dir):
        import shutil
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    global records_agregados
    erro_ocorrido = False

    print("Iniciando a coleta dos registros da API Springer Nature...\n")

    num_requisicoes = (MAX_SEARCH_RESULTS // PAGE_SIZE) + (1 if MAX_SEARCH_RESULTS % PAGE_SIZE else 0)
    print(f"Será necessário realizar até {num_requisicoes} requisições (p={PAGE_SIZE}).\n")

    for i in range(num_requisicoes):
        start = 1 + i * PAGE_SIZE
        params = {
            'api_key': API_KEY,
            'q': query,
            's': start,
            'p': PAGE_SIZE
        }

        url_debug = requests.Request('GET', BASE_URL, params=params).prepare().url
        print(f"Requisição {i+1} iniciada para resultados a partir do registro {start}:")
        print(f"URL: {url_debug}\n")

        try:
            response = requests.get(BASE_URL, params=params)
        except Exception as e:
            print(f"Exceção durante a requisição: {e}")
            erro_ocorrido = True
            break

        if response.status_code == 200:
            print(f"Requisição bem-sucedida (status {response.status_code}).")
            try:
                data = response.json()
            except Exception as e:
                print(f"Erro ao decodificar o JSON da resposta: {e}")
                erro_ocorrido = True
                break

            records = data.get('records', [])
            if not records:
                print("Nenhum registro retornado nesta página. Encerrando a coleta.\n")
                break

            records_agregados.extend(records)
            print(f"{len(records)} registros recebidos. Total acumulado: {len(records_agregados)}\n")

            if len(records) < PAGE_SIZE:
                print("Menos registros retornados que o esperado para a página. Finalizando a coleta.\n")
                break
        else:
            print(f"Erro na requisição: código de status {response.status_code}.")
            try:
                error_info = response.json()
                print(json.dumps(error_info, indent=4, ensure_ascii=False))
            except Exception:
                print(response.text)
            erro_ocorrido = True
            break

    if not records_agregados:
        print("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
        return ""
    elif erro_ocorrido:
        raise RuntimeError("Erro durante a coleta dos registros. Nenhum arquivo será salvo.")

    try:
        with open(os.path.join(out_dir, "springer.json"), "w", encoding="utf-8") as f_json:
            json.dump(records_agregados, f_json, ensure_ascii=False, indent=4)
        print("Todos os resultados brutos salvos em 'springer.json'\n")
    except Exception as e:
        raise Exception(f"Erro ao salvar o arquivo JSON: {e}")
        

    registros_filtrados = [rec for rec in records_agregados if rec.get('contentType', '') in ["Article", "Chapter ConferencePaper"]]
    print(f"Após filtragem, foram mantidos {len(registros_filtrados)} registros dos tipos desejados.\n")

    if not registros_filtrados:
        print("Nenhum registro do tipo desejado foi encontrado após a filtragem. Nenhum arquivo será salvo.")
        return ""

    bibtex_entries = [converte_para_bibtex(record) for record in registros_filtrados]

    try:
        with open(os.path.join(out_dir, "springer.bib"), "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Resultados convertidos para BibTeX salvos em 'springer.bib'")
    except Exception as e:
        raise Exception(f"Erro ao salvar o arquivo BibTeX: {e}")
        

    total = len(records_agregados)
    # Log final
    print("\n==============================================")
    print("     BUSCA FINALIZADA: SPRING NATURE            ")
    print(f"      Artigos encontros e adicionados: {total}")
    print("==============================================\n")
