import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import json
import re
import sys
from dotenv import load_dotenv

load_dotenv()

BASE_URL = 'http://export.arxiv.org/api/query'
# Remova a query fixa; ela será definida externamente
RESULTS_DESEJADOS = 500
PAGE_SIZE = 25

# Namespaces present in the XML returned by the API
ns = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom'
}

records_agregados = []
raw_feeds = []


# =============================================================================
# Helper functions
# =============================================================================
def extrai_ano(data_str):
    """Extracts the year from a date string."""
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""


def parse_xml_entry(entry):
    """
    Receives an XML <entry> element and extracts the desired fields,
    returning a dictionary with the data.
    """
    record = {}

    # Field id (e.g., http://arxiv.org/abs/2410.24105v1)
    id_elem = entry.find('atom:id', ns)
    if id_elem is not None and id_elem.text:
        record["id"] = id_elem.text.strip()

    # Title
    title_elem = entry.find('atom:title', ns)
    if title_elem is not None and title_elem.text:
        record["title"] = title_elem.text.strip()

    # Publication date
    published_elem = entry.find('atom:published', ns)
    if published_elem is not None and published_elem.text:
        record["published"] = published_elem.text.strip()

    # Abstract/summary
    summary_elem = entry.find('atom:summary', ns)
    if summary_elem is not None and summary_elem.text:
        record["summary"] = summary_elem.text.strip()

    # Authors
    authors = []
    for author in entry.findall('atom:author', ns):
        name_elem = author.find('atom:name', ns)
        if name_elem is not None and name_elem.text:
            authors.append({"name": name_elem.text.strip()})
    record["authors"] = authors

    # Categories (tags/keywords from arXiv)
    tags = []
    for category in entry.findall('atom:category', ns):
        term = category.attrib.get("term", "").strip()
        if term:
            tags.append({"term": term})
    record["tags"] = tags  # These are the keywords extracted from arXiv categories

    # Primary category (if available)
    primary_cat = entry.find('arxiv:primary_category', ns)
    if primary_cat is not None:
        record["arxiv_primary_category"] = {"term": primary_cat.attrib.get("term", "").strip()}

    # Attempts to extract DOI from XML (may not be present in many cases)
    doi_elem = entry.find('arxiv:doi', ns)
    if doi_elem is not None and doi_elem.text:
        record["doi"] = doi_elem.text.strip()

    # -------------------------------------------------------------------------
    # Extração dos links para download do HTML e do PDF a partir dos elementos <link>
    # -------------------------------------------------------------------------
    url_pdf = ""
    url_html = ""
    for link in entry.findall('atom:link', ns):
        href = link.attrib.get("href", "").strip()
        rel = link.attrib.get("rel", "").strip()
        typ = link.attrib.get("type", "").strip()
        title = link.attrib.get("title", "").strip().lower()
        if rel == "alternate" and typ == "text/html":
            url_html = href
        elif title == "pdf" or (rel == "related" and typ == "application/pdf"):
            url_pdf = href
    record["url_pdf"] = url_pdf
    record["url_html"] = url_html

    return record


def converter_query(query):
    """
    Converte a query (no formato livre) para o formato desejado pelo arXiv,
    em que cada termo deve ser 'all:termo' ou 'all:"termo com espaco"',
    respeitando operadores AND, OR, NOT -> ANDNOT e parênteses.
    
    Exemplo de uso:
      Input:
        ("Schema Matching" AND ("Language Model" OR "LLM"))
      Saída:
        ( all:"Schema Matching" AND ( all:"Language Model" OR all:"LLM" ) )
    """

    # Regex para capturar:
    # - Parênteses: ( ou )
    # - Strings entre aspas: "..."
    # - Operadores lógicos: AND, OR, ANDNOT, NOT
    # - Qualquer outro 'token' sem espaço nem parênteses
    pattern = r'(\(|\)|"[^"]*"|ANDNOT|AND|OR|NOT|[^()\s]+)'

    # Quebramos a query em tokens
    tokens = re.findall(pattern, query, flags=re.IGNORECASE)

    resultado = []
    for token in tokens:
        # Normalizamos para checar operadores em maiúsculo
        upper_token = token.upper()

        if token == '(' or token == ')':
            # Mantém parênteses como estão
            resultado.append(token)
        elif upper_token in ['AND', 'OR', 'ANDNOT']:
            # Mantém operadores em maiúsculo
            resultado.append(upper_token)
        elif upper_token == 'NOT':
            # Converte NOT em ANDNOT
            resultado.append('ANDNOT')
        elif token.startswith('"') and token.endswith('"'):
            # Token entre aspas -> remove as aspas externas e converte para all:"conteúdo"
            frase = token[1:-1]  # remove aspas
            resultado.append(f'all:"{frase}"')
        else:
            # Se o token tiver espaço, usa aspas
            if ' ' in token or '-' in token:
                resultado.append(f'all:"{token}"')
            else:
                resultado.append(f'all:{token}')

    # Junta tudo com espaço como separador
    return ' '.join(resultado)


def obter_doi(record, arxiv_id):
    """
    Returns the DOI present in the record or, if absent, generates it from the arXiv ID.
    Removes the version suffix (using re.sub(r'v\d+$', '', arxiv_id)) and constructs:

      https://doi.org/10.48550/arXiv.<arxiv_id_sem_versao>

    **DOI Generation Logic (Instruction 1 & 3):**
    This function implements the DOI generation logic as described.
    It first checks if 'doi' is already in the record (extracted from XML).
    If not, it proceeds to generate the DOI from arxiv_id.
    """
    doi = record.get("doi", "")
    if not doi and arxiv_id:
        # Remove the version suffix (e.g., 'v1', 'v2', etc.)
        arxiv_base = re.sub(r'v\d+$', '', arxiv_id)
        doi = f"https://doi.org/10.48550/arXiv.{arxiv_base}"
    return doi


def converte_para_bibtex(record):
    """
    Converts a record (dictionary) into a BibTeX entry.
    If the DOI is not provided in the XML, it is generated from the arXiv ID.
    If the publication type is not present, it is fixed as "Arxiv Paper".
    """
    # Format authors for BibTeX standard (names separated by "and")
    authors_list = record.get('authors', [])
    authors = " and ".join([author.get('name', '') for author in authors_list])

    title = record.get('title', '').replace('\n', ' ').strip()
    abstract = record.get('summary', '').replace('\n', ' ').strip()
    published = record.get('published', '')
    year = extrai_ano(published)

    # Extract the arXiv ID from the 'id' field
    arxiv_id = ""
    if "id" in record:
        arxiv_id = record["id"].split('/abs/')[-1]

    # Generate a unique key for the BibTeX entry
    bibtex_key = re.sub(r'\W+', '', arxiv_id) if arxiv_id else (
        re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    )

    # Concatenate keywords from tags
    tags = record.get("tags", [])
    # Directly use the terms from tags as keywords, separated by semicolons
    keywords = "; ".join([tag.get("term", "") for tag in tags]) if tags else ""

    # Primary category (if available)
    primary_category = ""
    if 'arxiv_primary_category' in record:
        primary_category = record['arxiv_primary_category'].get('term', '')

    # Get the DOI (if absent, generate from arXiv ID)
    doi = obter_doi(record, arxiv_id)

    # Publication type fixed as "Arxiv Paper"
    type_publication = "Arxiv Paper"  # Publication Type fixed as "Arxiv Paper"

    # Recupera os links para PDF e HTML extraídos
    url_pdf = record.get("url_pdf", "")
    url_html = record.get("url_html", "")

    bibtex_entry = (
        f"@misc{{{bibtex_key},\n"
        f"  author = {{{authors}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  eprint = {{{arxiv_id}}},\n"
        f"  archivePrefix = {{arXiv}},\n"
        f"  primaryClass = {{{primary_category}}},\n"
        f"  type_publication = {{{type_publication}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  keywords = {{{keywords}}},\n"  # Keywords are directly from arXiv categories
        f"  abstract = {{{abstract}}},\n"
        f"  url = {{{record.get('id', '')}}},\n"
        f"  url_pdf = {{{url_pdf}}},\n"
        f"  url_html = {{{url_html}}}\n"
        f"}}\n"
    )
    return bibtex_entry


def simplifica_entry(record):
    """
    Creates a simplified dictionary with the main fields of the record,
    facilitating serialization to JSON.
    """
    dados = {
        "id": record.get("id", ""),
        "title": record.get("title", "").replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').strip(),
        "published": record.get("published", ""),
        "summary": record.get("summary", "").replace('\n', ' ').replace('\t', ' ').replace('   ', ' ').replace('  ', ' ').strip(),
        "authors": [author.get("name", "") for author in record.get("authors", [])],
        "tags": [tag.get("term", "") for tag in record.get("tags", [])]  # Keywords are directly from arXiv categories
    }
    if "arxiv_primary_category" in record:
        dados["arxiv_primary_category"] = record["arxiv_primary_category"].get("term", "")
    if "doi" in record:
        dados["doi"] = record["doi"]
    # Opcional: incluir também os links extraídos, se desejado no JSON simplificado
    if "url_pdf" in record:
        dados["url_pdf"] = record["url_pdf"]
    if "url_html" in record:
        dados["url_html"] = record["url_html"]
    return dados


# =============================================================================
# Main function
# =============================================================================
def main(query, path_data):
    # Log inicial melhorado
    print("\n==============================================")
    print("          INICIANDO BUSCA: ARXIV              ")
    print("==============================================\n")
    
    out_dir = os.path.join(path_data, "arxiv")
    os.makedirs(out_dir, exist_ok=True)
    global records_agregados, raw_feeds
    erro_ocorrido = False
    print("Starting the collection of records from the arXiv API...\n")
    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE else 0)
    print(f"Up to {num_requisicoes} requests will be made (max_results={PAGE_SIZE}).\n")

    for i in range(num_requisicoes):
        start = i * PAGE_SIZE
        params = {
            'search_query': query,
            'start': start,
            'max_results': PAGE_SIZE
        }
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        print(f"Request {i+1} initiated for results starting from record {start}:")
        print(f"URL: {url}\n")

        try:
            response = requests.get(url)
        except Exception as e:
            print(f"Exception during request: {e}")
            erro_ocorrido = True
            break

        if response.status_code != 200:
            print(f"Error in request: status code {response.status_code}.")
            erro_ocorrido = True
            break

        try:
            # Parses the XML and stores the raw feed
            feed_xml = ET.fromstring(response.text)
            raw_feeds.append(feed_xml)
        except Exception as e:
            print(f"Error parsing XML: {e}")
            erro_ocorrido = True
            break

        entries = feed_xml.findall('atom:entry', ns)
        if not entries:
            print("No records returned on this page. Ending collection.\n")
            break

        for entry in entries:
            record = parse_xml_entry(entry)
            records_agregados.append(record)

        print(f"{len(entries)} records received. Accumulated total: {len(records_agregados)}\n")
        if len(entries) < PAGE_SIZE:
            print("Fewer records returned than expected for the page. Finalizing collection.\n")
            break

    if erro_ocorrido or not records_agregados:
        print("\nThere was an error during collection or no records were found. No files will be saved.")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Saves simplified data in JSON
    # -----------------------------------------------------------------------------
    registros_json = [simplifica_entry(record) for record in records_agregados]
    try:
        with open(os.path.join(out_dir, "resultados_api.json"), "w", encoding="utf-8") as f_json:
            json.dump(registros_json, f_json, ensure_ascii=False, indent=4)
        print("Simplified results saved in 'resultados_api.json'\n")
    except Exception as e:
        print(f"Error saving JSON file: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Saves aggregated XML feeds
    # -----------------------------------------------------------------------------
    try:
        root_agg = ET.Element("results")
        for feed in raw_feeds:
            root_agg.append(feed)
        tree = ET.ElementTree(root_agg)
        with open(os.path.join(out_dir, "resultados_api.xml"), "wb") as f_xml:
            tree.write(f_xml, encoding="utf-8", xml_declaration=True)
        print("Aggregated XML feeds saved in 'resultados_api.xml'\n")
    except Exception as e:
        print(f"Error saving XML file: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Converts records to BibTeX entries and saves
    # -----------------------------------------------------------------------------
    bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]
    try:
        with open(os.path.join(out_dir, "resultados_api.bib"), "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("BibTeX entries saved in 'resultados_api.bib'")
    except Exception as e:
        print(f"Error saving BibTeX file: {e}")
        sys.exit(1)

    # Log final
    print("\n==============================================")
    print("         BUSCA FINALIZADA: ARXIV               ")
    print(f"       Artigos encontros e adicionados: {len(records_agregados)}")
    print("==============================================\n")

    print("\nData collection and saving process completed successfully.")
    print("Please note: Keywords are extracted directly from arXiv API categories.")
    print("If specific keyword classification or filtering is desired, further processing needs to be implemented.")


if __name__ == "__main__":
    import sys
    QUERY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SEARCH_QUERY", "")
    PATH_DATA = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATH_DATA", "../Sandbox/Data")
    # Converte a query, se necessário
    QUERY = converter_query(QUERY)
    main(QUERY, PATH_DATA)





