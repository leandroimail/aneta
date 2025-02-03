import requests
import xml.etree.ElementTree as ET
import urllib.parse
import json
import re
import sys

# =============================================================================
# Configurações iniciais para a API arXiv
# =============================================================================
BASE_URL = 'http://export.arxiv.org/api/query'
QUERY = (
    'all:"Schema Matching" AND ('
    'all:"Language Model" OR all:LLM OR all:"Generative AI" OR '
    'all:GenAI OR all:RAG OR all:"Retrieval-Augmented Generation" OR '
    'all:"Retrieval Augmented Generation")'
)
RESULTS_DESEJADOS = 500
PAGE_SIZE = 25  # Número máximo de registros por requisição

# Namespaces presentes no XML retornado pela API
ns = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom'
}

records_agregados = []
raw_feeds = []


# =============================================================================
# Funções auxiliares
# =============================================================================
def extrai_ano(data_str):
    """Extrai o ano a partir de uma string de data."""
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""


def parse_xml_entry(entry):
    """
    Recebe um elemento XML <entry> e extrai os campos desejados,
    retornando um dicionário com os dados.
    """
    record = {}

    # Campo id (ex.: http://arxiv.org/abs/2410.24105v1)
    id_elem = entry.find('atom:id', ns)
    if id_elem is not None and id_elem.text:
        record["id"] = id_elem.text.strip()

    # Título
    title_elem = entry.find('atom:title', ns)
    if title_elem is not None and title_elem.text:
        record["title"] = title_elem.text.strip()

    # Data de publicação
    published_elem = entry.find('atom:published', ns)
    if published_elem is not None and published_elem.text:
        record["published"] = published_elem.text.strip()

    # Resumo/abstract
    summary_elem = entry.find('atom:summary', ns)
    if summary_elem is not None and summary_elem.text:
        record["summary"] = summary_elem.text.strip()

    # Autores
    authors = []
    for author in entry.findall('atom:author', ns):
        name_elem = author.find('atom:name', ns)
        if name_elem is not None and name_elem.text:
            authors.append({"name": name_elem.text.strip()})
    record["authors"] = authors

    # Categorias (tags)
    tags = []
    for category in entry.findall('atom:category', ns):
        term = category.attrib.get("term", "").strip()
        if term:
            tags.append({"term": term})
    record["tags"] = tags

    # Categoria primária (se disponível)
    primary_cat = entry.find('arxiv:primary_category', ns)
    if primary_cat is not None:
        record["arxiv_primary_category"] = {"term": primary_cat.attrib.get("term", "").strip()}

    # Tenta extrair o DOI do XML (pode não estar presente em muitos casos)
    doi_elem = entry.find('arxiv:doi', ns)
    if doi_elem is not None and doi_elem.text:
        record["doi"] = doi_elem.text.strip()

    return record


def obter_doi(record, arxiv_id):
    """
    Retorna o DOI presente no record ou, se ausente, gera-o a partir do arXiv ID.
    Remove o sufixo de versão (por meio de re.sub(r'v\d+$', '', arxiv_id)) e constrói:

      https://doi.org/10.48550/arXiv.<arxiv_id_sem_versao>

    **DOI Generation Logic (Instruction 1 & 3):**
    This function implements the DOI generation logic as described.
    It first checks if 'doi' is already in the record (extracted from XML).
    If not, it proceeds to generate the DOI from arxiv_id.
    """
    doi = record.get("doi", "")
    if not doi and arxiv_id:
        # Remove o sufixo de versão (ex.: 'v1', 'v2', etc.)
        arxiv_base = re.sub(r'v\d+$', '', arxiv_id)
        doi = f"https://doi.org/10.48550/arXiv.{arxiv_base}"
    return doi


def converte_para_bibtex(record):
    """
    Converte um registro (dicionário) em uma entrada BibTeX.
    Se o DOI não for fornecido no XML, ele é gerado a partir do arXiv ID.
    Se o tipo de publicação não estiver presente, ele é fixado como "Arxiv Paper".
    """
    # Formata os autores para o padrão BibTeX (nomes separados por "and")
    authors_list = record.get('authors', [])
    authors = " and ".join([author.get('name', '') for author in authors_list])

    title = record.get('title', '').replace('\n', ' ').strip()
    abstract = record.get('summary', '').replace('\n', ' ').strip()
    published = record.get('published', '')
    year = extrai_ano(published)

    # Extrai o arXiv ID a partir do campo 'id'
    arxiv_id = ""
    if "id" in record:
        arxiv_id = record["id"].split('/abs/')[-1]

    # Gera uma chave única para a entrada BibTeX
    bibtex_key = re.sub(r'\W+', '', arxiv_id) if arxiv_id else (
        re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    )

    # Concatena palavras-chave a partir das tags
    tags = record.get("tags", [])
    keywords = "; ".join([tag.get("term", "") for tag in tags]) if tags else ""

    # Categoria primária (se disponível)
    primary_category = ""
    if 'arxiv_primary_category' in record:
        primary_category = record['arxiv_primary_category'].get('term', '')

    # Obtém o DOI (se ausente, gera a partir do arXiv ID)
    doi = obter_doi(record, arxiv_id)

    # Tipo de publicação fixado como "Arxiv Paper"
    type_publication = "Arxiv Paper" # Publication Type fixed as "Arxiv Paper" (Instruction 2)

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
        f"  keywords = {{{keywords}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  url = {{{record.get('id', '')}}}\n"
        f"}}\n"
    )
    return bibtex_entry


def simplifica_entry(record):
    """
    Cria um dicionário simplificado com os campos principais do registro,
    facilitando a serialização para JSON.
    """
    dados = {
        "id": record.get("id", ""),
        "title": record.get("title", "").replace('\n', ' ').strip(),
        "published": record.get("published", ""),
        "summary": record.get("summary", "").replace('\n', ' ').strip(),
        "authors": [author.get("name", "") for author in record.get("authors", [])],
        "tags": [tag.get("term", "") for tag in record.get("tags", [])]
    }
    if "arxiv_primary_category" in record:
        dados["arxiv_primary_category"] = record["arxiv_primary_category"].get("term", "")
    if "doi" in record:
        dados["doi"] = record["doi"]
    return dados


# =============================================================================
# Função principal
# =============================================================================
def main():
    global records_agregados, raw_feeds
    erro_ocorrido = False
    print("Iniciando a coleta dos registros da API arXiv...\n")
    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE else 0)
    print(f"Serão realizadas até {num_requisicoes} requisições (max_results={PAGE_SIZE}).\n")

    for i in range(num_requisicoes):
        start = i * PAGE_SIZE
        params = {
            'search_query': QUERY,
            'start': start,
            'max_results': PAGE_SIZE
        }
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        print(f"Requisição {i+1} iniciada para resultados a partir do registro {start}:")
        print(f"URL: {url}\n")

        try:
            response = requests.get(url)
        except Exception as e:
            print(f"Exceção durante a requisição: {e}")
            erro_ocorrido = True
            break

        if response.status_code != 200:
            print(f"Erro na requisição: código de status {response.status_code}.")
            erro_ocorrido = True
            break

        try:
            # Faz o parsing do XML e armazena o feed bruto
            feed_xml = ET.fromstring(response.text)
            raw_feeds.append(feed_xml)
        except Exception as e:
            print(f"Erro ao parsear o XML: {e}")
            erro_ocorrido = True
            break

        entries = feed_xml.findall('atom:entry', ns)
        if not entries:
            print("Nenhum registro retornado nesta página. Encerrando a coleta.\n")
            break

        for entry in entries:
            record = parse_xml_entry(entry)
            records_agregados.append(record)

        print(f"{len(entries)} registros recebidos. Total acumulado: {len(records_agregados)}\n")
        if len(entries) < PAGE_SIZE:
            print("Menos registros retornados que o esperado para a página. Finalizando a coleta.\n")
            break

    if erro_ocorrido or not records_agregados:
        print("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Salva os dados simplificados em JSON
    # -----------------------------------------------------------------------------
    registros_json = [simplifica_entry(record) for record in records_agregados]
    try:
        with open("resultados_api.json", "w", encoding="utf-8") as f_json:
            json.dump(registros_json, f_json, ensure_ascii=False, indent=4)
        print("Resultados simplificados salvos em 'resultados_api.json'\n")
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Salva os feeds XML agregados
    # -----------------------------------------------------------------------------
    try:
        root_agg = ET.Element("results")
        for feed in raw_feeds:
            root_agg.append(feed)
        tree = ET.ElementTree(root_agg)
        tree.write("resultados_api.xml", encoding="utf-8", xml_declaration=True)
        print("Feeds XML agregados salvos em 'resultados_api.xml'\n")
    except Exception as e:
        print(f"Erro ao salvar o arquivo XML: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------------
    # Converte os registros para entradas BibTeX e salva
    # -----------------------------------------------------------------------------
    bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]
    try:
        with open("resultados_api.bib", "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Entradas BibTeX salvas em 'resultados_api.bib'")
    except Exception as e:
        print(f"Erro ao salvar o arquivo BibTeX: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()