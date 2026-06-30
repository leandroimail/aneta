"""Testes da montagem de prompt e de prompts da triagem por full-text (offline)."""
import os
import json

import pytest

from src.GenerativeAI.PDFTextExtract import sanitize_doi
from src.GenerativeAI.LLMSelectPapersByFullTextAsync import (
    _format_criteria,
    _load_template,
    _fill_prompt,
    build_fulltext_prompts,
)


def test_format_criteria_tem_blocos():
    os.environ.setdefault("PROJECT_PATH", os.getcwd())
    crit = _format_criteria()
    assert "principal_research_question" in crit["questions"]
    assert crit["rejection_criteria"]  # rc1...
    assert crit["accepted_criteria"]   # ac1...


def test_fill_prompt_preenche_texto_e_id():
    os.environ.setdefault("PROJECT_PATH", os.getcwd())
    template = _load_template()
    crit = _format_criteria()
    paper = {"doi": "10.5/zzz", "title": "Meu Título"}
    prompt = _fill_prompt(template, crit, paper, "CORPO COMPLETO DO PAPER AQUI")
    assert "CORPO COMPLETO DO PAPER AQUI" in prompt
    assert "10.5/zzz" in prompt
    assert "Meu Título" in prompt
    assert "{{full_text}}" not in prompt and "{{id}}" not in prompt


def test_build_fulltext_prompts(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    monkeypatch.setenv("PROJECT_PATH", os.getcwd())

    # 2 papers: um COM markdown (texto), outro SEM (pendente)
    doi_ok, doi_pend = "10.1/withtext", "10.2/notext"
    md_dir = tmp_path / "PDFs" / "markdowns"
    md_dir.mkdir(parents=True)
    (md_dir / (sanitize_doi(doi_ok) + ".md")).write_text(
        "Corpo completo do artigo com evidências.", encoding="utf-8")

    bib = tmp_path / "rel.bib"
    bib.write_text(
        '@article{a1,\n title={Paper Com Texto},\n doi={%s},\n abstract={abs1},\n keywords={k1}\n}\n'
        '@article{a2,\n title={Paper Sem Texto},\n doi={%s},\n abstract={abs2}\n}\n'
        % (doi_ok, doi_pend), encoding="utf-8")

    papers, pending = build_fulltext_prompts(str(bib))
    assert len(papers) == 1
    assert papers[0]["doi"] == doi_ok
    assert "Corpo completo do artigo" in papers[0]["prompt"]
    assert [p["id"] for p in pending] == [doi_pend]

    # select_bibs_fulltext.json escrito na ordem, com id=doi
    info_path = tmp_path / "OUTPUTS" / "select_bibs_fulltext.json"
    assert info_path.exists()
    info = json.loads(info_path.read_text(encoding="utf-8"))
    assert len(info) == 1 and info[0]["id"] == doi_ok and info[0]["doi"] == doi_ok
