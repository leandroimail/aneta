"""Shared content-addressed PDF storage. Run as a module to inspect/import a PDF folder."""
from src.CachePaths import cache_root, doi_key
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


def clone_or_copy(source, target):
    """Make an independent file, sharing physical blocks on copy-on-write filesystems."""
    source, target = Path(source).absolute(), Path(target).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        staged = Path(temp) / "document"
        if sys.platform in ("darwin", "linux"):
            try:
                option = "-c" if sys.platform == "darwin" else "--reflink=auto"
                subprocess.run(["/bin/cp", option, source, staged], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.CalledProcessError):
                shutil.copyfile(source, staged)
        else:
            shutil.copyfile(source, staged)
        os.replace(staged, target)


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _valid(path):
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-" or path.stat().st_size < 1024:
            return False
        stream.seek(-1024, os.SEEK_END)
        return b"%%EOF" in stream.read()


def _record(ref, digest, *, only_if_missing=False):
    if ref.exists() and ref.read_text() == digest:
        return
    ref.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=ref.parent, mode="w", delete=False) as stream:
        stream.write(digest)
    try:
        if only_if_missing:
            try:
                os.link(stream.name, ref)
            except FileExistsError:
                pass
        else:
            os.replace(stream.name, ref)
    finally:
        Path(stream.name).unlink(missing_ok=True)


class PdfCache:
    def __init__(self, root=None):
        self.root = Path(root or cache_root()).expanduser() / "pdf"

    def reference(self, identifier):
        key = doi_key(identifier)
        return self.root / "references" / hashlib.sha256(key.encode()).hexdigest()

    def store(self, identifier, source, *, pin=False, historical=False):
        source = Path(source)
        if not source.is_file() or not _valid(source):
            return None
        digest = _digest(source)
        blob = self.root / "objects" / digest
        if not blob.exists() or _digest(blob) != digest:
            blob.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=blob.parent) as temp:
                staged = Path(temp) / "object"
                clone_or_copy(source, staged)
                if _digest(staged) != digest or not _valid(staged):
                    raise OSError(f"PDF changed during import: {source}")
                os.replace(staged, blob)
        ref = self.reference(identifier)
        pinned = source.parent / ".aneta-pdf-versions" / ref.name
        if not pin or not pinned.exists() or pinned.read_text() != digest or not ref.exists():
            _record(ref, digest, only_if_missing=historical)
        if pin:
            _record(pinned, digest)
        return digest

    def restore(self, identifier, target):
        ref = self.reference(identifier)
        target = Path(target)
        pin = target.parent / ".aneta-pdf-versions" / ref.name
        if pin.is_file():
            ref = pin
        if target.exists() or not ref.is_file():
            return False
        digest = ref.read_text()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return False
        blob = self.root / "objects" / digest
        if not blob.is_file() or _digest(blob) != digest:
            return False
        clone_or_copy(blob, target)
        _record(pin, digest)
        return True


def inspect_folder(folder, apply=False):
    cache = PdfCache()
    hashes, inodes = set(), set()
    report = dict(files=0, allocated_bytes=0, unique_content_bytes=0, imported=0, invalid=0)
    for path in sorted(Path(folder).glob("*.pdf")):
        stat = path.stat()
        inode = (stat.st_dev, stat.st_ino)
        if inode not in inodes:
            report["allocated_bytes"] += stat.st_blocks * 512
            inodes.add(inode)
        digest = _digest(path)
        if digest not in hashes:
            report["unique_content_bytes"] += stat.st_size
            hashes.add(digest)
        report["files"] += 1
        if not _valid(path):
            report["invalid"] += 1
        elif apply and cache.store(unquote(path.stem), path, pin=True, historical=True):
            report["imported"] += 1
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--import", dest="apply", action="store_true")
    args = parser.parse_args()
    if not args.folder.is_dir():
        parser.error("PDF directory does not exist")
    print(json.dumps(inspect_folder(args.folder, args.apply), indent=2))
