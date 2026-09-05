"""
Extração de texto de PDFs para a triagem por TEXTO COMPLETO (Aneta).

Estratégia (rápida e barata):
  1) Reaproveita o markdown já gerado pelo docling (.data/PDFs/markdowns/<doi>.md), que
     traz tabelas como markdown — sem reprocessar.
  2) Se não houver markdown, extrai o texto via PyMuPDF (fitz) — instantâneo e leve.

Antes de devolver, remove (por heurística simples) o "back matter" — referências/
bibliografia e apêndice — que não ajuda na decisão de inclusão e gasta tokens à toa.

A chave é o DOI (sanitizado igual ao resto do pipeline: urllib.parse.quote(doi, safe='')).
"""
import os
import re
import urllib.parse
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))


def sanitize_doi(doi: str) -> str:
    """Igual a DonwloadPapers.sanitize_filename — chave de arquivo a partir do DOI."""
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return urllib.parse.quote(doi, safe="")


def _default_dirs():
    base = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    pdf_dir = os.path.join(base, os.getenv("FOLDER_SAVE_PDF", "PDFs"))
    md_dir = os.path.join(base, os.getenv("MARKDOWN_OUTPUT_FOLDER", "PDFs/markdowns"))
    return pdf_dir, md_dir


# Cabeçalhos que marcam o início do back matter (referências/bibliografia/apêndice).
_BACKMATTER_RE = re.compile(
    r"(?im)^\s*#*\s*\**\s*"
    r"(references|bibliography|refer[êe]ncias|bibliografia|works\s+cited|literature\s+cited|"
    r"appendix|ap[êe]ndice|supplementary\s+material)\b\s*\**\s*$"
)


def _strip_back_matter(text: str) -> str:
    """
    Remove referências/bibliografia/apêndice cortando a partir do ÚLTIMO cabeçalho desse
    tipo, desde que ele esteja na parte final do documento (> 50%), para não cortar uma
    menção precoce a "references". Split simples e conservador.
    """
    if not text:
        return text
    matches = list(_BACKMATTER_RE.finditer(text))
    if not matches:
        return text
    cutoff = len(text) // 2
    # Pega o primeiro cabeçalho de back matter que esteja na metade final do texto.
    for m in matches:
        if m.start() >= cutoff:
            return text[:m.start()].rstrip()
    return text


def _run_with_timeout(fn, timeout: float = 20.0):
    """Roda fn() numa thread DAEMON com timeout REAL — protege contra arquivos só-na-nuvem
    (OneDrive) cuja leitura pode pendurar indefinidamente. Retorna None em timeout/erro.

    Usa thread daemon + join(timeout) (não ThreadPoolExecutor com 'with', que faria
    shutdown(wait=True) e bloquearia esperando a thread travada — anulando o timeout).
    Em timeout, a thread é abandonada (daemon → morre no fim do processo)."""
    import threading
    box = {}

    def _runner():
        try:
            box["value"] = fn()
        except Exception:
            box["value"] = None

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None  # timeout: não espera a thread (que pode estar travada na leitura)
    return box.get("value")


def _extract_pymupdf(pdf_path: str) -> Optional[str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("⚠ PyMuPDF não instalado (pip install pymupdf). Não foi possível extrair o PDF.")
        return None
    try:
        parts = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                parts.append(page.get_text("text"))
        text = "\n".join(parts).strip()
        return text or None
    except Exception as e:
        print(f"⚠ Falha ao extrair PDF via PyMuPDF ({os.path.basename(pdf_path)}): {e}")
        return None


def extract_text(doi: str, pdf_dir: Optional[str] = None, markdown_dir: Optional[str] = None,
                 strip_back_matter: bool = True) -> Optional[str]:
    """
    Retorna o texto completo de um paper (markdown do docling se existir, senão PyMuPDF),
    com referências/apêndice removidos. Retorna None se não houver PDF nem markdown.
    """
    if not doi:
        return None
    d_pdf, d_md = _default_dirs()
    pdf_dir = pdf_dir or d_pdf
    markdown_dir = markdown_dir or d_md
    key = sanitize_doi(doi)

    text = None
    md_path = os.path.join(markdown_dir, key + ".md")
    if os.path.exists(md_path):
        # Leitura com timeout: se o markdown estiver só-na-nuvem (OneDrive) e pendurar,
        # cai no PDF (que é local, baixado por nós).
        def _read_md():
            with open(md_path, encoding="utf-8", errors="ignore") as f:
                return f.read()
        content = _run_with_timeout(_read_md, timeout=20.0)
        text = (content.strip() or None) if content else None
        if text is None:
            print(f"  (markdown indisponível/timeout p/ {doi}; tentando o PDF)")
    if text is None:
        pdf_path = os.path.join(pdf_dir, key + ".pdf")
        if os.path.exists(pdf_path):
            text = _run_with_timeout(lambda: _extract_pymupdf(pdf_path), timeout=40.0)

    if text and strip_back_matter:
        text = _strip_back_matter(text)
    return text


def has_text(doi: str, pdf_dir: Optional[str] = None, markdown_dir: Optional[str] = None) -> bool:
    """True se existe markdown OU PDF para o DOI (texto disponível para triagem)."""
    d_pdf, d_md = _default_dirs()
    pdf_dir = pdf_dir or d_pdf
    markdown_dir = markdown_dir or d_md
    key = sanitize_doi(doi)
    return (os.path.exists(os.path.join(markdown_dir, key + ".md"))
            or os.path.exists(os.path.join(pdf_dir, key + ".pdf")))
