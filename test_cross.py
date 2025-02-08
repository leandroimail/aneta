from Config import path_SPRINGER, path_ACM, path_directory_bibs
from DonwloadPapers import download_all_papers
import os
import bibtexparser
import json



def extract_bibtex_info(bibtex_file_path, output_json_path=None):
    """
    Extrai as tags 'title', 'abstract', 'keywords', 'type_publication' e 'doi' de um arquivo BibTeX e retorna um JSON.
    Se output_json_path for fornecido, salva o JSON no caminho especificado.

    :param bibtex_file_path: Caminho do arquivo BibTeX.
    :param output_json_path: Caminho onde salvar o JSON (opcional).
    :return: Lista de dicionários contendo as informações extraídas.
    """
    # Carrega o arquivo BibTeX
    with open(bibtex_file_path, 'r', encoding='utf-8') as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)

    # Lista para armazenar as entradas processadas
    entries = []

    # Itera sobre cada entrada no arquivo BibTeX
    for entry in bib_database.entries:
        # Cria um dicionário com as informações desejadas
        entry_info = {
            'title': entry.get('title', ''),
            'abstract': entry.get('abstract', ''),
            'keywords': entry.get('keywords', ''),
            'type_publication': entry.get('type_publication', ''),  # Nova tag
            'doi': entry.get('doi', '')  # Nova tag
        }
        # Adiciona o dicionário à lista de entradas
        entries.append(entry_info)

    # Se um caminho de saída for fornecido, salva o JSON
    if output_json_path:
        with open(output_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(entries, json_file, indent=4, ensure_ascii=False)
        print(f"Informações extraídas e salvas em {output_json_path}")

    # Retorna o JSON gerado
    return entries

bib_file = "OUTPUTS/select_bibs.bib"
json_file = "OUTPUTS/select_tags_bibs.json"
path_directory_file_bib = os.path.join(path_directory_bibs, bib_file)
path_directory_file_json = os.path.join(path_directory_bibs, json_file)

json_bibs = extract_bibtex_info(path_directory_file_bib, path_directory_file_json)

print(f"Quantidade de artigos {len(json_bibs)}")
print(json_bibs)