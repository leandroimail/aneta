import requests
import json
import re
import sys

# ============================================================
# Configurações iniciais
# ============================================================
API_KEY = "e795e9dbd2edeb1081126a218f52f693"
BASE_URL = 'https://api.elsevier.com/content/search/sciencedirect'

# Query definida para o campo "qs" (pesquisa livre sobre todo o conteúdo do artigo)
QS_QUERY = '("Schema Matching" AND ("Language Model" OR "LLM" OR "Generative AI" OR "GenAI" OR "RAG" OR "Retrieval-Augmented Generation" OR "Retrieval Augmented Generation"))'

RESULTS_DESEJADOS = 500
PAGE_SIZE = 25  # Valores permitidos: 10, 25, 50, 100
records_agregados = []


# ============================================================
# Funções auxiliares
# ============================================================
def extrai_ano(data_str):
    """
    Extrai o ano (quatro dígitos) de uma string de data.
    """
    if data_str:
        match = re.search(r'(\d{4})', data_str)
        if match:
            return int(match.group(1))
    return ""


def busca_abstract_keywords(pii):
    """
    Busca o abstract e as keywords geradas pelo author utilizando a API 
    Elsevier (Abstract Retrieval API).

    Parâmetros:
      pii - PII do artigo (string)

    Retorna:
      Uma tupla (abstract, keywords, tipo_publicacao), onde:
        abstract: conteúdo do abstract (string) ou "" se não encontrado.
        keywords: lista de keywords ou lista vazia, caso não encontre.
        tipo_publicacao: tipo do documento conforme prism:aggregationType
    """
    if not pii:
        return "", [], "Article"
    
    url = f"https://api.elsevier.com/content/abstract/pii/{pii}"
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/xml'
    }
    
    try:
        response = requests.get(url, headers=headers)
    except Exception as e:
        print(f"Exceção ao fazer a requisição para buscar abstract: {e}")
        return "", [], "Article"
    
    if response.status_code == 200:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            ns = {
                'xocs': 'http://www.elsevier.com/xml/svapi/abstract/dtd',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'prism': 'http://prismstandard.org/namespaces/basic/2.0/'
            }
            
            # Extraindo o abstract
            abstract = ""
            abstract_elem = root.find(".//dc:description", ns)
            if abstract_elem is not None and abstract_elem.text:
                abstract = abstract_elem.text.strip()
            
            # Extraindo as keywords
            keywords = []
            keyword_elems = root.findall(".//author-keywords/author-keyword")
            if keyword_elems:
                for k in keyword_elems:
                    if k.text:
                        keywords.append(k.text.strip())
            
            # Extraindo o tipo de publicação
            tipo_publicacao = "Article"  # valor padrão
            agg_type = root.find(".//prism:aggregationType", ns)
            if agg_type is not None and agg_type.text:
                tipo_publicacao = agg_type.text.strip()
            
            return abstract, keywords, tipo_publicacao
        except Exception as e:
            print(f"Erro ao processar o XML da resposta: {e}")
            return "", [], "Article"
    else:
        print(f"Erro ao buscar abstract: código {response.status_code}")
        return "", [], "Article"


def converte_para_bibtex(record):
    """
    Converte um registro retornado pela API Elsevier para o formato BibTeX.
    
    Campos mapeados:
      - authors: lista de autores (campo "authors", extraindo o atributo "name")
      - title: título do artigo (campo "title")
      - year: ano de publicação (extraído de "publicationDate")
      - publication: título da revista ou fonte (campo "sourceTitle")
      - doi: DOI do artigo (campo "doi")
      - url_html: URL do artigo (campo "uri")
    
    Outros campos (keywords, abstract, publisher) não estão disponíveis na resposta.
    """
    # Obtém a lista de autores e monta a string separada por "; "
    authors_list = record.get("authors", [])
    authors = "; ".join([autor.get("name", "").strip() for autor in authors_list if autor.get("name")])
    
    title = record.get("title", "").strip()
    publication_date = record.get("publicationDate", "")
    year = extrai_ano(publication_date)
    publication = record.get("sourceTitle", "").strip()
    doi = record.get("doi", "").strip()
    pii = record.get("pii", "").strip()
    uri = record.get("uri", "").strip()
    publisher = ""  # Inicializando publisher como string vazia
    
    # Busca abstract, keywords e tipo de publicação usando PII
    abstract, keywords, tipo_publicacao = busca_abstract_keywords(pii)
    keywords_str = ", ".join(keywords)
    
    # Define a chave do BibTeX utilizando o DOI ou PII ou parte do título
    if doi:
        bibtex_key = doi.replace('/', '_')
    elif pii:
        bibtex_key = pii.replace('-', '_')
    else:
        bibtex_key = re.sub(r'\W+', '', title)[:20] if title else "sem_titulo"
    
    bibtex_entry = (
        f"@{tipo_publicacao.lower()}{{{bibtex_key},\n"
        f"  authors = {{{authors}}},\n"
        f"  keywords = {{{keywords_str}}},\n"
        f"  abstract = {{{abstract}}},\n"
        f"  title = {{{title}}},\n"
        f"  year = {{{year}}},\n"
        f"  type_publication = {{{tipo_publicacao}}},\n"
        f"  publication = {{{publication}}},\n"
        f"  publisher = {{{publisher}}},\n"
        f"  doi = {{{doi}}},\n"
        f"  url_html = {{{uri}}}\n"
        f"}}\n"
    )
    return bibtex_entry




# ============================================================
# Função principal
# ============================================================
def main():
    global records_agregados
    erro_ocorrido = False

    print("Iniciando a coleta dos registros da API Elsevier (ScienceDirect) via PUT...\n")

    num_requisicoes = (RESULTS_DESEJADOS // PAGE_SIZE) + (1 if RESULTS_DESEJADOS % PAGE_SIZE != 0 else 0)
    print(f"Será necessário realizar até {num_requisicoes} requisições (show={PAGE_SIZE}).\n")

    # Cabeçalhos necessários para a requisição PUT
    headers = {
        'X-ELS-APIKey': API_KEY,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Loop de paginação
    for i in range(num_requisicoes):
        offset = i * PAGE_SIZE

        # Corpo da requisição seguindo o schema da API v2
        body = {
            "qs": QS_QUERY,
            "display": {
                "offset": offset,
                "show": PAGE_SIZE,
                "sortBy": "relevance"
            }
        }

        print(f"Requisição {i+1} iniciada para resultados a partir do offset {offset}.")
        print(f"Corpo da requisição: {json.dumps(body)}\n")

        try:
            response = requests.put(BASE_URL, json=body, headers=headers)
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

            results = data.get("results", [])
            if not results:
                print("Nenhum registro retornado nesta página. Encerrando a coleta.\n")
                break

            records_agregados.extend(results)
            print(f"{len(results)} registros recebidos. Total acumulado: {len(records_agregados)}\n")

            # Se o número de registros retornados for menor que o tamanho da página, encerra a coleta
            if len(results) < PAGE_SIZE:
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

    if erro_ocorrido or not records_agregados:
        print("\nHouve um erro durante a coleta ou nenhum registro foi encontrado. Nenhum arquivo será salvo.")
        sys.exit(1)

    # Salvando os resultados brutos em arquivo JSON
    try:
        # Adiciona abstract e keywords aos registros antes de salvar
        for record in records_agregados:
            if "pii" in record:
                abstract, keywords, tipo_publicacao = busca_abstract_keywords(record["pii"])
                record["abstract"] = abstract
                record["keywords"] = keywords
                record["type_publication"] = tipo_publicacao
                
        with open("elsevier.json", "w", encoding="utf-8") as f_json:
            json.dump(records_agregados, f_json, ensure_ascii=False, indent=4)
        print("Todos os resultados brutos salvos em 'elsevier.json'\n")
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        sys.exit(1)

    # Conversão dos registros para o formato BibTeX
    bibtex_entries = [converte_para_bibtex(record) for record in records_agregados]

    try:
        with open("elsevier.bib", "w", encoding="utf-8") as f_bib:
            f_bib.write("\n".join(bibtex_entries))
        print("Resultados convertidos para BibTeX salvos em 'elsevier.bib'")
    except Exception as e:
        print(f"Erro ao salvar o arquivo BibTeX: {e}")
        sys.exit(1)


# ============================================================
# Execução principal
# ============================================================
if __name__ == "__main__":
    main()
