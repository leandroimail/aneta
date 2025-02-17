import os
import requests
import json
from urllib.parse import quote
import re


def extrai_ano(data_str):
    """
    Extrai o ano (quatro dígitos) de uma string de data.
    """
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""


def converte_para_bibtex(record):
    """
    Converte um registro da API Elsevier para o formato BibTeX.
    Mapeia os seguintes campos do record:
      - dc:title              -> title
      - dc:description        -> abstract
      - prism:coverDate       -> year (extraído via extrai_ano)
      - prism:doi ou dc:identifier -> doi
      - prism:url             -> url_html
      - prism:isbn            -> isbn
      - prism:issn            -> issn
      - prism:volume          -> volume
      - prism:issueIdentifier -> number
      - prism:startingPage e prism:endingPage -> pages
      - prism:publicationName -> source e journal
      - authkeywords          -> author_keywords
      - openaccessArticle     -> openaccess
      - pubType               -> type_publication
    Os demais campos são preenchidos com valor vazio.
    """
    # Autores: se 'authors' for uma lista, une os nomes; se for string, utiliza diretamente.
    authors = ""
    authors_data = record.get("authors", {})
    if isinstance(authors_data, dict) and "author" in authors_data:
        authors_data = [author.get("$", "") for author in authors_data["author"]]
        authors = "; ".join(authors_data)     
    
    title = record.get("dc:title", "").strip()
    abstract = record.get("dc:description", "").strip()
    cover_date = record.get("prism:coverDate", "")
    year = extrai_ano(cover_date)
    doi = record.get("prism:doi", "").strip() or record.get("dc:identifier", "").strip()
    uri = record.get("prism:url", "").strip()

    # Não há mapeamento específico para publisher na documentação fornecida
    publisher = ""

    isbn = record.get("prism:isbn", "").strip()
    issn = record.get("prism:issn", "").strip()
    volume = record.get("prism:volume", "").strip()
    number = record.get("prism:issueIdentifier", "").strip()
    
    first = record.get("prism:startingPage", "").strip()
    last = record.get("prism:endingPage", "").strip()
    pages = f"{first}--{last}" if first and last else first
    
    source = record.get("prism:publicationName", "").strip()
    journal = source  # Usa o mesmo valor do source para journal
    conference = ""
    keywords_api = ""  # Não há mapeamento específico para keywords de publisher ou journal
    author_keywords = record.get("authkeywords", "").strip().replace("|", ";").replace(",", ";")
    cited_by_count_source = ""
    affiliations = ""
    autor_orcid = ""
    abbrev_source_title = ""
    openaccess = str(record.get("openaccessArticle", False)).lower()
    type_publication = record.get("prism:aggregationType", "").strip()
    if type_publication == "Journal":
        type_publication = "Article"
    elif type_publication == "Book":
        type_publication = "Book"
    elif type_publication == "Book Series":
        type_publication = "InCollection"
    elif type_publication == "referencework":
        type_publication = "InReference"
    elif record.get("prism:aggregationType", "").strip().lower() in ('fla', 'rev', 'rpl'):
        type_publication = "Article"
    else:
        type_publication = ""
    
    # Define a chave do BibTeX utilizando o DOI (se disponível) ou parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@article{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  title = {{{title}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  year = {{{year}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{uri}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  isbn = {{{isbn}}},\n"
        f"  issn = {{{issn}}},\n"
        f"  volume = {{{volume}}},\n"
        f"  number = {{{number}}},\n"
        f"  pages = {{{pages}}},\n"
        f"  source = {{{source}}},\n"
        f"  journal = {{{journal}}},\n"
        f"  conference = {{{conference}}},\n"
        f"  keywords = {{{keywords_api}}},\n"
        f"  author_keywords = {{{author_keywords}}},\n"
        f"  cited_by_count_source = {{{cited_by_count_source}}},\n"
        f"  affiliations = {{{affiliations}}},\n"
        f"  autor_orcid = {{{autor_orcid}}},\n"
        f"  abbrev_source_title = {{{abbrev_source_title}}},\n"
        f"  openaccess = {{{openaccess}}},\n"
        f"  type_publication = {{{type_publication}}}\n"
        f"}}\n"
    )
    return bibtex_entry


def get_metadata(list_pii, API_KEY):
    """Obtém os metadados dos artigos via Elsevier API."""
    dois_query = " OR ".join([f'"{pii}"' for pii in list_pii])
    query = f'pii({dois_query})'
    query_encoded = quote(query)
    url = (
        f'https://api.elsevier.com/content/metadata/article'
        f'?query={query_encoded}&apiKey={API_KEY}&view=COMPLETE'
    )
    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        response.raise_for_status()  # Levanta exceção para status diferentes de 200
        return response.json()
    except requests.RequestException as e:
        print("Erro na requisição:", e)
        return None

if __name__ == "__main__":
    API_KEY = os.getenv("ELSEVIER_API_KEY", "")
    if not API_KEY:
        print("Variável de ambiente ELSEVIER_API_KEY não está definida.")
        exit(1)
    
    list_pii = [
        'S0950705125000942',
        # 'S0169023X24001290',
        # 'S0925231221016635',
        # 'S0167739X18326529',
        # 'B9780120884698500383',
        # 'S1877050924008305',
        # 'S2210670722003468',
        # 'S0167923623001136',
        # 'S1570826824000015',
        # 'S0306437924000024',
        # 'B9780443296543000089',
        # 'S1574013719301297',
        # 'B9780080453743500223',
        # 'S1570826806000230',
        # 'B978012800867600011X',
        # 'S095070511930317X',
        # 'S0166361522001506',
        # 'S095741741300393X',
        # 'S1877050920320068',
        # 'S0950584912000043',
        # 'S1571066106005263',
        # 'S0306457307001471',
        # 'S0020025520302383',
        # 'B9781558608696500585',
        # 'S0306437909001203',
        # 'S0950705114002640',
        # 'S0893608005000341',
        # '0010027788900327',
    ]
    
    offset = 0   # Posição inicial
    limit = 25   # Quantidade de registros por página

    records_agregados = []
    data = get_metadata(list_pii, API_KEY)
    records_agregados.extend(data.get("search-results", {}).get("entry", []))
    if data:
        bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]
        
    print("\n".join(bibtex_entries))
