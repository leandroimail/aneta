import json
import re
from pathlib import Path

import pandas as pd
import rdata
import pytest

from src.BibliometryNative import generate_native_outputs


def test_native_outputs_match_inventory_and_metrics(tmp_path):
    records = []
    for i in range(8):
        records.append(
            {
                "id": f"W{i}",
                "doi": f"https://doi.org/10.1234/{i}",
                "title": f"Study {i}",
                "publication_year": 2020 + i % 2,
                "cited_by_count": 10 - i,
                "type": "article",
                "referenced_works": ["external"] + (["W0"] if i else []),
                "primary_location": {"source": {"display_name": "Journal"}},
                "authorships": [
                    {
                        "author": {"display_name": name},
                        "institutions": [
                            {"display_name": inst, "country_code": country}
                        ],
                    }
                    for name, inst, country in [
                        ("Alice", "Institute A", "BR"),
                        ("Bob", "Institute B", "US"),
                    ]
                ],
                "concepts": [
                    {"display_name": str(t), "score": 0.8}
                    for t in range(4)
                    if i % 4 != t
                ],
            }
        )
    status = generate_native_outputs(records, tmp_path)
    script = Path("src/Bibliometry/RunBibliometrix.r").read_text()
    expected = set(re.findall(r'"([\w.-]+\.(?:png|xlsx|html|pdf|rds))"', script))
    assert expected == set(status)
    assert all(
        status[f] == "generated" and (tmp_path / f).stat().st_size for f in expected
    )
    cited = pd.read_excel(tmp_path / "top20_most_locally_cited_papers.xlsx")
    assert cited.iloc[0][["DOI", "LCS", "GCS"]].tolist() == ["10.1234/0", 7, 10]
    assert len(rdata.read_rds(tmp_path / "bibliometry_data.rds")) == 8
    countries = pd.read_excel(tmp_path / "world_map_publications_top20.xlsx")
    assert countries.values.tolist() == [["brazil", 8]]
    status = generate_native_outputs([], tmp_path)
    assert not (tmp_path / "conceptual_structure_dendogram.png").exists()
    assert "five" in status["conceptual_structure_dendogram.png"]
    assert json.loads((tmp_path / "bibliometry_artifacts.json").read_text()) == status


def test_entrypoints_keep_stage_corpora_separate_without_r(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PATH", "")
    from src import Bibliometry, BibliometryAsync

    corpus = tmp_path / "OUTPUTS"
    corpus.mkdir()
    for name in ("relevant_abstract_papers", "final_papers"):
        (corpus / f"{name}.bib").write_text("@article{p,title={Paper},doi={10.1/p}}")
    stages = []

    def offline(path, stage):
        stages.append((Path(path).stem, stage))
        work = {
            "id": stage,
            "title": stage,
            "publication_year": 2024,
            "cited_by_count": len(stages),
        }
        return [], None, [work]

    monkeypatch.setattr(BibliometryAsync, "fetch_and_store_metadata", offline)
    Bibliometry.run_bibliometry(stage="both")
    for pos, stage in enumerate(["post_abstract", "final"], 1):
        output = corpus / "BIBLIOMETRY" / stage
        table = pd.read_excel(output / "top20_most_cited_papers.xlsx")
        assert table.iloc[0]["TC"] == pos
        assert table.iloc[0]["Paper"] == stage
    assert stages == [
        ("relevant_abstract_papers", "post_abstract"),
        ("final_papers", "final"),
    ]
    final_table = corpus / "BIBLIOMETRY" / "final" / "top20_most_cited_papers.xlsx"
    previous = final_table.read_bytes()
    monkeypatch.setattr(
        BibliometryAsync,
        "fetch_and_store_metadata",
        lambda *args, **kwargs: ([{}], "fetch.log", []),
    )
    with pytest.raises(RuntimeError, match="fetch.log"):
        Bibliometry.run_bibliometry(stage="final")
    assert final_table.read_bytes() == previous


def test_malformed_optional_metadata_and_literal_titles(tmp_path):
    from openpyxl import load_workbook

    record = {
        "title": "=2+2",
        "authorships": [None, {"institutions": [None]}],
        "concepts": [None],
        "keywords": [None],
    }
    generate_native_outputs([record], tmp_path)
    workbook = load_workbook(tmp_path / "most_cited_papers.xlsx")
    cell = workbook.active["B2"]
    assert (cell.value, cell.data_type) == ("=2+2", "s")
    workbook.close()
