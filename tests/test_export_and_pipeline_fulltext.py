"""Testes offline: etapas de full-text no pipeline-report + exportação dos resultados finais."""
import os
import json


def _w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_pipeline_pulls_fulltext(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    from src.PipelineReport import (
        _paths, _pull_classificacao_fulltext, _pull_consolidacao_fulltext, _pull_filtro_final,
    )
    out = tmp_path / "OUTPUTS"
    # respostas brutas full-text (2 LLMs)
    _w(str(out / "raw_responses_fulltext" / "llmA" / "response_1_llmA_m_raw.txt"), "{}")
    _w(str(out / "raw_responses_fulltext" / "llmB" / "response_1_llmB_m_raw.txt"), "{}")
    # consolidado + finais
    _w(str(out / "processed_responses" / "combined_responses_fulltext_consolidated.json"),
       json.dumps([{"total_responses": 2}, {"total_responses": 2}]))
    _w(str(out / "processed_responses" / "final_papers.json"), json.dumps([{"doi": "10.1/a"}]))
    _w(str(out / "processed_responses" / "final_excluded_papers.json"), json.dumps([{"doi": "10.2/b"}]))

    P = _paths()
    cls = _pull_classificacao_fulltext(P)
    assert cls["llms"] == 2 and cls["respostas_por_llm"] == {"llmA": 1, "llmB": 1}
    cons = _pull_consolidacao_fulltext(P)
    assert cons["artigos_consolidados"] == 2
    flt = _pull_filtro_final(P)
    assert flt["selecionados"] == 1 and flt["rejeitados"] == 1 and flt["entrada"] == 2


def test_export_final_results(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    from src.ExportFinalResults import export_final_results, _selected_dois, _sanitize

    out = tmp_path / "OUTPUTS"
    _w(str(out / "processed_responses" / "final_papers.json"),
       json.dumps([{"doi": "10.1/a", "title": "A"}, {"doi": "10.2/b", "title": "B"}]))
    _w(str(out / "final_papers.bib"), '@article{a, doi={10.1/a}}\n@article{b, doi={10.2/b}}\n')
    _w(str(out / "processed_responses" / "final_papers_report.md"), "# rel")
    # 1 PDF presente (10.1/a), o outro ausente (10.2/b)
    pdfs = tmp_path / "PDFs"
    pdfs.mkdir()
    (pdfs / (_sanitize("10.1/a") + ".pdf")).write_bytes(b"%PDF-1.4 teste")

    dest = export_final_results()
    assert dest and os.path.isdir(dest)
    # PDF presente copiado; ausente não
    assert os.path.exists(os.path.join(dest, "pdfs", _sanitize("10.1/a") + ".pdf"))
    assert not os.path.exists(os.path.join(dest, "pdfs", _sanitize("10.2/b") + ".pdf"))
    # artefatos finais + LEIA-ME
    assert os.path.exists(os.path.join(dest, "final_papers.bib"))
    assert os.path.exists(os.path.join(dest, "final_papers_report.md"))
    assert os.path.exists(os.path.join(dest, "LEIA-ME.md"))


def test_selected_dois_fallback_to_bib(tmp_path):
    from src.ExportFinalResults import _selected_dois
    bib = tmp_path / "f.bib"
    bib.write_text('@article{a, doi={10.1/x}}\n@article{b, doi={10.1/X}}\n', encoding="utf-8")
    # json ausente → usa o bib; dedup case-insensitive (10.1/x == 10.1/X)
    dois = _selected_dois(str(tmp_path / "missing.json"), str(bib))
    assert len(dois) == 1 and dois[0].lower() == "10.1/x"
