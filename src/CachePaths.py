"""Storage paths and identifiers shared by the pipeline."""
import os
from pathlib import Path
from urllib.parse import quote


def cache_root():
    return Path(os.getenv("ANETA_CACHE_DIR") or "~/.cache/aneta").expanduser()


def doi_key(doi):
    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def doi_filename(doi):
    # Historical filenames preserve case, including percent-encoded characters.
    return quote(doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip(), safe="")
