import os
import sys
import urllib
import tempfile
import requests
import argparse
import time  
import random
import yaml
from dotenv import load_dotenv
from src.Database import create_lancedb_instance, save_bibliographic_database, fetch_bibliographic_database


try:
    import bibtexparser
except ImportError:
    raise ImportError("A biblioteca bibtexparser não está instalada. Instale com: pip install bibtexparser")

try:
    from markdownify import markdownify as md
except ImportError:
    raise ImportError("A biblioteca markdownify não está instalada. Instale com: pip install markdownify")

# Importa scholarly para buscas no Google Scholar
try:
    from scholarly import scholarly
except ImportError as error:
    raise ImportError(f"Erro ao importar a biblioteca scholarly. Error: {error}")

# =====================================================================
# Funções utilitárias
# =====================================================================

db = create_lancedb_instance()
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}



def sanitize_filename(doi):
    """
    Converte um DOI em um nome de arquivo válido:
    substitui caracteres não alfanuméricos (exceto pontos e hífens) por underline.
    """
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return urllib.parse.quote(doi, safe='')

def download_file(url, file_path, binary=True, timeout=20):
    """
    Tenta fazer download do conteúdo da URL e salvar em file_path.
    Retorna True se o download foi bem-sucedido, False caso contrário.
    Adicionado timeout para requests.get
    """
    try:
        response = requests.get(url, stream=True, timeout=timeout, headers=HEADERS)
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
# Carregamento de configurações
# =====================================================================

def load_config():
    """
    Carrega as configurações do arquivo YAML.
    """
    config_path = os.path.abspath("Config/general_config.yaml")
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        return {
            'enable_PyPaperBot_download': False,
            'enable_search_link_file_by_google_scholars': False
        }

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
    
    if os.path.exists(pdf_path):
        print(f"PDF já baixado: {pdf_path}")
        logs["downloaded"].append(f"{doi} -> PDF já baixado")
        return True
    
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
        type_source = "crossref"
        try:
            data = fetch_bibliographic_database(type_source, doi, db)
            if data: print(f"Registro encontrado no banco de dados: {doi}")
        except Exception as e:
            print(f"Erro ao buscar registro no banco de dados: {e}")
            data = None
        if not data:
            headers = HEADERS
            headers['Accept'] = 'application/json'
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 404:
                print(f"Erro ao buscar PDF no Crossref. Status code: {response.status_code}")
                return None
            response.raise_for_status()
            data = response.json()
            if data:
                try:
                    save_bibliographic_database(type_source, doi, data, db)
                    print(f"Registro salvo no banco de dados: {doi}")
                except Exception as e:
                    print(f"Erro ao salvar registro no banco de dados: {e}")
        if data:    
            if 'link' in data['message']:
                for link in data['message']['link']:
                    if link.get('content-type') == 'application/pdf':
                        pdf_url = link['URL']
                        print(f"Link PDF encontrado via Crossref: {pdf_url}")
                        return pdf_url
            if 'link' in data['message'] and data['message']['link']:
                pdf_url = data['message']['link'][0]['URL']
                print(f"Link PDF encontrado via Crossref (outro formato): {pdf_url}")
                return pdf_url
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



def get_openalex_pdf_link(doi, timeout=10, email=""):
    """
    Busca a URL do PDF via API do OpenAlex usando o DOI.
    Retorna a URL do PDF (string) se encontrada ou None.
    
    Parâmetros:
    - doi (str): DOI do trabalho científico
    - timeout (int): Tempo máximo de espera em segundos
    - email (str): E-mail para identificação no 'Polite Pool' da API
    
    Referência: :cite[1]:cite[5]:cite[9]
    """
    print("Buscando PDF via OpenAlex...")
    
    if not email:
        email = os.getenv('OPENALEX_EMAIL')
        if not email:
            print("E-mail não fornecido e variável de ambiente OPENALEX_EMAIL não definida")
            print("Recomenda-se fornecer um e-mail para evitar limitações na API")
            print("Consulte  para mais informações")
            print("Obtenção de PDFs pode ser limitada sem e-mail se o uso unpaywall")
            return None
    try:        
        type_source = "openalex"
        try:
            data = fetch_bibliographic_database(type_source, doi, db)
            if data: print(f"Registro encontrado no banco de dados: {doi}")
        except Exception as e:
            print(f"Erro ao buscar registro no banco de dados: {e}")
            data = None
        if not data:
            headers = {
                'Accept': 'application/json',
                'From': email  # Melhora prioridade na API :cite[3]
            }
            headers = {**headers, **HEADERS}
            url = f"https://api.openalex.org/works/https://doi.org/{doi}"
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
            if data:
                try:
                    save_bibliographic_database(type_source, doi, data, db)
                    print(f"Registro salvo no banco de dados: {doi}")
                except Exception as e:
                    print(f"Erro ao salvar registro no banco de dados: {e}")
            elif response.status_code == 403:
                print("Erro 403: Acesso negado. Verifique o formato do DOI")
                return None
            
            elif response.status_code == 404:
                print("Erro 404: DOI não encontrado no OpenAlex")
                return None
                
            else:
                print(f"Erro na requisição. Status code: {response.status_code}")
                return None
        
        # Primeira verificação: Open Access direct URL :cite[9]
        if data.get('open_access'):
            oa_info = data['open_access']
            if oa_info.get('is_oa') and oa_info.get('oa_url'):
                pdf_url = oa_info['oa_url']
                print(f"Link OA encontrado via OpenAlex: {pdf_url}")
                return pdf_url
        
        # Segunda verificação: Locations com PDF :cite[9]
        for location in data.get('locations') or []:
            if location.get('pdf_url'):
                pdf_url = location['pdf_url']
                print(f"Link PDF em locations encontrado: {pdf_url}")
                return pdf_url
        
        # Terceira verificação: Versão mais recente :cite[9]
        best_oa = data.get('best_oa_location') or {}
        if best_oa.get('pdf_url'):
            pdf_url = best_oa['pdf_url']
            print(f"Link PDF em best_oa_location: {pdf_url}")
            return pdf_url
        
        print("Nenhum link PDF encontrado via OpenAlex")
        return None
            

            
    except requests.exceptions.Timeout:
        print(f"Timeout ao buscar DOI {doi} no OpenAlex")
        return None
    except Exception as e:
        print(f"Erro geral ao buscar PDF via OpenAlex: {str(e)}")
        return None


def get_unpaywall_pdf_link(doi, timeout=10, email=""):
    """
    Busca a URL do PDF via API do Unpaywall usando o DOI.
    Retorna a URL do PDF (string) se encontrada ou None.
    """
    print("Buscando PDF via Unpaywall...")
    
    if not email:
        email = os.getenv('UNPAYWALL_EMAIL')
        if not email:
            print("E-mail não fornecido e variável de ambiente UNPAYWALL_EMAIL não definida")
            print("Recomenda-se fornecer um e-mail para evitar limitações na API")
            print("Consulte https://unpaywall.org/products/api para mais informações")
            print("Obtenção de PDFs pode ser limitada sem e-mail se o uso unpaywall")
            return None
        
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            best_oa = data.get('best_oa_location') or {}
            if best_oa.get('url_for_pdf'):
                pdf_url = best_oa['url_for_pdf']
                print(f"Link PDF encontrado via Unpaywall: {pdf_url}")
                return pdf_url
            print("Nenhum link PDF encontrado via Unpaywall")
            return None
        else:
            print(f"Erro na requisição no Unpaywall. Status code: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout ao buscar DOI {doi} no Unpaywall")
        return None
    except Exception as e:
        print(f"Erro geral ao buscar PDF via Unpaywall: {str(e)}")
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


def download_doi_entry(entry, pdf_dir, logs, failed_entries):
    """
    Faz o download de um artigo identificado por DOI.
    Estratégia:
      1. Verificar se o PDF já existe
      2. Tentar campo url_pdf
      3. Download direto via DOI
      4. Buscar via Crossref API
      5. Buscar via OpenAlex
      6. Buscar via Unpaywall
    Se todas estas estratégias falharem, adiciona à lista de failed_entries para tentar depois.
    """
    doi = entry.get("doi", "").strip()
    title = entry.get("title", "").strip()
    if not doi:
        print("Entrada sem DOI.")
        # Registra no log de falhas que não foi possível baixar por falta de DOI
        entry_id = entry.get("ID", "entrada_desconhecida")
        logs["failed"].append(f"{entry_id} -> Não foi possível baixar pois artigo não possui DOI: Titulo: {title}")
        return False
    filename = sanitize_filename(doi) + ".pdf"
    pdf_path = os.path.join(pdf_dir, filename)
    
    # 1. Verificar se o PDF já foi baixado
    if os.path.exists(pdf_path):
        print(f"PDF já baixado: {pdf_path}")
        logs["downloaded"].append(f"{doi} -> PDF já baixado")
        return True
    
    # 2. Tentando baixar via campo url_pdf
    url_pdf = entry.get("url_pdf", "")
    print(f"Tentando download via campo url_pdf: {url_pdf}")
    if url_pdf:
        if download_file(url_pdf, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via campo url_pdf")
            return True
    else:
        print("Falha ao baixar via campo url_pdf. Tentando baixar via DOI...")

    # 3. Download direto via DOI
    doi_url = "https://doi.org/" + doi
    print(f"Tentando download direto via DOI: {doi_url}")
    try:
        response = requests.get(doi_url, stream=True, timeout=20, headers=HEADERS)
        content_type = response.headers.get("Content-Type", "")
        if response.status_code == 200 and "pdf" in content_type.lower():
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via DOI direto")
            return True
        else:
            print("Download direto não retornou PDF. Tentando encontrar link de PDF em bases acadêmicas...")
    except Exception as e:
        print(f"Erro no download direto via DOI: {e}")

    # 4. Buscar PDF via Crossref API
    print("Tentando busca PDF via Crossref API...")
    pdf_url = get_crossref_pdf_link(doi)
    if pdf_url:
        if download_file(pdf_url, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via Crossref API")
            return True
        
    # 5. Buscar PDF via OpenAlex
    print("Tentando buscar PDF via OpenAlex...")
    pdf_url = get_openalex_pdf_link(doi)
    if pdf_url:
        if download_file(pdf_url, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via OpenAlex")
            return True

    # 6. Buscar PDF via Unpaywall
    print("Tentando buscar PDF via Unpaywall...")
    pdf_url = get_unpaywall_pdf_link(doi)
    if pdf_url:
        if download_file(pdf_url, pdf_path):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via Unpaywall")
            return True
    
    # Se chegamos aqui, todas as tentativas falharam
    # Adicionar o DOI à lista de falhas para tentar depois com GS e PyPaperBot
    print(f"Método principais falharam para {doi}. Adicionando à lista para tentar mais tarde.")
    failed_entries.append(entry)
    
    return False

# =====================================================================
# Processamento em lote dos artigos que falharam
# =====================================================================

def batch_download_google_scholar(failed_entries, pdf_dir, logs):
    """
    Tenta baixar em lote todos os artigos falhos usando o Google Scholar.
    Retorna a lista de entradas que ainda falharam.
    """
    config = load_config()
    if not config.get('enable_search_link_file_by_google_scholars', False):
        print("Download via Google Scholar desabilitado nas configurações.")
        return failed_entries
    
    still_failed = []
    print("\n\n=================================================")
    print("TENTATIVA EM LOTE VIA GOOGLE SCHOLAR")
    print(f"Tentando baixar {len(failed_entries)} artigos via Google Scholar")
    print("=================================================\n")
    
    for entry in failed_entries:
        print("--------------------------------------------------")
        doi = entry.get("doi", "").strip()
        filename = sanitize_filename(doi) + ".pdf"
        pdf_path = os.path.join(pdf_dir, filename)
        
        # Já verifica se o arquivo foi baixado por outro método entre tentativas
        if os.path.exists(pdf_path):
            print(f"PDF já baixado: {pdf_path}")
            logs["downloaded"].append(f"{doi} -> PDF baixado entre tentativas")
            continue
            
        success = False
        
        # Buscar apenas por DOI (removida a busca por título)
        if doi:
            print(f"Tentando buscar PDF via Google Scholar (por DOI): {doi}")
            pdf_url = fetch_article_by_doi(doi)
            if pdf_url and pdf_url != 'PDF não encontrado.' and pdf_url != "Artigo não encontrado." and not pdf_url.startswith("Erro ao buscar artigo"):
                if download_file(pdf_url, pdf_path):
                    print(f"PDF salvo: {pdf_path}\n")
                    logs["downloaded"].append(f"{doi} -> PDF via busca Google Scholar (por DOI) em lote")
                    success = True
        
        if not success:
            still_failed.append(entry)
            print(f"Google Scholar falhou para {doi}")
            
        print("--------------------------------------------------\n")
    
    return still_failed

def batch_download_pypaperbot(failed_entries, pdf_dir, logs):
    """
    Tenta baixar em lote todos os artigos falhos usando o PyPaperBot.
    Se falhar, tenta baixar o HTML e converter para Markdown como último recurso.
    """
    config = load_config()
    if not config.get('enable_PyPaperBot_download', False):
        print("Download via PyPaperBot desabilitado nas configurações.")
        return failed_entries
    else:
        still_failed_entries = []
        print("\n\n=================================================")
        print("TENTATIVA EM LOTE VIA PYPAPERBOT")
        print(f"Tentando baixar {len(failed_entries)} artigos via PyPaperBot")
        print("=================================================\n")
        
        # Criar arquivo temporário com todos os DOIs
        temp_doi_file = os.path.join(tempfile.gettempdir(), "batch_doi.txt")
        try:
            with open(temp_doi_file, "w", encoding="utf-8") as f:
                for entry in failed_entries:
                    doi = entry.get("doi", "").strip()
                    if doi:
                        f.write(doi + "\n")
            
            # Tentar executar o PyPaperBot para todos os DOIs
            try:
                from PyPaperBot import __main__ as pypaperbot_main
                old_argv = sys.argv.copy()
                sys.argv = ["PyPaperBot", "--doi-file", temp_doi_file, "--dwn-dir", pdf_dir, "--use-doi-as-filename"]
                try:
                    pypaperbot_main.main()
                finally:
                    sys.argv = old_argv
                    
                # Verificar quais foram baixados
                for entry in failed_entries:
                    doi = entry.get("doi", "").strip()
                    filename = sanitize_filename(doi) + ".pdf"
                    pdf_path = os.path.join(pdf_dir, filename)
                    if os.path.exists(pdf_path):
                        print(f"PyPaperBot baixou com sucesso: {doi}")
                        logs["downloaded"].append(f"{doi} -> PDF via PyPaperBot em lote")
                    else:
                        still_failed_entries.append(entry)
                        
            except ImportError:
                print("PyPaperBot não está instalado ou não pode ser importado.")
                still_failed_entries = failed_entries
        except Exception as e:
            print(f"Erro na integração com o PyPaperBot em lote: {e}")
            still_failed_entries = failed_entries
        finally:
            if os.path.exists(temp_doi_file):
                os.remove(temp_doi_file)
    
    # Última tentativa: converter HTML para Markdown para os que ainda falharam
    if config.get('enable_save_md_to_lost_papers', False):
        print("\n\n=================================================")
        print("ÚLTIMA TENTATIVA: CONVERTER HTML PARA MARKDOWN")
        print(f"Tentando baixar {len(still_failed_entries)} artigos em formato HTML/Markdown")
        print("=================================================\n")
        
        for entry in still_failed_entries:
            doi = entry.get("doi", "").strip()
            if not doi:
                continue
                
            doi_url = "https://doi.org/" + doi
            print(f"Tentando baixar HTML para {doi} e converter para Markdown...")
            
            try:
                response = requests.get(doi_url, timeout=20, headers=HEADERS)
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
                    logs["markdown_saved"].append(f"{doi} -> HTML convertido para Markdown via DOI")
                else:
                    print(f"Falha ao obter HTML para {doi}. Status: {response.status_code}")
                    logs["failed"].append(f"{doi} -> Falha em todas as estratégias")
            except Exception as e:
                print(f"Erro ao baixar/converter HTML para {doi}: {e}")
                logs["failed"].append(f"{doi} -> Falha em todas as estratégias")
    
    return still_failed_entries

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
    # Limpar arquivos antigos de execuções anteriores
    print("\nVerificando e removendo arquivos antigos...\n")
    files_to_clean = [
        os.path.join(pdf_dir, "downloaded_log.txt"),
        os.path.join(pdf_dir, "failed_log.txt"),
        os.path.join(pdf_dir, "markdown_log.txt"),
        os.path.join(pdf_dir, "result.csv"),
        os.path.join(pdf_dir, "bibtex.bib")
    ]
        
    for file_path in files_to_clean:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Arquivo removido: {file_path}")
            except Exception as e:
                print(f"Não foi possível remover o arquivo {file_path}: {e}")
    
    print("\nIniciando processamento de novos dados...\n")
    
    os.makedirs(pdf_dir, exist_ok=True)

    logs = {
        "downloaded": [],
        "failed": [],
        "markdown_saved": [] # Nova categoria para arquivos markdown
    }
    
    # Lista para armazenar entradas que falharam nos métodos principais
    failed_entries = []

    print("\nInício do processamento...\n")

    arxiv_entries, doi_bibtex_entries = process_bibtex(bibtex_path)
    if doi_file_path and doi_file_path.strip() != "":
        external_dois = read_doi_file(doi_file_path)
        doi_entries = merge_doi_lists(doi_bibtex_entries, external_dois)
    else:
        doi_entries = doi_bibtex_entries

    print("\nProcessando entradas do arXiv...\n")
    for entry in arxiv_entries:
        print("--------------------------------------------------")
        download_arxiv_entry(entry, pdf_dir, logs)
        print("--------------------------------------------------\n")

    print("\nProcessando entradas com DOI...\n")
    for entry in doi_entries:
        print("--------------------------------------------------")
        download_doi_entry(entry, pdf_dir, logs, failed_entries)
        print("--------------------------------------------------\n")

    # Processamento em lote dos artigos que falharam
    if failed_entries:
        print(f"\nTentando baixar {len(failed_entries)} artigos que falharam nos métodos principais...\n")
        # Primeiro, tenta Google Scholar em lote
        failed_entries = batch_download_pypaperbot(failed_entries, pdf_dir, logs)
        
    # Depois, tenta PyPaperBot em lote para os que ainda falharam
    print(f"\nTentando baixar {len(failed_entries)} artigos que falharam nos métodos principais...\n")
    if failed_entries:
        failed_entries = batch_download_google_scholar(failed_entries, pdf_dir, logs)
        
    if failed_entries:
        print(f"\n{len(failed_entries)} artigos ainda falharam após tentativas em lote.\n")
        # Exibir detalhes dos artigos que falharam
        print("\nDetailhes dos artigos com falha no download:")
        print("-" * 90)
        print(f"{'TÍTULO':<71} | {'DOI':<21}")
        print("-" * 90)
        
        # Adicionar ao log as entradas que falharam após todas as tentativas
        for entry in failed_entries:
            title = entry.get("title", "Titulo Não Encontrado")
            doi = entry.get("doi", "").strip()
            entry_id = entry.get("ID", "")
            
            # Imprimir na tela o título e DOI de cada artigo que falhou
            title_display = (title[:47] + "...") if len(title) > 47 else title
            print(f"{title_display:<50} | {doi:<20}")
            
            log_entry = f"ID: {entry_id} -> DOI: {doi} -> Título: {title} -> Falha em todas as estratégias"
            logs["failed"].append(log_entry)
        print("-" * 70)
    else:
        print("\nTodos os artigos foram baixados com sucesso pelos métodos principais.\n")

    downloaded_log_path = os.path.join(pdf_dir, "downloaded_log.txt")
    failed_log_path = os.path.join(pdf_dir, "failed_log.txt")
    markdown_log_path = os.path.join(pdf_dir, "markdown_log.txt")
    
    try:
        with open(downloaded_log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs["downloaded"]))
        with open(failed_log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs["failed"]))
        if load_config().get('enable_save_md_to_lost_papers', False):
            with open(markdown_log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(logs["markdown_saved"]))
            print(f"Logs salvos:\n - Sucesso: {downloaded_log_path}\n - Falhas: {failed_log_path}\n - Markdown: {markdown_log_path}\n")
    except Exception as e:
        print(f"Erro ao salvar os logs: {e}")

    # Exibir destaque em vermelho para artigos que não foram baixados
    if logs["failed"]:
        # Cores ANSI para terminal
        RED = '\033[91m'
        BOLD = '\033[1m'
        END = '\033[0m'
        
        print(f"\n{RED}{BOLD}================================================={END}")
        print(f"{RED}{BOLD}  ATENÇÃO: {len(logs['failed'])} ARTIGOS NÃO FORAM BAIXADOS!  {END}")
        print(f"{RED}{BOLD}  Verifique o arquivo de log: {failed_log_path}  {END}")
        print(f"{RED}{BOLD}================================================={END}\n")

    print("Processamento concluído.\n")