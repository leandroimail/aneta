import sqlite3
from concurrent.futures import ThreadPoolExecutor

import lancedb

from src.Database import migrate_legacy, create_lancedb_instance, fetch_bibliographic_database, save_bibliographic_database


def test_review_pins_and_concurrent_reuse(tmp_path, monkeypatch):
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "shared"))
    def review(name):
        monkeypatch.setenv("PATH_DATA", str(tmp_path / name))
        return create_lancedb_instance()
    first = review("first")
    second = review("second")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: save_bibliographic_database("oa", "ABC", {"v": 1}, first), range(12)))
    assert fetch_bibliographic_database("oa", "https://doi.org/abc", second) == {"v": 1}
    save_bibliographic_database("oa", "abc", {"v": 2}, second)
    assert fetch_bibliographic_database("oa", "ABC", first) == {"v": 1}
    assert fetch_bibliographic_database("oa", "abc", review("third")) == {"v": 2}
    with sqlite3.connect(first.database) as conn:
        assert conn.execute("SELECT count(*) FROM payloads").fetchone() == (2,)


def test_legacy_import(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path))
    cache = create_lancedb_instance("old")
    legacy = lancedb.connect(cache.legacy)
    legacy.create_table("enriched_data", data=[dict(type_source="oa", doi="a'b", json_text='{"a":2}')])
    assert fetch_bibliographic_database("oa", "a'b", cache) == {"a": 2}
    assert fetch_bibliographic_database("oa", "a'b", cache) == {"a": 2}
    assert migrate_legacy(cache) == 1
    assert migrate_legacy(cache, apply=True) == 1


def test_import_preserves_newer_pins_and_latest(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "old-review"))
    monkeypatch.setenv("ANETA_CACHE_DIR", str(tmp_path / "cache"))
    old = create_lancedb_instance()
    old.legacy.mkdir(parents=True)
    lancedb.connect(old.legacy).create_table(
        "enriched_data", data=[dict(type_source="oa", doi="abc", json_text='{"v":1}')]
    )
    save_bibliographic_database("oa", "abc", {"v": 2}, old)
    assert migrate_legacy(old, apply=True) == 1
    assert fetch_bibliographic_database("oa", "abc", old) == {"v": 2}
    monkeypatch.setenv("PATH_DATA", str(tmp_path / "another-review"))
    assert fetch_bibliographic_database("oa", "abc", create_lancedb_instance()) == {"v": 2}
