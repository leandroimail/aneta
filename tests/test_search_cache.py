from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.SearchCache import cached_search


def test_search_snapshot_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    requests = []

    def search(query, workspace):
        folder = Path(workspace) / "example"
        folder.mkdir()
        requests.append(query)
        (folder / "example.bib").write_text(query)
        if query == "failed":
            raise RuntimeError("Interrupted after first page")

    provider = SimpleNamespace(main=search, PAGE_SIZE=1, MAX_SEARCH_RESULTS=5)
    def run(query, destination):
        cached_search("example", provider, query, tmp_path / destination)

    run("one", "review1")
    run("one", "review2")
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: run("one", "review2"), range(6)))
    assert requests == ["one"]
    assert (tmp_path / "review2/example/example.bib").read_text() == "one"
    for _ in range(2):
        with pytest.raises(RuntimeError):
            run("failed", "review1")
    assert requests.count("failed") == 2
    assert (tmp_path / "review1/example/example.bib").read_text() == "one"
    provider.MAX_SEARCH_RESULTS = 10
    run("one", "review2")
    assert requests.count("one") == 2
    monkeypatch.setenv("ANETA_SEARCH_EDITION", "2026-11")
    run("one", "review2")
    assert requests.count("one") == 3


def test_springer_filter_changes_search_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    calls = []
    def search(query, workspace):
        (Path(workspace) / "spring_nature").mkdir()
        calls.append(query)
    provider = SimpleNamespace(main=search, PAGE_SIZE=1, MAX_SEARCH_RESULTS=2)
    for value in ("false", "true", "sim"):
        monkeypatch.setenv("SPRINGER_EXCLUDE_BIBLIOGRAPHY", value)
        cached_search("spring_nature", provider, "query", tmp_path / "review")
    assert len(calls) == 2


def test_corrupt_cache_preserves_review(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    def search(query, workspace):
        folder = Path(workspace) / "example"
        folder.mkdir()
        (folder / "records.bib").write_text(query)
    provider = SimpleNamespace(main=search, PAGE_SIZE=5, MAX_SEARCH_RESULTS=10)
    cached_search("example", provider, "q", tmp_path / "review")
    next((tmp_path / "cache").rglob("*.zip")).write_bytes(b"invalid")
    with pytest.raises(ValueError, match="ANETA_SEARCH_EDITION"):
        cached_search("example", provider, "q", tmp_path / "review")
    assert (tmp_path / "review/example/records.bib").read_text() == "q"


def test_pipeline_reuses_all_six_provider_snapshots(tmp_path, monkeypatch):
    import requests
    import yaml
    from src.Search import run_search

    providers = ("arxiv", "science_direct", "scopus", "spring_nature", "web_of_science", "ieee")
    config = tmp_path / "config"
    config.mkdir()
    (config / "search_config.yaml").write_text(yaml.safe_dump({
        "search_string": '"bibliometry"', **dict.fromkeys(providers, True),
    }))
    response = SimpleNamespace(status_code=200, text='<feed xmlns="http://www.w3.org/2005/Atom"/>',
                               json=lambda: {"results": [], "articles": [], "records": [], "hits": [],
                                             "search-results": {"entry": []}}, raise_for_status=lambda: None)
    calls = []
    def serve(*args, **kwargs):
        calls.append(1)
        return response
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "review1"))
    monkeypatch.setattr(requests, "get", serve)
    monkeypatch.setattr(requests, "put", serve)
    run_search()
    assert len(calls) == len(providers)
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "review2"))
    run_search()
    assert len(calls) == len(providers)
    assert all((tmp_path / "review2/.bibs" / name / ".search-key").is_file() for name in providers)
