#!/usr/bin/env python3
"""Summarize a consolidated multi-LLM screening result for the human checkpoint.

Usage:   python summarize_decision.py <consolidated.json> [threshold=65] [margin=15]
Exit:    0 ok | 2 file/parse error.

Reports total papers, vote distribution, is_relevant_yes_percent buckets, BORDERLINE papers
(relevance within +/-margin of the threshold) and LOW-VOTE papers (fewer votes than the
panel size). Read-only.
"""
import sys
import json
from collections import Counter


def main(path: str, threshold: float, margin: float) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: could not read {path}: {e}", file=sys.stderr)
        return 2
    if not isinstance(data, list):
        print(f"ERROR: {path} must be a JSON list of consolidated papers.", file=sys.stderr)
        return 2

    n = len(data)
    votes = Counter(r.get("total_responses") for r in data)
    panel = max((v for v in votes if isinstance(v, int)), default=0)

    buckets = Counter()
    borderline, low_vote = [], []
    for r in data:
        pct = r.get("is_relevant_yes_percent")
        tr = r.get("total_responses")
        label = (r.get("article_title") or r.get("doi") or r.get("id") or "?")
        if isinstance(tr, int) and panel and tr < panel:
            low_vote.append((label, tr))
        if isinstance(pct, (int, float)):
            if pct == 0:
                buckets["0%"] += 1
            elif pct < 50:
                buckets["1-49%"] += 1
            elif pct < threshold:
                buckets[f"50-{int(threshold)-1}%"] += 1
            elif pct < 100:
                buckets[f"{int(threshold)}-99%"] += 1
            else:
                buckets["100%"] += 1
            if abs(pct - threshold) <= margin:
                borderline.append((label, pct, tr))

    print(f"Papers consolidated: {n}")
    print(f"Vote distribution (total_responses): {dict(sorted(votes.items(), key=lambda x: (x[0] is None, x[0])))}")
    print(f"is_relevant_yes_percent buckets: {dict(buckets)}")
    print(f"\nBORDERLINE (within +/-{margin:g} of {threshold:g}%): {len(borderline)}")
    for label, pct, tr in sorted(borderline, key=lambda x: abs(x[1] - threshold))[:40]:
        print(f"  - {pct:g}% ({tr} votes)  {str(label)[:90]}")
    print(f"\nLOW-VOTE (< panel size {panel}): {len(low_vote)}")
    for label, tr in low_vote[:40]:
        print(f"  - {tr} votes  {str(label)[:90]}")
    if len(borderline) > 40 or len(low_vote) > 40:
        print("\n(lists truncated to 40; see selection_decisions*.xlsx for all)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    th = float(sys.argv[2]) if len(sys.argv) > 2 else 65.0
    mg = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    sys.exit(main(sys.argv[1], th, mg))
