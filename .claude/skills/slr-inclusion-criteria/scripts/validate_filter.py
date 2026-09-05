#!/usr/bin/env python3
"""Validate an Aneta filter_accept_results_llm*.yaml selection clause.

Usage:   python validate_filter.py config/filter_accept_results_llm.yaml
Exit:    0 valid | 1 invalid | 2 file/parse error.

Checks: a non-empty `filter` clause, balanced parentheses, a minimum-votes guard, and that
column tokens look like real consolidated columns (warn on suspicious names).
"""
import sys
import re

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Resolve the interpreter via aneta-runner first.", file=sys.stderr)
    sys.exit(2)

KNOWN_SUFFIXES = ("_yes_count", "_no_count", "_other_count", "_total_count",
                  "_yes_percent", "_no_percent", "_other_percent")
KNOWN_BARE = {"total_responses"}
SQL_WORDS = {"and", "or", "not", "null", "is", "in", "between"}


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

    clause = data.get("filter")
    issues, warns = [], []
    if not isinstance(clause, str) or not clause.strip():
        print(f"FAIL: {path} — missing/empty `filter` clause.")
        return 1

    if clause.count("(") != clause.count(")"):
        issues.append("unbalanced parentheses in the clause.")
    if not re.search(r"(total_responses|_total_count)\s*>=?\s*\d+", clause):
        warns.append("no minimum-votes guard (total_responses / _total_count) — a single "
                     "vote could decide a paper.")

    # Column-like tokens: identifiers compared to a number.
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\s*[<>=])", clause):
        low = tok.lower()
        if low in SQL_WORDS or low in KNOWN_BARE:
            continue
        if not low.endswith(KNOWN_SUFFIXES):
            warns.append(f"column '{tok}' has no known suffix "
                         f"({', '.join(KNOWN_SUFFIXES)}); verify it exists in the consolidated data.")

    if issues:
        print(f"FAIL: {len(issues)} issue(s) in {path}")
        for i in issues:
            print(f"  - {i}")
        for w in warns:
            print(f"  (warn) {w}")
        return 1

    print(f"PASS: {path} clause looks valid.")
    for w in warns:
        print(f"  (warn) {w}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
