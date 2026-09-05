import os
import sys
import urllib
import tempfile
import requests
import argparse
import time  
import random
import yaml
import re
from typing import Optional, Tuple, Dict, List, Set
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
load_dotenv(os.path.abspath("config/.env"))
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

PDF_DOWNLOAD_HEADERS = {
    'Accept': 'application/pdf,application/octet-stream;q=0.9,*/*;q=0.8',
    'Accept-Language': HEADERS.get('Accept-Language', 'en-US,en;q=0.9'),
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION_PREPARED_HOSTS: Set[str] = set()



def sanitize_filename(doi):
    """
    Converte um DOI em um nome de arquivo válido:
    substitui caracteres não alfanuméricos (exceto pontos e hífens) por underline.
    """
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return urllib.parse.quote(doi, safe='')


def normalize_doi(doi: str) -> str:
    """Normaliza um DOI para comparação (sem prefixo e em minúsculas)."""
    if not doi:
        return ""
    normalized = doi.strip().lower()
    normalized = normalized.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return normalized


def prepare_session_for_domain(session: requests.Session, url: str, timeout: int = 20) -> None:
    """Garantir que o domínio possua cookies básicos antes de baixar PDFs."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return
    host = (parsed.netloc or "").lower()
    if not host or host in SESSION_PREPARED_HOSTS:
        return

    base_url = urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, "/", "", ""))
    try:
        session.get(base_url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"Falha ao inicializar sessão para {base_url}: {exc}")
    SESSION_PREPARED_HOSTS.add(host)


def warmup_session(session: requests.Session, url: Optional[str], timeout: int = 20) -> None:
    """Realiza uma requisição HTML para configurar cookies/redirecionamentos necessários."""
    if not url:
        return
    if url.lower().endswith(".pdf"):
        return
    try:
        session.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"Falha ao aquecer sessão com {url}: {exc}")


def build_pdf_referers(original_url: str, sanitized: Optional[str], sanitized_alt: Optional[str]) -> List[str]:
    """Gera candidatos de Referer/URLs HTML a visitar antes de tentar baixar o PDF."""
    referers: List[str] = []

    def add_candidate(candidate: Optional[str]) -> None:
        if candidate and candidate not in referers:
            referers.append(candidate)

    add_candidate(sanitized)
    add_candidate(sanitized_alt)

    try:
        parsed = urllib.parse.urlsplit(original_url)
    except ValueError:
        parsed = urllib.parse.SplitResult("", "", "", "", "")

    netloc_lower = parsed.netloc.lower()
    base_url = urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, "/", "", ""))
    path = parsed.path or ""

    if "mdpi.com" in netloc_lower and "/pdf" in path:
        add_candidate(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path.replace("/pdf", ""), "", "")))

    if "ieeexplore.ieee.org" in netloc_lower:
        match = re.search(r'/(\d+)\.pdf', path)
        if match:
            article_id = match.group(1)
            base_doc = f"{parsed.scheme}://{parsed.netloc}/document/{article_id}"
            stamp = f"{parsed.scheme}://{parsed.netloc}/stamp/stamp.jsp?tp=&arnumber={article_id}"
            add_candidate(base_doc)
            add_candidate(stamp)

    if "sciencedirect.com" in netloc_lower:
        trimmed_path = path
        if "/pdf" in trimmed_path:
            trimmed_path = trimmed_path.split("/pdf", 1)[0]
        add_candidate(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, trimmed_path, "", "")))

    add_candidate(base_url)
    return referers


def extract_pdf_from_html(base_url: str, html_content: str) -> Optional[str]:
    """
    Procura referências a PDFs dentro de uma resposta HTML (IEEEXplore, etc.).
    Retorna a URL absoluta do PDF se encontrar.
    """
    if not html_content:
        return None

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    # Tentativas usando BeautifulSoup (mais robusto)
    if BeautifulSoup:
        soup = BeautifulSoup(html_content, "html.parser")

        iframe = soup.find("iframe", src=lambda s: isinstance(s, str) and s.lower().endswith(".pdf"))
        if iframe and iframe.get("src"):
            return urllib.parse.urljoin(base_url, iframe["src"])

        meta_refresh = soup.find("meta", attrs={"http-equiv": lambda v: isinstance(v, str) and v.lower() == "refresh"})
        if meta_refresh:
            content = meta_refresh.get("content", "")
            if "url=" in content.lower():
                target = content.split("=", 1)[-1].strip()
                if target.lower().endswith(".pdf"):
                    return urllib.parse.urljoin(base_url, target)

        link = soup.find("a", href=lambda h: isinstance(h, str) and h.lower().endswith(".pdf"))
        if link and link.get("href"):
            return urllib.parse.urljoin(base_url, link["href"])

    # Fallback com regex simples (caso BeautifulSoup não esteja instalado)
    candidates = []

    # Atributos comuns (href/src/etc)
    attribute_pattern = r'(?:href|src|content|data-[\w-]+)\s*=\s*["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']'
    candidates.extend(re.findall(attribute_pattern, html_content, flags=re.IGNORECASE))

    # JS ou JSON embutido (ex.: pdfUrl="...")
    js_pattern = r'pdf\s*url[^"\']*["\':=]\s*["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']'
    candidates.extend(re.findall(js_pattern, html_content, flags=re.IGNORECASE))

    # Qualquer string .pdf entre aspas
    generic_pattern = r'["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']'
    candidates.extend(re.findall(generic_pattern, html_content, flags=re.IGNORECASE))

    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        # Poucos casos trazem HTML escaped (&amp;)
        normalized = normalized.replace("&amp;", "&")
        return urllib.parse.urljoin(base_url, normalized)

    return None

def validate_pdf_file(file_path: str, expected_size: Optional[int] = None, min_size_bytes: int = 1024) -> Tuple[bool, str]:
    """Validate if a PDF file has the expected structure and size."""
    if not os.path.exists(file_path):
        return False, "Arquivo PDF não encontrado após download."

    file_size = os.path.getsize(file_path)
    if expected_size is not None and file_size != expected_size:
        return False, (
            f"Tamanho inconsistente: esperado {expected_size} bytes, obtido {file_size} bytes"
        )

    if file_size < min_size_bytes:
        return False, f"Arquivo muito pequeno para ser um PDF válido ({file_size} bytes)."

    try:
        with open(file_path, "rb") as pdf_file:
            header = pdf_file.read(5)
            if header != b"%PDF-":
                return False, "Assinatura PDF inválida."

            try:
                pdf_file.seek(-1024, os.SEEK_END)
            except OSError:
                pdf_file.seek(0, os.SEEK_END)
                pdf_file.seek(0)
            tail = pdf_file.read()
            if b"%%EOF" not in tail:
                return False, "Marcador %%EOF não encontrado no final do PDF."
    except OSError as exc:
        return False, f"Erro ao validar PDF: {exc}"

    return True, f"PDF válido ({file_size} bytes)."


def _save_response_content(response: requests.Response, file_path: str, binary: bool = True, skip_validation: bool = False) -> bool:
    """Persist HTTP response content to disk using a temporary file and integrity checks.
    
    Args:
        response: HTTP response object
        file_path: Path where to save the file
        binary: Whether to save as binary file
        skip_validation: If True, skips PDF validation checks
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    temp_path = f"{file_path}.part"
    success = False
    expected_length: Optional[int] = None

    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            expected_length = int(content_length)
        except ValueError:
            expected_length = None

    try:
        if binary:
            bytes_written = 0
            with open(temp_path, "wb") as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                        bytes_written += len(chunk)

            if not skip_validation and expected_length is not None and bytes_written != expected_length:
                print(
                    "Tamanho de arquivo recebido difere do esperado. Tentando próxima estratégia."
                )
                return False

            if file_path.lower().endswith(".pdf") and not skip_validation:
                is_valid, message = validate_pdf_file(temp_path, expected_size=expected_length)
                if not is_valid:
                    print(f"Falha na validação do PDF: {message}")
                    return False
                print(f"Verificação do PDF concluída: {message}")
            elif skip_validation and file_path.lower().endswith(".pdf"):
                print(f"⚠️  Validação de PDF ignorada. Arquivo salvo com {bytes_written} bytes.")

        else:
            response.encoding = response.encoding or "utf-8"
            with open(temp_path, "w", encoding=response.encoding) as temp_file:
                temp_file.write(response.text)

        os.replace(temp_path, file_path)
        success = True
        return True
    finally:
        if not success and os.path.exists(temp_path):
            os.remove(temp_path)


def download_file(
    url,
    file_path,
    binary=True,
    timeout=20,
    skip_validation=False,
    session: Optional[requests.Session] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    allow_redirects: bool = True,
    depth: int = 0,
    visited: Optional[Set[str]] = None,
):
    """
    Tenta fazer download do conteúdo da URL e salvar em file_path.
    
    Args:
        url: URL to download from
        file_path: Path where to save the file
        binary: Whether to save as binary file
        timeout: Request timeout in seconds
        skip_validation: If True, skips PDF validation checks
        session: Optional requests.Session to reuse cookies
        extra_headers: Headers adicionais para a requisição
        allow_redirects: Whether to allow HTTP redirects
    
    Returns:
        bool: True if download was successful, False otherwise
    """
    response: Optional[requests.Response] = None
    visited = visited or set()
    if url in visited:
        print(f"URL {url} já foi visitada nesta cadeia. Interrompendo para evitar loop.")
        return False
    visited.add(url)
    if depth > 3:
        print(f"Profundidade máxima atingida ao tentar baixar {url}.")
        return False
    try:
        http_client = session or requests
        headers = dict(HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        response = http_client.get(
            url,
            stream=True,
            timeout=timeout,
            headers=headers,
            allow_redirects=allow_redirects,
        )
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if (
                binary
                and file_path.lower().endswith(".pdf")
                and not skip_validation
                and content_type
                and "pdf" not in content_type.lower()
                and "octet-stream" not in content_type.lower()
                and "html" not in content_type.lower()
            ):
                print(
                    f"Conteúdo inesperado ao baixar {url}. Content-Type: {content_type}"
                )
                return False
            if (
                binary
                and file_path.lower().endswith(".pdf")
                and content_type
                and "html" in content_type.lower()
            ):
                html = response.text
                pdf_candidate = extract_pdf_from_html(response.url, html)
                if pdf_candidate:
                    print(f"HTML retornou referência para PDF: {pdf_candidate}")
                    new_headers = dict(PDF_DOWNLOAD_HEADERS)
                    if extra_headers:
                        new_headers.update(extra_headers)
                    new_headers.setdefault("Referer", response.url)
                    return download_file(
                        pdf_candidate,
                        file_path,
                        binary=binary,
                        timeout=timeout,
                        skip_validation=skip_validation,
                        session=session,
                        extra_headers=new_headers,
                        allow_redirects=allow_redirects,
                        depth=depth + 1,
                        visited=visited,
                    )
                return False
            if _save_response_content(response, file_path, binary=binary, skip_validation=skip_validation):
                return True
            print(f"Verificação de integridade falhou para {url}")
            return False

        print(f"Falha ao baixar {url} - Status code: {response.status_code}")
        return False
    except requests.exceptions.Timeout:
        print(f"Timeout ao baixar {url}")
        return False
    except requests.exceptions.RequestException as exc:
        print(f"Erro na requisição ao baixar {url}: {exc}")
        return False
    except Exception as exc:
        print(f"Erro inesperado ao baixar {url}: {exc}")
        return False
    finally:
        if response is not None:
            response.close()


def download_pdf_url(url: Optional[str], file_path: str, timeout: int = 20, skip_validation: bool = False) -> bool:
    """
    Envelopa download_file para lidar com URLs de PDF com queries, cookies e bloqueios.
    Tenta a URL original, versões sanitizadas e combinações de Referer/cookies para domínios mais exigentes.
    """
    if not url:
        return False

    session = SESSION
    prepare_session_for_domain(session, url, timeout)

    url_candidates: List[str] = []

    def add_candidate(candidate: Optional[str]) -> None:
        if candidate:
            candidate = candidate.strip()
            if candidate and candidate not in url_candidates:
                url_candidates.append(candidate)

    add_candidate(url)

    try:
        parsed_original = urllib.parse.urlsplit(url)
    except ValueError:
        parsed_original = urllib.parse.SplitResult("", "", "", "", "")

    sanitized_no_query = urllib.parse.urlunsplit(
        (parsed_original.scheme, parsed_original.netloc, parsed_original.path, "", "")
    )
    add_candidate(sanitized_no_query)

    decoded_path_original = urllib.parse.unquote(parsed_original.path or "")
    sanitized_decoded = None
    if "?" in decoded_path_original:
        sanitized_decoded = urllib.parse.urlunsplit(
            (parsed_original.scheme, parsed_original.netloc, decoded_path_original.split("?", 1)[0], "", "")
        )
        add_candidate(sanitized_decoded)

    tried: Set[str] = set()
    for candidate in url_candidates:
        if not candidate or candidate in tried:
            continue
        tried.add(candidate)

        prepare_session_for_domain(session, candidate, timeout)

        try:
            parsed_candidate = urllib.parse.urlsplit(candidate)
        except ValueError:
            parsed_candidate = urllib.parse.SplitResult("", "", "", "", "")

        sanitized_candidate = urllib.parse.urlunsplit(
            (parsed_candidate.scheme, parsed_candidate.netloc, parsed_candidate.path, "", "")
        )
        decoded_candidate_path = urllib.parse.unquote(parsed_candidate.path or "")
        sanitized_candidate_alt = None
        if "?" in decoded_candidate_path:
            sanitized_candidate_alt = urllib.parse.urlunsplit(
                (parsed_candidate.scheme, parsed_candidate.netloc, decoded_candidate_path.split("?", 1)[0], "", "")
            )

        referers = build_pdf_referers(candidate, sanitized_candidate, sanitized_candidate_alt)
        looks_like_pdf = sanitized_candidate.lower().endswith(".pdf")

        if not looks_like_pdf:
            warmup_session(session, candidate, timeout)
            html_referers: List[Optional[str]] = [None] + referers
            for html_ref in html_referers:
                if html_ref:
                    prepare_session_for_domain(session, html_ref, timeout)
                    warmup_session(session, html_ref, timeout)
                html_headers = {'Referer': html_ref} if html_ref else None
                if download_file(
                    candidate,
                    file_path,
                    binary=True,
                    timeout=timeout,
                    skip_validation=skip_validation,
                    session=session,
                    extra_headers=html_headers,
                ):
                    if candidate != url:
                        print(f"Download obtido via URL alternativa: {candidate}")
                    return True

        for referer in referers:
            prepare_session_for_domain(session, referer, timeout)
            warmup_session(session, referer, timeout)
            pdf_headers = dict(PDF_DOWNLOAD_HEADERS)
            pdf_headers["Referer"] = referer
            if download_file(
                candidate,
                file_path,
                binary=True,
                timeout=timeout,
                skip_validation=skip_validation,
                session=session,
                extra_headers=pdf_headers,
            ):
                if candidate != url:
                    print(f"Download do PDF bem-sucedido usando URL sanitizada: {candidate}")
                return True

        if download_file(
            candidate,
            file_path,
            binary=True,
            timeout=timeout,
            skip_validation=skip_validation,
            session=session,
            extra_headers=PDF_DOWNLOAD_HEADERS,
        ):
            if candidate != url:
                print(f"Download do PDF bem-sucedido usando URL sanitizada: {candidate}")
            return True
    return False


# =====================================================================
# Carregamento de configurações
# =====================================================================

def load_config():
    """
    Carrega as configurações do arquivo YAML.
    """
    config_path = os.path.abspath("config/general_config.yaml")
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

def download_arxiv_entry(entry, pdf_dir, logs, skip_validation=False):
    """
    Faz o download de um artigo arXiv.
    Tenta:
      1. Obter o PDF diretamente (substituindo "abs" por "pdf" na URL).
      2. Se falhar, baixa o HTML (substituindo "abs" por "html"), converte para Markdown
         e salva na pasta "markdown" (dentro de pdf_dir).
    Registra no log o método utilizado.
    
    Args:
        entry: BibTeX entry dictionary
        pdf_dir: Directory to save PDFs
        logs: Logs dictionary
        skip_validation: If True, skips PDF validation checks
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
    if download_pdf_url(pdf_url, pdf_path, skip_validation=skip_validation):
        print(f"PDF salvo: {pdf_path}\n")
        logs["downloaded"].append(f"{doi} -> PDF via arXiv (direto)")
        return True
    else:
        print("Falha no download do PDF. Tentando HTML para Markdown...")
        html_url = url.replace("abs", "html")
        temp_html = os.path.join(tempfile.gettempdir(), sanitize_filename(doi) + ".html")
        if download_file(html_url, temp_html, binary=False, skip_validation=skip_validation):
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
            headers = {**HEADERS, 'Accept': 'application/json'}
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
            headers = {**HEADERS, 'Accept': 'application/json', 'From': email}
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
    target_doi = normalize_doi(doi)
    try:
        # Introduce random delay before Google Scholar search
        delay = random.randint(1, 20)
        print(f"Aguardando {delay} segundos antes da busca no Google Scholar...")
        time.sleep(delay)

        search_query = scholarly.search_pubs(doi)
        for index, article in enumerate(search_query):
            if index >= 5:
                break
            try:
                scholarly.fill(article)
            except Exception as fill_error:
                print(f"Falha ao carregar detalhes do resultado {index + 1}: {fill_error}")
                continue

            bib = article.get('bib', {})
            result_doi = normalize_doi(bib.get('doi', ''))
            if target_doi and result_doi and result_doi != target_doi:
                print(f"Resultado {index + 1} retornou DOI diferente ({result_doi}). Buscando próximo.")
                continue

            pdf_url = article.get('eprint_url') or bib.get('eprint_url')
            if not pdf_url:
                pub_url = article.get('pub_url')
                if pub_url and pub_url.lower().endswith(".pdf"):
                    pdf_url = pub_url

            if pdf_url:
                print(f"URL do PDF encontrada no Google Scholar (por DOI): {pdf_url}")
                return pdf_url
            else:
                print(f"Resultado {index + 1} sem campo 'eprint_url'. Tentando próximo.")

        print(f"Artigo não encontrado no Google Scholar para DOI: {doi}")
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
        for index, article in enumerate(search_query):
            if index >= 5:
                break
            try:
                scholarly.fill(article)
            except Exception as fill_error:
                print(f"Falha ao carregar detalhes do resultado {index + 1}: {fill_error}")
                continue

            pdf_url = article.get('eprint_url')
            if not pdf_url:
                bib = article.get('bib', {})
                pdf_url = bib.get('eprint_url')
            if not pdf_url:
                pub_url = article.get('pub_url')
                if pub_url and pub_url.lower().endswith(".pdf"):
                    pdf_url = pub_url

            if pdf_url:
                print(f"URL do PDF encontrada no Google Scholar (por título): {pdf_url}")
                return pdf_url
            else:
                print(f"Resultado {index + 1} sem campo 'eprint_url'. Tentando próximo.")

        print(f"Artigo não encontrado no Google Scholar para título: {title}")
        return None
    except Exception as e:
        print(f"Erro ao buscar PDF no Google Scholar por título: {e} - Timeout possivelmente atingido.")
        return None


def download_elsevier_api(doi, pdf_path, skip_validation=False, timeout=40):
    """
    Baixa o full-text de um artigo Elsevier via a Article Retrieval API
    (https://api.elsevier.com/content/article/doi/<doi>).

    O entitlement do full-text é por IP institucional (ex.: VPN da USP); a API key vem de
    ELSEVIER_API_KEY (config/.env) e, opcionalmente, ELSEVIER_INSTTOKEN. É a via confiável
    para a Elsevier/ScienceDirect, que bloqueia download direto via requests e navegador.

    Returns:
        bool: True se um PDF válido foi salvo.
    """
    api_key = os.getenv("ELSEVIER_API_KEY", "").strip()
    if not api_key:
        return False

    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/pdf"}
    insttoken = os.getenv("ELSEVIER_INSTTOKEN", "").strip()
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken

    try:
        print("Tentando baixar via Elsevier API...")
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
            with open(pdf_path, "wb") as f:
                f.write(resp.content)
            if not skip_validation:
                ok, msg = validate_pdf_file(pdf_path)
                if not ok:
                    print(f"Elsevier API: PDF inválido ({msg}).")
                    os.remove(pdf_path)
                    return False
            return True
        print(f"Elsevier API não retornou PDF (HTTP {resp.status_code}).")
    except Exception as e:
        print(f"Erro na Elsevier API: {e}")
    return False


def download_doi_entry(entry, pdf_dir, logs, failed_entries, skip_validation=False):
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
    
    Args:
        entry: BibTeX entry dictionary
        pdf_dir: Directory to save PDFs
        logs: Logs dictionary
        failed_entries: List to store failed entries
        skip_validation: If True, skips PDF validation checks
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

    # 1b. Elsevier/ScienceDirect: a Article Retrieval API (entitlement por IP) é a única via
    #     confiável — o download direto e o navegador são bloqueados pelo publisher.
    if doi.startswith("10.1016") and os.getenv("ELSEVIER_API_KEY", "").strip():
        if download_elsevier_api(doi, pdf_path, skip_validation=skip_validation):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via Elsevier API")
            return True

    # 2. Tentando baixar via campo url_pdf
    url_pdf = entry.get("url_pdf", "")
    print(f"Tentando download via campo url_pdf: {url_pdf}")
    if url_pdf:
        if download_pdf_url(url_pdf, pdf_path, skip_validation=skip_validation):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via campo url_pdf")
            return True
    else:
        print("Falha ao baixar via campo url_pdf. Tentando baixar via DOI...")

    # 3. Download direto via DOI
    doi_url = "https://doi.org/" + doi
    print(f"Tentando download direto via DOI: {doi_url}")
    response: Optional[requests.Response] = None
    try:
        response = requests.get(
            doi_url,
            stream=True,
            timeout=20,
            headers=HEADERS,
            allow_redirects=True,
        )
        content_type = response.headers.get("Content-Type", "") if response else ""
        if response is not None and response.status_code == 200 and "pdf" in content_type.lower():
            if _save_response_content(response, pdf_path, binary=True, skip_validation=skip_validation):
                print(f"PDF salvo: {pdf_path}\n")
                logs["downloaded"].append(f"{doi} -> PDF via DOI direto")
                return True
            print("Validação do PDF falhou após download via DOI direto. Tentando outras fontes...")
        else:
            print("Download direto não retornou PDF. Tentando encontrar link de PDF em bases acadêmicas...")
    except Exception as e:
        print(f"Erro no download direto via DOI: {e}")
    finally:
        if response is not None:
            response.close()

    # 4. Buscar PDF via Crossref API
    print("Tentando busca PDF via Crossref API...")
    pdf_url = get_crossref_pdf_link(doi)
    if pdf_url:
        if download_pdf_url(pdf_url, pdf_path, skip_validation=skip_validation):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via Crossref API")
            return True
    
    # 5. Buscar PDF via OpenAlex
    print("Tentando buscar PDF via OpenAlex...")
    pdf_url = get_openalex_pdf_link(doi)
    if pdf_url:
        if download_pdf_url(pdf_url, pdf_path, skip_validation=skip_validation):
            print(f"PDF salvo: {pdf_path}\n")
            logs["downloaded"].append(f"{doi} -> PDF via OpenAlex")
            return True

    # 6. Buscar PDF via Unpaywall
    print("Tentando buscar PDF via Unpaywall...")
    pdf_url = get_unpaywall_pdf_link(doi)
    if pdf_url:
        if download_pdf_url(pdf_url, pdf_path, skip_validation=skip_validation):
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

def batch_download_google_scholar(failed_entries, pdf_dir, logs, skip_validation=False):
    """
    Tenta baixar em lote todos os artigos falhos usando o Google Scholar.
    Retorna a lista de entradas que ainda falharam.
    
    Args:
        failed_entries: List of failed BibTeX entries
        pdf_dir: Directory to save PDFs
        logs: Logs dictionary
        skip_validation: If True, skips PDF validation checks
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
                if download_pdf_url(pdf_url, pdf_path, skip_validation=skip_validation):
                    print(f"PDF salvo: {pdf_path}\n")
                    logs["downloaded"].append(f"{doi} -> PDF via busca Google Scholar (por DOI) em lote")
                    success = True
        
        if not success:
            still_failed.append(entry)
            print(f"Google Scholar falhou para {doi}")
            
        print("--------------------------------------------------\n")
    
    return still_failed

# Prefixos de DOI de publishers protegidos por Cloudflare: o navegador automatizado
# (headless OU headful) fica preso no desafio JS, então pulamos direto para o PyPaperBot.
CLOUDFLARE_DOI_PREFIXES = ("10.1145", "10.3390", "10.1080", "10.1002", "10.1111")

# User-Agent realista para o contexto do navegador.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


async def _playwright_fetch_one(context, doi, pdf_dir, skip_validation):
    """Resolve e baixa o PDF de UM artigo usando a sessão do navegador (acesso por IP)."""
    pdf_path = os.path.join(pdf_dir, sanitize_filename(doi) + ".pdf")
    if os.path.exists(pdf_path):
        return True

    page = await context.new_page()
    try:
        try:
            await page.goto("https://doi.org/" + doi, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass  # mesmo com erro de navegação, ainda tentamos achar o PDF pela URL final

        url = page.url
        candidates: List[str] = []

        # IEEE: o PDF fica num iframe da página stamp.jsp (getPDF.jsp?arnumber=...)
        m = re.search(r"/document/(\d+)", url)
        if "ieee" in url.lower() and m:
            num = m.group(1)
            try:
                await page.goto(f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={num}",
                                wait_until="domcontentloaded", timeout=45000)
                srcs = await page.eval_on_selector_all("iframe", "els => els.map(e => e.src)")
                candidates += [s for s in srcs if s and ("getpdf" in s.lower() or ".pdf" in s.lower() or "ielx" in s.lower())]
            except Exception:
                pass
            candidates.append(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={num}&ref=")

        # Genérico: meta citation_pdf_url, links e iframes que apontem para PDF.
        try:
            meta = await page.eval_on_selector_all('meta[name="citation_pdf_url"]', "els => els.map(e => e.content)")
            candidates += [x for x in meta if x]
            hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            candidates += [h for h in hrefs if h and "pdf" in h.lower()][:5]
            ifr = await page.eval_on_selector_all("iframe", "els => els.map(e => e.src)")
            candidates += [s for s in ifr if s and "pdf" in s.lower()]
        except Exception:
            pass

        # Tenta cada candidato baixando via a sessão autenticada do navegador.
        seen = set()
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            try:
                resp = await context.request.get(cand, timeout=60000)
                if resp.status != 200:
                    continue
                body = await resp.body()
                if body[:5] != b"%PDF-":
                    continue
                with open(pdf_path, "wb") as f:
                    f.write(body)
                if not skip_validation:
                    ok, msg = validate_pdf_file(pdf_path)
                    if not ok:
                        os.remove(pdf_path)
                        continue
                print(f"✓ Playwright baixou: {doi} ({len(body)} bytes)")
                return True
            except Exception:
                continue
        return False
    finally:
        await page.close()


async def _playwright_download_batch(entries, pdf_dir, concurrency, skip_validation, logs):
    """Roda os downloads de navegador concorrentemente (1 browser, N páginas)."""
    from playwright.async_api import async_playwright
    import asyncio

    downloaded: Set[str] = set()
    sem = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=BROWSER_UA, viewport={"width": 1280, "height": 900})

        async def worker(entry):
            doi = entry.get("doi", "").strip()
            if not doi:
                return
            async with sem:
                ok = await _playwright_fetch_one(context, doi, pdf_dir, skip_validation)
            if ok:
                downloaded.add(doi)
                logs["downloaded"].append(f"{doi} -> PDF via Playwright (navegador headless)")

        await asyncio.gather(*[worker(e) for e in entries], return_exceptions=True)
        await context.close()
        await browser.close()

    return downloaded


def batch_download_playwright(failed_entries, pdf_dir, logs, skip_validation=False):
    """
    Fallback preferencial: baixa os artigos que falharam usando um navegador REAL headless
    (Playwright), aproveitando o acesso institucional por IP (ex.: VPN da USP). Resolve
    publishers que bloqueiam o `requests` cru mas liberam para navegador (ex.: IEEE).

    Pula prefixos de DOI sabidamente protegidos por Cloudflare (vão para o PyPaperBot, pois
    o desafio JS bloqueia qualquer navegador automatizado). Retorna as entradas que ainda
    falharam.

    Args:
        failed_entries: entradas BibTeX que falharam nos métodos anteriores
        pdf_dir: diretório de saída dos PDFs
        logs: dicionário de logs
        skip_validation: se True, não valida os PDFs baixados
    """
    config = load_config()
    if not config.get('enable_playwright_download', False):
        print("Download via Playwright desabilitado nas configurações.")
        return failed_entries

    try:
        import asyncio  # noqa: F401
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        print("⚠ Playwright não instalado. Rode: pip install playwright && playwright install chromium. Pulando etapa.")
        return failed_entries

    try:
        concurrency = int(os.getenv("DOWNLOAD_BROWSER_CONCURRENT", "8"))
    except (TypeError, ValueError):
        concurrency = 8
    concurrency = max(1, concurrency)

    cloudflare = [e for e in failed_entries if e.get("doi", "").strip().startswith(CLOUDFLARE_DOI_PREFIXES)]
    cf_ids = {id(e) for e in cloudflare}
    todo = [e for e in failed_entries if id(e) not in cf_ids]

    print("\n\n=================================================")
    print("TENTATIVA EM LOTE VIA PLAYWRIGHT (navegador headless)")
    print(f"  candidatos: {len(todo)}  |  Cloudflare pulados (-> PyPaperBot): {len(cloudflare)}")
    print(f"  concorrência: {concurrency} (env DOWNLOAD_BROWSER_CONCURRENT)")
    print("  ⚠ alto paralelismo no IP institucional pode disparar anti-abuso do publisher")
    print("=================================================\n")

    if not todo:
        return failed_entries

    import asyncio
    downloaded = asyncio.run(_playwright_download_batch(todo, pdf_dir, concurrency, skip_validation, logs))

    still_failed = list(cloudflare) + [e for e in todo if e.get("doi", "").strip() not in downloaded]
    print(f"\nPlaywright: {len(downloaded)} baixados / {len(todo) - len(downloaded)} falharam "
          f"(+{len(cloudflare)} Cloudflare encaminhados ao PyPaperBot).\n")
    return still_failed


def batch_download_pypaperbot(failed_entries, pdf_dir, logs, skip_validation=False):
    """
    Tenta baixar em lote todos os artigos falhos usando o PyPaperBot.
    Se falhar, tenta baixar o HTML e converter para Markdown como último recurso.
    
    Args:
        failed_entries: Lista de entradas que falharam nas tentativas anteriores.
        pdf_dir: Diretório onde os PDFs devem ser salvos.
        logs: Dicionário para registrar sucessos, falhas e markdowns.
        skip_validation: Se True, não valida os PDFs gerados pelo PyPaperBot.
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
                        if not skip_validation and pdf_path.lower().endswith(".pdf"):
                            is_valid, message = validate_pdf_file(pdf_path)
                            if not is_valid:
                                print(f"PDF inválido gerado pelo PyPaperBot ({doi}): {message}")
                                logs["failed"].append(f"{doi} -> PyPaperBot retornou arquivo inválido: {message}")
                                try:
                                    os.remove(pdf_path)
                                    print(f"Arquivo inválido removido: {pdf_path}")
                                except OSError as exc:
                                    print(f"Não foi possível remover o arquivo inválido {pdf_path}: {exc}")
                                still_failed_entries.append(entry)
                                continue
                            print(f"Verificação do PDF (PyPaperBot): {message}")
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
                response = requests.get(doi_url, timeout=20, headers=HEADERS, allow_redirects=True)
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

# =====================================================================
# Modo ASSISTIDO (human-in-the-loop) para Cloudflare e demais faltantes
# =====================================================================

def _looks_blocked(page) -> bool:
    """Heurística: a página atual é um desafio (Cloudflare etc.) e não o conteúdo?"""
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    markers = ("just a moment", "um momento", "attention required",
               "verifying you are human", "verificando", "checking your browser")
    if any(m in title for m in markers):
        return True
    if "__cf_chl" in (page.url or ""):
        return True
    return False


def _pdf_candidates(page, doi) -> List[str]:
    """Monta URLs candidatas de PDF: padrões por publisher + meta citation_pdf_url + links."""
    url = page.url or ""
    c: List[str] = []
    if doi.startswith("10.1145"):
        c.append(f"https://dl.acm.org/doi/pdf/{doi}")
    if doi.startswith("10.1080"):
        c += [f"https://www.tandfonline.com/doi/pdf/{doi}",
              f"https://www.tandfonline.com/doi/epdf/{doi}"]
    if doi.startswith(("10.1002", "10.1111")):
        c.append(f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}")
    if doi.startswith("10.1177"):
        c += [f"https://journals.sagepub.com/doi/pdf/{doi}",
              f"https://journals.sagepub.com/doi/epub/{doi}"]
    if "mdpi.com" in url:
        c.append(url.split("?")[0].rstrip("/") + "/pdf")
    m = re.search(r"/document/(\d+)", url)
    if m:
        c.append(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={m.group(1)}&ref=")
    try:
        c += [x for x in page.eval_on_selector_all(
            'meta[name="citation_pdf_url"]', "els => els.map(e => e.content)") if x]
        c += [h for h in page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href)")
            if h and ("pdf" in h.lower() or "/download" in h.lower())][:8]
        c += [s for s in page.eval_on_selector_all(
            "iframe", "els => els.map(e => e.src)") if s and "pdf" in s.lower()]
    except Exception:
        pass
    seen, out = set(), []
    for x in c:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _validate_saved_pdf(pdf_path, skip_validation) -> bool:
    """Valida o PDF salvo; remove se inválido. Retorna True se ok."""
    if skip_validation:
        return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    ok, _msg = validate_pdf_file(pdf_path)
    if not ok and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except Exception:
            pass
    return ok


def _navigate_capture(page, cand, pdf_path, skip_validation, timeout=12000) -> bool:
    """
    Navega até `cand` e captura o PDF de duas maneiras numa única navegação:
      - download por attachment (ex.: MDPI), via expect_download;
      - PDF que ABRE NA TELA (visualizador inline, ex.: OnePetro/eReader), interceptando a
        resposta de rede com content-type application/pdf e salvando os bytes.
    """
    holder = {}

    def on_resp(r):
        try:
            ct = (r.headers.get("content-type") or "").lower()
            if "application/pdf" in ct:
                holder["resp"] = r
        except Exception:
            pass

    page.on("response", on_resp)
    try:
        # Tenta download por attachment.
        try:
            with page.expect_download(timeout=timeout) as dl_info:
                try:
                    page.goto(cand, timeout=timeout)
                except Exception:
                    pass  # navegação vira download (attachment) ou carrega o viewer
            dl_info.value.save_as(pdf_path)
            if _validate_saved_pdf(pdf_path, skip_validation):
                return True
        except Exception:
            pass
        # Sem attachment: usa a resposta-PDF interceptada (PDF aberto na tela).
        resp = holder.get("resp")
        if resp is not None:
            try:
                body = resp.body()
                if body[:5] == b"%PDF-":
                    with open(pdf_path, "wb") as f:
                        f.write(body)
                    if _validate_saved_pdf(pdf_path, skip_validation):
                        return True
            except Exception:
                pass
    finally:
        try:
            page.remove_listener("response", on_resp)
        except Exception:
            pass
    return False


def _assisted_fetch_pdf(context, page, doi, pdf_path, skip_validation) -> bool:
    """
    Tenta baixar o PDF (página já liberada) em duas estratégias:
      1) GET via a sessão do navegador (rápido; serve quando o PDF vem direto);
      2) navegar até a URL e CAPTURAR o download (publishers que servem por attachment,
         ex.: MDPI, cujo /pdf retorna 200 mas não é PDF num GET cru).
    """
    candidates = _pdf_candidates(page, doi)

    # Estratégia 1: GET direto (usa cookies/sessão).
    for cand in candidates:
        try:
            resp = context.request.get(cand, timeout=60000)
            if resp.status == 200 and resp.body()[:5] == b"%PDF-":
                with open(pdf_path, "wb") as f:
                    f.write(resp.body())
                if _validate_saved_pdf(pdf_path, skip_validation):
                    return True
        except Exception:
            continue

    # Estratégia 2: navegar e capturar (download por attachment OU PDF aberto na tela,
    # interceptando a resposta de rede application/pdf). Só os candidatos mais promissores.
    for cand in candidates[:4]:
        if _navigate_capture(page, cand, pdf_path, skip_validation):
            return True

    return False


def batch_download_playwright_assisted(entries, pdf_dir, logs, skip_validation=False):
    """
    Abre um navegador VISÍVEL (headful, perfil persistente) e percorre os artigos faltantes.
    Quando detecta um desafio (Cloudflare), pausa e pede ao usuário resolver na janela e
    teclar ENTER — uma vez por domínio (a liberação cf_clearance é reaproveitada). Depois,
    baixa o PDF via a sessão já liberada. Retorna a lista de DOIs baixados.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠ Playwright não instalado. Rode: pip install playwright && playwright install chromium.")
        return []
    from urllib.parse import urlparse

    profile_dir = os.path.join(os.path.dirname(os.path.abspath(pdf_dir)), ".browser_profile")
    os.makedirs(profile_dir, exist_ok=True)

    # Agrupa por domínio conhecido para resolver o Cloudflare uma vez por site.
    def domain_key(entry):
        doi = entry.get("doi", "").strip()
        for pfx, dom in (("10.1145", "dl.acm.org"), ("10.3390", "mdpi.com"),
                         ("10.1080", "tandfonline.com"), ("10.1002", "wiley.com"),
                         ("10.1111", "wiley.com")):
            if doi.startswith(pfx):
                return dom
        return "zzz_" + doi[:7]
    entries = sorted(entries, key=domain_key)

    downloaded: List[str] = []
    solved_domains: Set[str] = set()

    with sync_playwright() as p:
        launch_kw = dict(headless=False, accept_downloads=True,
                         user_agent=BROWSER_UA, viewport={"width": 1280, "height": 900})
        try:
            context = p.chromium.launch_persistent_context(profile_dir, channel="chrome", **launch_kw)
        except Exception:
            context = p.chromium.launch_persistent_context(profile_dir, **launch_kw)
        page = context.pages[0] if context.pages else context.new_page()

        for entry in entries:
            doi = entry.get("doi", "").strip()
            if not doi:
                continue
            pdf_path = os.path.join(pdf_dir, sanitize_filename(doi) + ".pdf")
            if os.path.exists(pdf_path):
                downloaded.append(doi)
                continue

            try:
                page.goto("https://doi.org/" + doi, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            domain = urlparse(page.url).netloc

            if _looks_blocked(page) and domain not in solved_domains:
                print(f"\n🔒 Desafio (Cloudflare) em {domain}  —  artigo {doi}")
                print("   → Resolva o desafio NA JANELA do navegador e tecle ENTER aqui para continuar...")
                try:
                    input()
                except EOFError:
                    pass
                solved_domains.add(domain)
                try:
                    page.goto("https://doi.org/" + doi, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    pass

            if _assisted_fetch_pdf(context, page, doi, pdf_path, skip_validation):
                downloaded.append(doi)
                logs["downloaded"].append(f"{doi} -> PDF via Playwright assistido")
                print(f"  ✓ baixado: {doi}")
            else:
                logs["failed"].append(f"{doi} -> falhou no modo assistido")
                print(f"  ✗ não consegui: {doi}")

        context.close()

    return downloaded


def download_assisted(bibtex_path=None, pdf_dir=None, skip_validation=False):
    """
    Modo ASSISTIDO: para TODOS os artigos do bib ainda NÃO baixados, abre um navegador
    visível e pede ajuda manual para passar pelo Cloudflare. Pergunta no terminal se deseja
    iniciar agora; caso contrário, deixa para depois (não faz nada).

    Returns:
        bool: True se rodou (ou nada a fazer); False se o usuário adiou.
    """
    if not bibtex_path or not pdf_dir:
        print("Caminhos de BibTeX/PDF não informados para o modo assistido.")
        return False
    if not os.path.exists(bibtex_path):
        print(f"BibTeX não encontrado: {bibtex_path}")
        return False

    parser = bibtexparser.bparser.BibTexParser(common_strings=True)
    with open(bibtex_path, encoding="utf-8") as f:
        database = bibtexparser.load(f, parser=parser)

    missing = []
    for entry in database.entries:
        doi = (entry.get("doi") or "").strip()
        if not doi:
            continue
        if not os.path.exists(os.path.join(pdf_dir, sanitize_filename(doi) + ".pdf")):
            missing.append(entry)

    if not missing:
        print("✓ Todos os artigos com DOI já estão baixados. Nada a fazer no modo assistido.")
        return True

    print("\n" + "=" * 64)
    print(f"DOWNLOAD ASSISTIDO  —  {len(missing)} artigos ainda NÃO baixados")
    print("=" * 64)
    print("Vai abrir um navegador VISÍVEL. Em sites com Cloudflare, resolva o desafio")
    print("('I'm human') na janela e tecle ENTER no terminal — apenas 1x por site.")
    print("Os PDFs vão para:", pdf_dir)

    try:
        resp = input("\nIniciar o processo assistido agora? [s/N]: ").strip().lower()
    except EOFError:
        resp = ""

    if resp not in ("s", "sim", "y", "yes"):
        print("\nOk — deixado para depois. Quando quiser, rode: python aneta.py --download_pdf_assisted\n")
        return False

    logs = {"downloaded": [], "failed": [], "markdown_saved": []}
    # Usa o Chrome real via CDP (passa o Cloudflare sozinho) + HITL: quando o automático
    # falha, pausa e captura o download que você fizer manualmente na janela.
    got = batch_download_cdp(missing, pdf_dir, logs, skip_validation=skip_validation, assisted=True)
    print("\n" + "=" * 64)
    print(f"✓ Modo assistido concluído: {len(got)} baixados / {len(missing) - len(got)} ainda faltando.")
    print("=" * 64 + "\n")
    return True


def _find_chrome():
    """Localiza o binário do Google Chrome instalado (macOS/Linux)."""
    import shutil
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _hitl_manual_download(context, page, doi, pdf_path, skip_validation, wait_seconds=180) -> bool:
    """
    Human-in-the-loop: o Chrome real já está aberto no artigo. Você pode NAVEGAR livremente
    (mudar de página, abrir outras abas, ir ao site do editor) e clicar em 'Download PDF' /
    'View PDF'. Capturo o PDF de QUALQUER aba, por download (attachment) OU por resposta
    inline (application/pdf). Tecle ENTER no terminal para pular este artigo.
    """
    import select
    print(f"  🙋 Ajuda manual: {doi}")
    print(f"     Janela do Chrome: {(page.url or '')[:72]}")
    print(f"     → navegue/clique para baixar o PDF (qualquer aba serve). Capturo sozinho.")
    print(f"     (ENTER no terminal = pular este | aguardo até {wait_seconds}s)")

    captured = {}

    def on_download(dl):
        if captured.get("ok"):
            return
        try:
            dl.save_as(pdf_path)
            if _validate_saved_pdf(pdf_path, skip_validation):
                captured["ok"] = True
        except Exception:
            pass

    def on_response(resp):
        if captured.get("ok"):
            return
        try:
            if "application/pdf" in (resp.headers.get("content-type") or "").lower():
                body = resp.body()
                if body[:5] == b"%PDF-":
                    with open(pdf_path, "wb") as f:
                        f.write(body)
                    if _validate_saved_pdf(pdf_path, skip_validation):
                        captured["ok"] = True
        except Exception:
            pass

    def attach(pg):
        try:
            pg.on("download", on_download)
            pg.on("response", on_response)
        except Exception:
            pass

    # Escuta TODAS as abas atuais e as que você abrir durante a navegação.
    for pg in context.pages:
        attach(pg)
    context.on("page", attach)

    skipped = False
    try:
        for _ in range(wait_seconds * 2):
            if captured.get("ok"):
                break
            try:
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.readline()
                    skipped = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
    finally:
        try:
            context.remove_listener("page", attach)
        except Exception:
            pass
        for pg in context.pages:
            try:
                pg.remove_listener("download", on_download)
                pg.remove_listener("response", on_response)
            except Exception:
                pass

    if captured.get("ok"):
        print("     ✓ PDF capturado.")
        return True
    print("     (pulado.)" if skipped else "     (nada capturado — pulando.)")
    return False


def batch_download_cdp(entries, pdf_dir, logs, skip_validation=False, port=0, assisted=False):
    """
    Baixa via CDP conectado a um Chrome REAL **headful**.

    Um Chrome genuíno (lançado normalmente, não pelo Playwright) passa o desafio do
    Cloudflare AUTOMATICAMENTE, sem interação humana — então resolve os publishers
    Cloudflare (ACM/MDPI/T&F/Wiley) e também IEEE/genéricos. O Playwright apenas se
    *conecta* (connect_over_cdp), sem injetar flags de automação.

    Headless NÃO funciona aqui (o Cloudflare detecta), por isso é headful: abre uma janela
    do Chrome que fecha sozinha ao final. Requer Google Chrome instalado.

    Returns: lista de DOIs baixados.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠ Playwright não instalado. Pulando etapa CDP.")
        return []
    chrome = _find_chrome()
    if not chrome:
        print("⚠ Google Chrome não encontrado — modo CDP indisponível. Pulando etapa.")
        return []

    import subprocess
    import urllib.request
    import socket
    import tempfile
    import shutil
    # Perfil LOCAL e único por execução: evita locks/lentidão de perfil em pasta sincronizada
    # (OneDrive) e conflito com um Chrome já aberto. O cf_clearance re-resolve em ~6s mesmo.
    profile = tempfile.mkdtemp(prefix="aneta_chrome_cdp_")
    # Porta de debug LIVRE e dinâmica (evita conflito com instância anterior na 9222).
    if not port:
        _s = socket.socket()
        _s.bind(("127.0.0.1", 0))
        port = _s.getsockname()[1]
        _s.close()

    print("\n\n=================================================")
    print("TENTATIVA EM LOTE VIA CDP (Chrome real headful — passa Cloudflare)")
    print(f"  entradas: {len(entries)} | porta: {port}")
    print("  (uma janela do Chrome vai abrir e fechar automaticamente)")
    print("=================================================\n")

    proc = subprocess.Popen(
        [chrome, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    downloaded: List[str] = []
    try:
        ready = False
        for _ in range(45):
            if proc.poll() is not None:
                print("⚠ O Chrome encerrou logo após abrir (provável conflito com um Chrome já aberto).")
                print("   Feche TODAS as janelas do Google Chrome e rode novamente.")
                return []
            try:
                urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
                ready = True
                break
            except Exception:
                time.sleep(1)
        if not ready:
            print("⚠ CDP não respondeu a tempo (45s). Feche o Chrome aberto e tente novamente.")
            return []

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            for entry in entries:
                doi = entry.get("doi", "").strip()
                if not doi:
                    continue
                pdf_path = os.path.join(pdf_dir, sanitize_filename(doi) + ".pdf")
                if os.path.exists(pdf_path):
                    downloaded.append(doi)
                    continue
                page = ctx.new_page()
                try:
                    try:
                        page.goto("https://doi.org/" + doi, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        pass
                    # aguarda o Cloudflare liberar sozinho (navegador genuíno)
                    for _ in range(9):
                        if not _looks_blocked(page):
                            break
                        time.sleep(2)
                    ok = _assisted_fetch_pdf(ctx, page, doi, pdf_path, skip_validation)
                    if not ok and assisted:
                        ok = _hitl_manual_download(ctx, page, doi, pdf_path, skip_validation)
                    if ok:
                        downloaded.append(doi)
                        logs["downloaded"].append(f"{doi} -> PDF via CDP (Chrome real)")
                        print(f"  ✓ {doi}")
                    else:
                        logs["failed"].append(f"{doi} -> falhou no CDP")
                        print(f"  ✗ {doi}")
                finally:
                    page.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)

    print(f"\nCDP: {len(downloaded)} baixados de {len(entries)} processados.\n")
    return downloaded


def download_all_papers(bibtex_path=None, pdf_dir=None, doi_file_path=None, skip_validation=False,
                        max_workers=None):
    """
    Função principal que realiza:
      - Leitura do BibTeX e do arquivo de DOIs.
      - Mescla as entradas e tenta fazer download dos PDFs (ou converter o HTML para Markdown)
        usando todas as estratégias disponíveis.
      - Mantém logs de sucesso e falhas, imprimindo cada etapa no console.

    Args:
        bibtex_path: Path to BibTeX file
        pdf_dir: Directory to save PDFs
        doi_file_path: Path to DOI list file
        skip_validation: If True, skips PDF validation checks (faster but less safe)
        max_workers: nº de downloads concorrentes (I/O-bound). None/1 => sequencial
            (comportamento original); >1 => paralelo via ThreadPoolExecutor. Cada entrada
            é independente (PDF em path único; só faz append em logs/failed_entries, que é
            thread-safe sob o GIL) e pula PDFs já baixados, então a concorrência é segura.
    """
    config = load_config()
    gs_enabled = config.get('enable_search_link_file_by_google_scholars', False)
    pypaperbot_enabled = config.get('enable_PyPaperBot_download', False)
    playwright_enabled = config.get('enable_playwright_download', False)

    print(f"\nArquivo BibTeX usado para download: {bibtex_path}")
    print(f"\nPasta de destino dos PDFs: {pdf_dir}")
    
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

    # Resolver o nível de concorrência (env DOWNLOAD_MAX_CONCURRENT como fallback).
    if max_workers is None:
        try:
            max_workers = int(os.getenv("DOWNLOAD_MAX_CONCURRENT", "1"))
        except (TypeError, ValueError):
            max_workers = 1
    max_workers = max(1, int(max_workers))

    if skip_validation:
        print("⚠️  AVISO: Validação de PDF DESABILITADA - arquivos serão salvos sem verificação de integridade\n")

    if max_workers > 1:
        # Modo concorrente: downloads são I/O-bound, então threads dão ganho ~linear.
        from concurrent.futures import ThreadPoolExecutor
        total = len(arxiv_entries) + len(doi_entries)
        print(f"\nDownload CONCORRENTE: {max_workers} workers para {total} entradas "
              f"({len(arxiv_entries)} arXiv + {len(doi_entries)} DOI)...\n")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(download_arxiv_entry, entry, pdf_dir, logs, skip_validation)
                       for entry in arxiv_entries]
            futures += [executor.submit(download_doi_entry, entry, pdf_dir, logs, failed_entries, skip_validation)
                        for entry in doi_entries]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    # Uma entrada com erro inesperado não derruba o lote inteiro.
                    print(f"⚠ Erro inesperado em download concorrente: {exc}")
    else:
        # Modo sequencial (comportamento original).
        print("\nProcessando entradas do arXiv...\n")
        for entry in arxiv_entries:
            print("--------------------------------------------------")
            download_arxiv_entry(entry, pdf_dir, logs, skip_validation=skip_validation)
            print("--------------------------------------------------\n")

        print("\nProcessando entradas com DOI...\n")
        for entry in doi_entries:
            print("--------------------------------------------------")
            download_doi_entry(entry, pdf_dir, logs, failed_entries, skip_validation=skip_validation)
            print("--------------------------------------------------\n")

    # Fallback 1 (PREFERENCIAL): navegador. Prefere o Chrome REAL via CDP (headful) — passa
    # o Cloudflare sozinho e cobre IEEE/genéricos; se o Chrome não estiver instalado, cai no
    # Playwright headless (resolve IEEE/não-Cloudflare, mas não os Cloudflare).
    if failed_entries:
        if playwright_enabled:
            if _find_chrome():
                print(f"\nTentando baixar {len(failed_entries)} artigos via CDP (Chrome real, passa Cloudflare)...\n")
                failed_entries = batch_download_cdp(
                    failed_entries, pdf_dir, logs, skip_validation=skip_validation,
                )
            else:
                print(f"\nChrome não encontrado; usando Playwright headless para {len(failed_entries)} artigos...\n")
                failed_entries = batch_download_playwright(
                    failed_entries, pdf_dir, logs, skip_validation=skip_validation,
                )
        else:
            print("\nDownload via navegador desabilitado nas configurações. Pulando etapa.\n")

    # Processamento em lote dos artigos que falharam
    if failed_entries:
        if gs_enabled:
            print(f"\nTentando baixar {len(failed_entries)} artigos que falharam nos métodos principais via Google Scholar...\n")
            failed_entries = batch_download_google_scholar(
                failed_entries,
                pdf_dir,
                logs,
                skip_validation=skip_validation,
            )
        else:
            print("\nBusca via Google Scholar desabilitada nas configurações. Pulando etapa.\n")

    # Depois, tenta PyPaperBot em lote para os que ainda falharam
    if failed_entries:
        if pypaperbot_enabled:
            print(f"\nTentando baixar {len(failed_entries)} artigos restantes via PyPaperBot...\n")
            failed_entries = batch_download_pypaperbot(
                failed_entries,
                pdf_dir,
                logs,
                skip_validation=skip_validation,
            )
        else:
            print("\nDownload via PyPaperBot desabilitado nas configurações. Pulando etapa.\n")

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
        if config.get('enable_save_md_to_lost_papers', False):
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
