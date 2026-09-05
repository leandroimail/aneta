#!/usr/bin/env python3
"""Validate an Aneta research_questions.yaml protocol file.

Usage:   python validate_protocol.py config/research_questions.yaml
Output:  human-readable PASS/FAIL with specific issues.
Exit:    0 = valid | 1 = invalid | 2 = file/parse error.
"""
import sys
import re

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Resolve the interpreter via aneta-runner first.", file=sys.stderr)
    sys.exit(2)


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
        print(f"ERROR: {path} top level must be a mapping (got {type(data).__name__}).", file=sys.stderr)
        return 2

    issues = []

    prq = data.get("principal_research_question")
    if not isinstance(prq, str) or not prq.strip():
        issues.append("principal_research_question: missing or empty (must be a single question).")

    # dict sections with their required key prefix; accepted/rejection are mandatory.
    sections = {
        "additional_research_questions": ("arq", False),
        "supporting_questions": ("sq", False),
        "accepted_criteria": ("ac", True),
        "rejection_criteria": ("rc", True),
    }
    for name, (prefix, required) in sections.items():
        section = data.get(name)
        if section is None:
            if required:
                issues.append(f"{name}: missing (at least one {prefix}1 is required).")
            continue
        if not isinstance(section, dict):
            issues.append(f"{name}: must be a mapping of {prefix}<n> -> text.")
            continue
        if required and not section:
            issues.append(f"{name}: empty (at least one {prefix}1 is required).")
        for key, val in section.items():
            if not re.fullmatch(rf"{prefix}\d+", str(key)):
                issues.append(f"{name}.{key}: key must match '{prefix}<number>' (e.g. {prefix}1).")
            if not isinstance(val, str) or not val.strip():
                issues.append(f"{name}.{key}: empty text.")
            elif len(val.strip()) < 15:
                issues.append(f"{name}.{key}: very short — make it operational/decidable: {val.strip()!r}")

    if issues:
        print(f"FAIL: {len(issues)} issue(s) in {path}")
        for i in issues:
            print(f"  - {i}")
        return 1

    print(f"PASS: {path} is a valid Aneta protocol.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
