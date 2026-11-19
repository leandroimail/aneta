from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.PdfCache import PdfCache, inspect_folder


def pdf(marker):
    return b"%PDF-1.5\n" + marker * 1100 + b"\n%%EOF"


def test_two_reviews_with_overlap(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    cache = PdfCache()
    a, b = tmp_path / "first", tmp_path / "second"
    a.mkdir()
    b.mkdir()
    for identifier in ("a", "b"):
        (a / identifier).write_bytes(pdf(identifier.encode()))
        cache.store(identifier, a / identifier, pin=True)
    missing = [key for key in ("b", "c") if not cache.restore(key, b / key)]
    assert missing == ["c"]
    assert (b / "b").read_bytes() == (a / "b").read_bytes()
    (b / "b").write_bytes(pdf(b"x"))
    cache.store("b", b / "b", pin=True)
    (a / "b").unlink()
    assert cache.restore("B", a / "b")
    assert (a / "b").read_bytes() == pdf(b"b")


def test_parallel_import_and_offline_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    cache = PdfCache()
    p = tmp_path / "10.123%2FABC.pdf"
    p.write_bytes(pdf(b"x"))
    assert inspect_folder(tmp_path)["imported"] == 0
    assert not cache.root.exists()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert [x["imported"] for x in pool.map(lambda _: inspect_folder(tmp_path, True), range(8))] == [1] * 8
    blobs = list((cache.root / "objects").iterdir())
    assert len(blobs) == 1
    assert cache.restore("https://doi.org/10.123/abc", tmp_path / "verified")
    blobs[0].write_bytes(pdf(b"y"))
    assert not cache.restore("10.123/abc", tmp_path / "rejected")


def test_import_pins_historical_pdf_without_changing_latest(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    path = old / "10.1%2Fa.pdf"
    path.write_bytes(pdf(b"a"))
    current = new / path.name
    current.write_bytes(pdf(b"b"))
    cache = PdfCache()
    cache.store("10.1/a", current)
    inspect_folder(old, apply=True)
    path.unlink()
    assert cache.restore("10.1/a", path)
    assert path.read_bytes() == pdf(b"a")
    fresh = tmp_path / "fresh"
    assert cache.restore("10.1/a", fresh)
    assert fresh.read_bytes() == pdf(b"b")


def test_acquisition_reuses_overlap_before_any_network(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "data"))
    from src import DonwloadPapers as downloader

    monkeypatch.setattr(downloader, "load_config", lambda: {})
    downloaded = []
    def fetch(url, file_path, **kwargs):
        assert url.startswith("https://example.org/")
        downloaded.append(url)
        Path(file_path).write_bytes(pdf(url[-1].encode()))
        return True
    monkeypatch.setattr(downloader, "download_pdf_url", fetch)

    for stage, keys in (("first", ["a", "b"]), ("second", ["b", "c"])):
        bib = tmp_path / (stage + ".bib")
        bib.write_text("\n".join(
            f"@article{{{key}, doi={{10.1/{key}}}, url_pdf={{https://example.org/{key}}}}}"
            for key in keys
        ))
        downloader.download_all_papers(str(bib), str(tmp_path / stage))
    assert downloaded == [f"https://example.org/{key}" for key in "abc"]


def test_batch_preserves_newer_global_version(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "data"))
    from src import DonwloadPapers as downloader

    monkeypatch.setattr(downloader, "load_config", lambda: {})
    folder = tmp_path / "old"
    folder.mkdir()
    path = folder / (downloader.sanitize_filename("10.1/test") + ".pdf")
    path.write_bytes(pdf(b"a"))
    newest = tmp_path / "newest.pdf"
    newest.write_bytes(pdf(b"b"))
    cache = PdfCache()
    cache.store("10.1/test", newest)
    bib = tmp_path / "old.bib"
    bib.write_text("@article{key, doi={10.1/test}}")
    downloader.download_all_papers(str(bib), str(folder))
    restored = tmp_path / "fresh" / "article.pdf"
    assert cache.restore("10.1/test", restored)
    assert restored.read_bytes() == newest.read_bytes()
    path.unlink()
    assert cache.restore("10.1/test", path)
    assert path.read_bytes() == pdf(b"a")
