"""Immutable, compressed snapshots of completed database searches."""
from src.CachePaths import cache_root
from contextlib import closing
import sqlite3
import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile


def cached_search(source, provider, query, output):
    root = cache_root() / "search" / source
    root.mkdir(parents=True, exist_ok=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    parameters = [1, source, query, provider.MAX_SEARCH_RESULTS, provider.PAGE_SIZE,
                  getattr(provider, "SCOPUS_VIEW", None), os.getenv("ANETA_SEARCH_EDITION", "1")]
    if source == "spring_nature":
        parameters.append(os.getenv("SPRINGER_EXCLUDE_BIBLIOGRAPHY", "").strip().lower() in ("1", "true", "yes", "sim"))
    key = hashlib.sha256(json.dumps(parameters).encode()).hexdigest()
    snapshot = root / (key + ".zip")
    # Selection recursively reads every .bib under output. Keep unpublished pages
    # and recovery copies outside that tree, including after process interruption.
    staging = output.parent / ("." + output.name.lstrip(".") + "-search-work")
    staging.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=staging) as workspace:
        stage = Path(workspace) / source
        if snapshot.exists():
            stage.mkdir()
            try:
                with ZipFile(snapshot) as archive:
                    for name in archive.namelist():
                        if Path(name).name != name:
                            raise BadZipFile("Invalid search archive member")
                        with archive.open(name) as src, (stage / name).open("wb") as dst:
                            shutil.copyfileobj(src, dst)
            except BadZipFile as exc:
                raise ValueError(f"Cache de busca danificado: {snapshot}. Defina ANETA_SEARCH_EDITION para uma nova coleta.") from exc
        else:
            provider.main(query, workspace)
            with TemporaryDirectory(dir=root) as scratch:
                packed = Path(scratch) / "snapshot.zip"
                with ZipFile(packed, "w", ZIP_DEFLATED) as archive:
                    for item in sorted(stage.iterdir()):
                        archive.write(item, item.name)
                # Two concurrent searches may observe different upstream data. Publish
                # only the first snapshot and use that exact version in both reviews.
                try:
                    os.link(packed, snapshot)
                except FileExistsError:
                    return cached_search(source, provider, query, output)
        (stage / ".search-key").write_text(key + "\n", encoding="utf-8")
        # Serialize publication to one review even when two workers restore at once.
        with closing(sqlite3.connect(output / ".search-lock.sqlite", timeout=60)) as lock:
            lock.execute("BEGIN IMMEDIATE")
            destination = output / source
            backup = staging / (source + ".previous")
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            if backup.exists():
                shutil.rmtree(backup)
            if destination.exists():
                destination.rename(backup)
            try:
                stage.rename(destination)
            except OSError:
                if backup.exists() and not destination.exists():
                    backup.rename(destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
