"""Shared immutable metadata payloads with per-review version pins.

The historical public factory name is retained for pipeline callers.
Existing Lance datasets are read lazily and imported on first access.
"""
import hashlib
import json
import os
import sqlite3
import zlib
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from src.CachePaths import cache_root, doi_key
from dotenv import load_dotenv

load_dotenv(".conf")
load_dotenv("config/.env")


@dataclass(frozen=True)
class MetadataCache:
    database: Path
    pins: Path
    legacy: Path


def create_lancedb_instance(path_db=None):
    review = Path(os.getenv("PATH_DATA", "Data")).resolve()
    shared = cache_root()
    legacy = review / (path_db or ".db")
    root = legacy if path_db is not None else shared
    root.mkdir(parents=True, exist_ok=True)
    return MetadataCache(root / "metadata.sqlite3", review / ".metadata-pins.sqlite3", legacy)


def _connect(cache):
    cache.pins.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cache.database, timeout=60)
    conn.execute("ATTACH DATABASE ? AS review", (str(cache.pins),))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS payloads (digest TEXT PRIMARY KEY, body BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS latest (
            source TEXT, doi TEXT, digest TEXT NOT NULL, PRIMARY KEY(source, doi));
        CREATE TABLE IF NOT EXISTS review.pins (
            source TEXT, doi TEXT, digest TEXT NOT NULL, PRIMARY KEY(source, doi));
    """)
    return conn


def save_bibliographic_database(type_source, doi, json_data, db, *, historical=False):
    data = json.loads(json_data) if isinstance(json_data, str) else json_data
    body = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    digest = hashlib.sha256(body).hexdigest()
    row = (type_source, doi_key(doi), digest)
    with closing(_connect(db)) as conn, conn:
        conn.execute("INSERT OR IGNORE INTO payloads VALUES (?, ?)", (digest, zlib.compress(body)))
        if historical:
            stored = conn.execute("SELECT body FROM payloads WHERE digest=?", (digest,)).fetchone()
            if zlib.decompress(stored[0]) != body:
                raise ValueError("Metadata verification failed")
        for table in ("latest", "review.pins"):
            if historical:
                conn.execute(f"INSERT OR IGNORE INTO {table} VALUES (?, ?, ?)", row)
                continue
            conn.execute(f"""INSERT INTO {table} VALUES (?, ?, ?)
                ON CONFLICT(source, doi) DO UPDATE SET digest=excluded.digest
                WHERE digest != excluded.digest""", row)


def fetch_bibliographic_database(type_source, doi, db):
    key = (type_source, doi_key(doi))
    with closing(_connect(db)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        pin = conn.execute("SELECT digest FROM review.pins WHERE source=? AND doi=?", key).fetchone()
        if pin:
            body = conn.execute("SELECT body FROM payloads WHERE digest=?", pin).fetchone()
            if body is None:
                raise ValueError("Pinned metadata missing from shared cache")
            return json.loads(zlib.decompress(body[0]))
        if not (db.legacy / "enriched_data.lance").exists():
            return _fetch_shared(conn, key)

    import lancedb
    table = lancedb.connect(db.legacy).open_table("enriched_data")
    source = type_source.replace("'", "''")
    identifier = doi.replace("'", "''")
    rows = table.search().where(f"type_source='{source}' AND doi='{identifier}'").limit(1).to_list()
    if rows:
        data = json.loads(rows[0]["json_text"])
        save_bibliographic_database(type_source, doi, data, db, historical=True)
        return fetch_bibliographic_database(type_source, doi, db)
    with closing(_connect(db)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        return _fetch_shared(conn, key)


def _fetch_shared(conn, key):
    result = conn.execute("""SELECT digest, body FROM latest JOIN payloads USING(digest)
                             WHERE source=? AND doi=?""", key).fetchone()
    if result is None:
        return {}
    conn.execute("INSERT OR IGNORE INTO review.pins VALUES (?, ?, ?)", (*key, result[0]))
    return json.loads(zlib.decompress(result[1]))


def migrate_legacy(cache, apply=False):
    """Inspect or import a local Lance table without removing historical files."""
    if not (cache.legacy / "enriched_data.lance").is_dir():
        return 0
    import lancedb
    table = lancedb.connect(cache.legacy).open_table("enriched_data")
    count = 0
    for batch in table.search().select(["type_source", "doi", "json_text"]).limit(None).to_batches():
        for row in batch.to_pylist():
            data = json.loads(row["json_text"])
            if apply:
                save_bibliographic_database(row["type_source"], row["doi"], data, cache, historical=True)

            count += 1
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Inspect or import this review's legacy Lance data")
    parser.add_argument("--import", action="store_true", dest="apply")
    args = parser.parse_args()
    print("Legacy records:", migrate_legacy(create_lancedb_instance(), args.apply))
