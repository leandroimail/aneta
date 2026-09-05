#!/usr/bin/env python3
"""Validate an Aneta search_config.yaml (structure + search_string balance).

Usage:   python validate_search.py config/search_config.yaml
Exit:    0 valid | 1 invalid | 2 file/parse error.
"""
import sys

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Resolve the interpreter via aneta-runner first.", file=sys.stderr)
    sys.exit(2)

KNOWN_BASES = ["arxiv", "science_direct", "spring_nature", "web_of_science", "ieee", "scopus", "acm"]


def _balanced(s: str):
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    if depth != 0:
        return False
    # quotes: even count of each kind
    return s.count('"') % 2 == 0 and s.count("'") % 2 == 0


def main(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    except yaml.YAMLError as e:
        print(f"ERROR: invalid YAML in {path}: {e}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print(f"ERROR: {path} top level must be a mapping.", file=sys.stderr)
        return 2

    issues = []
    enabled = [b for b in KNOWN_BASES if data.get(b) is True]
    if not enabled:
        issues.append("no database enabled (set at least one of "
                      f"{', '.join(b for b in KNOWN_BASES if b != 'acm')} to true).")
    if data.get("acm") is True:
        issues.append("acm is enabled but not API-supported (search will skip it).")

    ss = data.get("search_string")
    if not isinstance(ss, str) or not ss.strip():
        issues.append("search_string: missing or empty.")
    elif not _balanced(ss):
        issues.append("search_string: unbalanced parentheses or quotes.")

    if issues:
        print(f"FAIL: {len(issues)} issue(s) in {path}")
        for i in issues:
            print(f"  - {i}")
        return 1

    print(f"PASS: {path} valid. Enabled bases: {', '.join(enabled)}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
