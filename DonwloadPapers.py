#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para download de artigos científicos a partir de arquivo BibTeX e lista de DOIs.
Suporta download de PDFs (ou conversão do HTML para Markdown) para:
    - Artigos arXiv (via substituição na URL)
    - Artigos com DOI (tentando download direto, fallback para busca no Google Scholar e PyPaperBot)
As estratégias de fallback são tentadas em sequência e o log de arquivos baixados e não baixados é gerado.
"""

import os
import sys
import re
import shutil
import tempfile
import requests
import argparse
import time  # Import time module for sleep
import random # Import random module for random delays

try:
    import bibtexparser
except ImportError:
    print("A biblioteca bibtexparser não está instalada. Instale com: pip install bibtexparser")
    sys.exit(1)

try:
    from markdownify import markdownify as md
except ImportError:
    print("A biblioteca markdownify não está instalada. Instale com: pip install markdownify")
    sys.exit(1)

# Importa scholarly para buscas no Google Scholar
try:
    from scholarly import scholarly
except ImportError:
    print("A biblioteca scholarly não está instalada. Instale com: pip install scholarly")
    sys.exit(1)

# =====================================================================
# Funções utilitárias
# =====================================================================


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}



def sanitize_filename(doi):
    """
    Converte um DOI em um nome de arquivo válido:
    substitui caracteres não alfanuméricos (exceto pontos e hífens) por underline.
    """
    return re.sub(r'[^a-zA-Z0-9\.\-]', '_', doi)

def download_file(url, file_path, binary=True, timeout=20):
    """
    Tenta fazer download do conteúdo da URL e salvar em file_path.
    Retorna True se o download foi bem-sucedido, False caso contrário.
    Adicionado timeout para requests.get
    """
    try:
        # Removendo parâmetros da URL antes do download
        url_sem_parametros = url.split('?')[0]
        response = requests.get(url_sem_parametros, stream=True, timeout=timeout, headers = HEADERS)
        if response.status_code == 200:
            mode = 'wb' if binary else 'w'
            with open(file_path, mode) as f:
                if binary:
                    f.write(response.content)
                else:
                    f.write(response.text)
            return True
        else:
            print(f"Falha ao baixar {url} - Status code: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"Timeout ao baixar {url}")
        return False
    except Exception as e:
        print(f"Erro ao baixar {url}: {e}")
        return False

# =====================================================================
# Processamento dos arquivos de entrada
# =====================================================================

def process_bibtex(bibtex_path):
    """
    Lê o arquivo BibTeX e separa as entradas em:
      - arxiv_entries: aquelas cuja URL contém "arxiv"
      - doi_entries: aquelas que possuem campo DOI (e não são arxiv)
    Retorna duas listas de dicionários.
    """
    arxiv_entries = []
    doi_entries = []
    try:
        with open(bibtex_path, encoding="utf-8") as bibtex_file:
            bib_database = bibtexparser.load(bibtex_file)
            for entry in bib_database.entries:
                url = entry.get("url", "").lower()
                doi = entry.get("doi", "").strip()
                if "arxiv" in url:
                    arxiv_entries.append(entry)
                elif doi != "":
                    doi_entries.append(entry)
        print("\nBibTeX processado com sucesso.\n")
    except Exception as e:
        print(f"Erro ao processar o arquivo BibTeX: {e}")
    return arxiv_entries, doi_entries

def read_doi_file(doi_file_path):
    """
    Lê o arquivo de texto contendo DOIs (um por linha),
    normaliza cada DOI e descarta os que contenham "arxiv".
    Retorna uma lista de strings.
    """
    dois = []
    try:
        with open(doi_file_path, "r", encoding="utf-8") as f:
            for line in f:
                doi = line.strip()
                if doi and "arxiv" not in doi.lower():
                    dois.append(doi)
        print("\nArquivo de DOIs lido com sucesso.\n")
    except Exception as e:
        print(f"Erro ao ler o arquivo de DOIs: {e}")
    return dois

def merge_doi_lists(bibtex_doi_entries, external_doi_list):
    """
    Verifica, para cada DOI do arquivo externo, se já existe na lista proveniente do BibTeX.
    Se não existir, cria uma entrada simples (com as chaves "doi" e "ID") e adiciona.
    Retorna a lista mesclada de entradas DOI.
    """
    merged = bibtex_doi_entries.copy()
    # Extrai DOIs já existentes
    existing_dois = set()
    for entry in bibtex_doi_entries:
        doi_val = entry.get("doi", "").strip().lower()
        if doi_val:
            existing_dois.add(doi_val)
    for doi in external_doi_list:
        if doi.lower() not in existing_dois:
            merged.append({"doi": doi, "ID": doi})
    print("\nListas de DOIs mescladas.\n")
    return merged

# =====================================================================
# Funções de download para cada tipo de entrada
# =====================================================================

def download_arxiv_entry(entry, pdf_dir, logs):
    """
    Faz o download de um artigo arXiv.
    Tenta:
      1. Obter o PDF diretamente (substituindo "abs" por "pdf" na URL).
      2. Se falhar, baixa o HTML (substituindo "abs" por "html"), converte para Markdown
         e salva na pasta "markdown" (dentro de pdf_dir).
    Registra no log o método utilizado.
    """
    url = entry.get("url", "")
    if not url:
        print("Entrada arXiv sem URL.")
        return False

    doi = entry.get("doi", entry.get("ID", "arxiv_unknown"))
    filename = sanitize_filename(doi) + ".pdf"
    pdf_path = os.path.join(pdf_dir, filename)

    # URL para PDF (substituir 'abs' por 'pdf')
    pdf_url = url.replace("abs", "pdf")
    print(f"Baixando PDF do arXiv: {pdf_url}")
    if download_file(pdf_url, pdf_path):
        print(f"PDF salvo: {pdf_path}\n")
        logs["downloaded"].append(f"{doi} -> PDF via arXiv (direto)")
        return True
    else:
        print("Falha no download do PDF. Tentando HTML para Markdown...")
        html_url = url.replace("abs", "html")
        temp_html = os.path.join(tempfile.gettempdir(), sanitize_filename(doi) + ".html")
        if download_file(html_url, temp_html, binary=False):
            try:
                with open(temp_html, "r", encoding="utf-8") as f:
                    html_content = f.read()
                markdown_content = md(html_content, heading_style="ATX")
                markdown_dir = os.path.join(pdf_dir, "markdown")
                os.makedirs(markdown_dir, exist_ok=True)
                md_filename = sanitize_filename(doi) + ".md"
                md_path = os.path.join(markdown_dir, md_filename)
                with open(md_path, "w", encoding="utf-8") as f_md:
                    f_md.write(markdown_content)
                print(f"Arquivo markdown salvo: {md_path}\n")
                logs["downloaded"].append(f"{doi} -> HTML convertido para Markdown via arXiv")
                os.remove(temp_html)
                return True
            except Exception as e:
                print(f"Erro ao converter HTML para Markdown: {e}")
        logs["failed"].append(f"{doi} -> Não foi possível baixar (arXiv)")
        return False


def get_crossref_pdf_link(doi, timeout=10):
    """
    Busca a URL do PDF via API do Crossref usando o DOI.
    Retorna a URL do PDF (string) se encontrada ou None.
    """
    print("Buscando PDF via Crossref...")
    url = f"https://api.crossref.org/works/{doi}"

    try:
        headers = HEADERS
        headers['Accept'] = 'application/json'
        response = requests.get(url, headers=headers, timeout=timeout)

        if response.status_code == 200:
            data = response.json()

            if 'link' in data['message']:
                for link in data['message']['link']:
                    if link.get('content-type') == 'application/pdf':
                        pdf_url = link['URL']
                        # Removendo parâmetros da URL antes de retornar
                        pdf_url_sem_parametros = pdf_url.split('?')[0]
                        print(f"Link PDF encontrado via Crossref: {pdf_url_sem_parametros}")
                        return pdf_url_sem_parametros

            if 'link' in data['message'] and data['message']['link']:
                pdf_url = data['message']['link'][0]['URL']
                # Removendo parâmetros da URL antes de retornar
                pdf_url_sem_parametros = pdf_url.split('?')[0]
                print(f"Link PDF encontrado via Crossref (outro formato): {pdf_url_sem_parametros}")
                return pdf_url_sem_parametros

            print("Link PDF não encontrado via Crossref.")
            return None

        else:
            print(f"Erro ao buscar PDF no Crossref. Status code: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        print(f"Timeout ao buscar PDF no Crossref para DOI: {doi}")
        return None
    except Exception as e:
        print(f"Erro ao recuperar o link do PDF via Crossref para DOI {doi}: {e}")
        return None


def fetch_article_by_doi(doi, timeout=20):
    """
    Busca a URL do PDF no Google Scholar usando o DOI.
    Utiliza scholarly para pesquisar publicações e extrair a chave 'eprint_url' do campo 'bib'.
    Adicionado timeout para a busca no scholarly e delay randomico.
    Retorna a URL do PDF (string) se encontrada ou None.
    """
    try:
        # Introduce random delay before Google Scholar search
        delay = random.randint(1, 20)
        print(f"Aguardando {delay} segundos antes da busca no Google Scholar...")
        time.sleep(delay)

        search_query = scholarly.search_pubs(doi)
        article = next(search_query, None)

        if article:
            scholarly.fill(article) # Removido timeout daqui
            pdf_url = article.get('eprint_url', None)
            if pdf_url:
                print(f"URL do PDF encontrada no Google Scholar (por DOI): {pdf_url}")
                return pdf_url
            else:
                print(f"Campo 'eprint_url' não encontrado no Google Scholar para DOI: {doi}")
                return None
        else:
            print(f"Artigo não encontrado no Google Scholar para DOI: {doi}")
            return None
    except StopIteration:
        print(f"Nenhum resultado encontrado no Google Scholar para DOI: {doi}")
        return None
    except Exception as e:
        print(f"Erro ao buscar PDF no Google Scholar por DOI: {e} - Timeout possivelmente atingido.")
        return None


def fetch_article_by_title(title, timeout=20):
    """
    Busca a URL do PDF no Google Scholar usando o título do artigo.
    Utiliza scholarly para pesquisar publicações e extrair a chave 'eprint_url' do campo 'bib'.
    Adicionado timeout para a busca no scholarly e delay randomico.
    Retorna a URL do PDF (string) se encontrada ou None.
    """
    try:
        # Introduce random delay before Google Scholar search
        delay = random.randint(1, 20)
        print(f"Aguardando {delay} segundos antes da busca no Google Scholar...")
        time.sleep(delay)

        search_query = scholarly.search_pubs(title)
        article = next(search_query, None)

        if article:
            scholarly.fill(article) # Removido timeout daqui
            pdf_url = article.get('eprint_url', None)
            if pdf_url:
                print(f"URL do PDF encontrada no Google Scholar (por título): {pdf_url}")
                return pdf_url
            else:
                print(f"Campo 'eprint_url' não encontrado no Google Scholar para título: {title}")
                return None
        else:
            print(f"Artigo não encontrado no Google Scholar para título: {title}")
            return None

    except StopIteration:
        print(f"Nenhum resultado encontrado no Google Scholar para título: {title}")
        return None
    except Exception as e:
        print(f"Erro ao buscar PDF no Google Scholar por título: {e} - Timeout possivelmente atingido.")
        return None


def download_doi_entry(entry, pdf_dir, logs):
    """
    Faz o download de um artigo identificado por DOI.
    Estratégia:
      1. Tenta o download direto via DOI (usando resolvedor em https://doi.org/).
         Se o conteúdo retornado for PDF, salva-o.
      2. Se falhar, tenta baixar o HTML e converter para Markdown.
      3. Se persistir a falha, tenta buscar PDF via Crossref API.
      4. Se persistir a falha, tenta buscar no Google Scholar (por DOI e, se disponível, por título).
      5. Se ainda não obtiver sucesso, tenta integrar com o PyPaperBot.
    Registra no log o método utilizado ou a falha.
    """
    doi = entry.get("doi", "").strip()
    if not doi:
        print("Entrada sem DOI.")
        return False
    filename = sanitize_filename(doi) + ".pdf"
    pdf_path = os.path.join(pdf_dir, filename)

    # 1. Download direto via DOI
    doi_url = "https://doi.org/" + doi
    print(f"Tentando download direto via DOI: {doi_url}")
    try:
        response = requests.get(doi_url, stream=True, timeout=20, headers = HEADERS)
        content_type = response.headers.get("Content-Type", "")
        if response.status_code == 200 and "pdf" in content_type.lower():
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via DOI direto")
            return True
        else:
            print("Download direto não retornou PDF. Tentando baixar HTML e converter para Markdown...")
    except Exception as e:
        print(f"Erro no download direto via DOI: {e}")

    # 2. Buscar PDF via Crossref API
    print("Tentando busca PDF via Crossref API...")
    pdf_url = get_crossref_pdf_link(doi)
    if pdf_url:
        if download_file(pdf_url, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via Crossref API")
            return True

    # 3. Busca no Google Scholar por DOI
    print("Tentando buscar PDF via Google Scholar (por DOI)...")
    pdf_url = fetch_article_by_doi(doi)
    if pdf_url and pdf_url != 'PDF não encontrado.' and pdf_url != "Artigo não encontrado." and not pdf_url.startswith("Erro ao buscar artigo"): # Check for error messages from scholarly
        if download_file(pdf_url, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via busca Google Scholar (por DOI)")
            return True

    # 4. Busca no Google Scholar por título (se disponível)
    title = entry.get("title", "")
    if title:
        print("Tentando buscar PDF via Google Scholar (por título)...")
        pdf_url = fetch_article_by_title(title)
        if pdf_url and pdf_url != 'PDF não encontrado.'  and pdf_url != "Artigo não encontrado." and not pdf_url.startswith("Erro ao buscar artigo"): # Check for error messages from scholarly
            if download_file(pdf_url, pdf_path):
                print(f"PDF salvo: {pdf_path}\n")
                logs["downloaded"].append(f"{doi} -> PDF via busca Google Scholar (por título)")
                return True

    # 5. Tentar integração com PyPaperBot
    print("Tentando utilizar o PyPaperBot...")
    if run_pypaperbot_for_doi(doi, pdf_dir):
        print(f"PyPaperBot conseguiu baixar o PDF para {doi}\n")
        logs["downloaded"].append(f"{doi} -> PDF via PyPaperBot")
        
        # Tentar baixar o HTML e converter para Markdown
        try:
            response = requests.get(doi_url, timeout=20, headers = HEADERS)
            if response.status_code == 200:
                temp_html = os.path.join(tempfile.gettempdir(), sanitize_filename(doi) + ".html")
                with open(temp_html, "w", encoding="utf-8") as f:
                    f.write(response.text)
                markdown_content = md(response.text, heading_style="ATX")
                markdown_dir = os.path.join(pdf_dir, "markdown")
                os.makedirs(markdown_dir, exist_ok=True)
                md_filename = sanitize_filename(doi) + ".md"
                md_path = os.path.join(markdown_dir, md_filename)
                with open(md_path, "w", encoding="utf-8") as f_md:
                    f_md.write(markdown_content)
                print(f"Arquivo markdown salvo: {md_path}\n")
                logs["downloaded"].append(f"{doi} -> HTML convertido para Markdown via DOI")
                os.remove(temp_html)
                # return True
        except Exception as e:
            print(f"Erro ao baixar/converter HTML via DOI: {e}")
        
        
        
        return True

    print(f"Não foi possível baixar o PDF para {doi}\n")
    logs["failed"].append(f"{doi} -> Falha em todas as estratégias")
    return False


# =====================================================================
# Integração com o PyPaperBot
# =====================================================================

def run_pypaperbot_for_doi(doi, pdf_dir):
    """
    Tenta chamar o PyPaperBot internamente para baixar o PDF do artigo.
    A ideia é:
      - Criar um arquivo temporário contendo o DOI (seguindo o modelo de argumento do PyPaperBot).
      - Ajustar o sys.argv para simular a chamada via linha de comando.
    Retorna True se o PyPaperBot obtiver sucesso, False caso contrário.
    """
    try:
        temp_doi_file = os.path.join(tempfile.gettempdir(), "temp_doi.txt")
        with open(temp_doi_file, "w", encoding="utf-8") as f:
            f.write(doi)
        try:
            from PyPaperBot import __main__ as pypaperbot_main
        except ImportError:
            print("PyPaperBot não está instalado ou não pode ser importado.")
            return False
        old_argv = sys.argv.copy()
        sys.argv = ["PyPaperBot", "--doi-file", temp_doi_file, "--dwn-dir", pdf_dir]
        try:
            pypaperbot_main.main()
        finally:
            sys.argv = old_argv
        filename = sanitize_filename(doi) + ".pdf"
        pdf_path = os.path.join(pdf_dir, filename)
        if os.path.exists(pdf_path):
            os.remove(temp_doi_file)
            return True
        else:
            os.remove(temp_doi_file)
            return False
    except Exception as e:
        print(f"Erro na integração com o PyPaperBot: {e}")
        return False

# =====================================================================
# Função principal para download de todos os artigos
# =====================================================================

def download_all_papers(bibtex_path=None, pdf_dir=None, doi_file_path=None):
    """
    Função principal que realiza:
      - Leitura do BibTeX e do arquivo de DOIs.
      - Mescla as entradas e tenta fazer download dos PDFs (ou converter o HTML para Markdown)
        usando todas as estratégias disponíveis.
      - Mantém logs de sucesso e falhas, imprimindo cada etapa no console.

    Os parâmetros podem ser passados diretamente ou via linha de comando.
    """
    if not bibtex_path or not pdf_dir or not doi_file_path:
        parser = argparse.ArgumentParser(description="Download de artigos via BibTeX e DOIs.")
        parser.add_argument("--bibtex", required=True, help="Caminho do arquivo BibTeX")
        parser.add_argument("--pdf-dir", required=True, help="Diretório onde serão salvos os PDFs")
        parser.add_argument("--doi-file", required=True, help="Arquivo txt contendo DOIs")
        args = parser.parse_args()
        bibtex_path = args.bibtex
        pdf_dir = args.pdf_dir
        doi_file_path = args.doi_file

    os.makedirs(pdf_dir, exist_ok=True)

    logs = {
        "downloaded": [],
        "failed": []
    }

    print("\nInício do processamento...\n")

    arxiv_entries, doi_bibtex_entries = process_bibtex(bibtex_path)
    external_dois = read_doi_file(doi_file_path)
    doi_entries = merge_doi_lists(doi_bibtex_entries, external_dois)

    print("\nProcessando entradas do arXiv...\n")
    for entry in arxiv_entries:
        print("--------------------------------------------------")
        download_arxiv_entry(entry, pdf_dir, logs)
        print("--------------------------------------------------\n")

    print("\nProcessando entradas com DOI...\n")
    for entry in doi_entries:
        print("--------------------------------------------------")
        download_doi_entry(entry, pdf_dir, logs)
        print("--------------------------------------------------\n")

    downloaded_log_path = os.path.join(pdf_dir, "downloaded_log.txt")
    failed_log_path = os.path.join(pdf_dir, "failed_log.txt")
    try:
        with open(downloaded_log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs["downloaded"]))
        with open(failed_log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs["failed"]))
        print(f"Logs salvos:\n - Sucesso: {downloaded_log_path}\n - Falhas: {failed_log_path}\n")
    except Exception as e:
        print(f"Erro ao salvar os logs: {e}")

    print("Processamento concluído.\n")

# =====================================================================
# Permite chamada via linha de comando ou importação
# =====================================================================

if __name__ == "__main__":
    download_all_papers()