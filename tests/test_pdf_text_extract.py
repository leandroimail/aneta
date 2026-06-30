"""Testes da extração de texto de PDF para a triagem por full-text (offline)."""
import os

import pytest

from src.GenerativeAI.PDFTextExtract import (
    sanitize_doi,
    _strip_back_matter,
    extract_text,
    has_text,
)


def test_sanitize_doi():
    assert sanitize_doi("10.1007/s40747-025-1") == "10.1007%2Fs40747-025-1"
    assert sanitize_doi("https://doi.org/10.1/x") == "10.1%2Fx"


def test_strip_back_matter_remove_referencias_no_fim():
    body = "Introduction\n" + ("conteúdo relevante do corpo. " * 50)
    text = body + "\n## References\n[1] Autor et al. 2024.\n[2] Outro 2023."
    out = _strip_back_matter(text)
    assert "References" not in out
    assert "[1] Autor" not in out
    assert "conteúdo relevante" in out


def test_strip_back_matter_nao_corta_mencao_precoce():
    # "references" no início (primeira metade) NÃO deve cortar.
    text = "References are discussed here.\n" + ("corpo " * 200)
    out = _strip_back_matter(text)
    assert out == text  # nada removido


def test_strip_back_matter_remove_appendix():
    body = ("corpo do artigo. " * 80)
    text = body + "\nAppendix\nTabela extra A1."
    out = _strip_back_matter(text)
    assert "Appendix" not in out


def test_extract_text_reusa_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    doi = "10.1/abc"
    md_dir = tmp_path / "PDFs" / "markdowns"
    md_dir.mkdir(parents=True)
    (md_dir / (sanitize_doi(doi) + ".md")).write_text(
        "# Título\nCorpo do paper via docling.\n## References\n[1] x", encoding="utf-8")
    out = extract_text(doi)
    assert "Corpo do paper via docling" in out
    assert "References" not in out  # back matter removido
    assert has_text(doi) is True


def test_extract_text_pymupdf(tmp_path, monkeypatch):
    fitz = pytest.importorskip("fitz")  # PyMuPDF
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    doi = "10.2/xyz"
    pdf_dir = tmp_path / "PDFs"
    pdf_dir.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Texto extraido do PDF de teste.")
    doc.save(str(pdf_dir / (sanitize_doi(doi) + ".pdf")))
    doc.close()
    out = extract_text(doi)
    assert out and "Texto extraido do PDF" in out


def test_extract_text_sem_arquivo(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    assert extract_text("10.9/inexistente") is None
    assert has_text("10.9/inexistente") is False


def test_run_with_timeout_retorna_rapido():
    """O timeout deve desbloquear de fato: não pode esperar a thread lenta terminar."""
    import time
    from src.GenerativeAI.PDFTextExtract import _run_with_timeout
    t0 = time.time()
    out = _run_with_timeout(lambda: (time.sleep(3), "done")[1], timeout=0.3)
    elapsed = time.time() - t0
    assert out is None          # estourou o timeout
    assert elapsed < 1.5        # retornou logo (NÃO esperou os 3s da thread)
    # caminho feliz: conclui antes do timeout e devolve o valor
    assert _run_with_timeout(lambda: "ok", timeout=2.0) == "ok"
