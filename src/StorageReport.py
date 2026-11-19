"""Report allocated and duplicate bytes across review folders, including hidden files."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def measure(roots):
    allocated = Counter()
    inodes = set()
    by_size = defaultdict(list)
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"Missing review folder: {root}")
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            inode = stat.st_dev, stat.st_ino
            if inode in inodes:
                continue
            inodes.add(inode)
            category = str(root / path.relative_to(root).parts[0])
            allocated[category] += stat.st_blocks * 512
            by_size[stat.st_size].append(path)
    repeated = 0
    for size, paths in by_size.items():
        if len(paths) < 2 or not size:
            continue
        digests = set()
        for path in paths:
            with path.open("rb") as stream:
                digests.add(hashlib.file_digest(stream, "sha256").digest())
        repeated += size * (len(paths) - len(digests))
    return {"allocated_bytes_by_directory": allocated, "duplicate_logical_bytes": repeated}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", type=Path, nargs="+")
    print(json.dumps(measure(parser.parse_args().roots), indent=2))
