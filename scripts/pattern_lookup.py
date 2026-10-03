#!/usr/bin/env python3
"""
pattern_lookup.py — Query extracted patterns for task creation context.

Usage:
  python3 scripts/pattern_lookup.py --query loop_health
  python3 scripts/pattern_lookup.py --query apify --limit 3
  python3 scripts/pattern_lookup.py --list
"""

import argparse
import json
import sys
from pathlib import Path


def load_patterns(path: str = "/tmp/patterns.json") -> dict:
    p = Path(path)
    if not p.exists():
        print(f"Error: patterns file not found: {path}", file=sys.stderr)
        print("Run pattern_extractor.py first.", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lookup(query: str, limit: int = 5, patterns_path: str = "/tmp/patterns.json") -> list[dict]:
    data = load_patterns(patterns_path)
    patterns = data.get("patterns", [])
    query_lower = query.lower()

    matches = []
    for pat in patterns:
        score = 0
        name = pat.get("name", "").lower()
        if query_lower in name:
            score += 10
        desc = pat.get("description", "").lower()
        if query_lower in desc:
            score += 5
        if score > 0:
            matches.append((score, pat))

    matches.sort(key=lambda x: -x[0])
    return [m[1] for m in matches[:limit]]


def main():
    parser = argparse.ArgumentParser(description="Lookup patterns from extracted kanban data")
    parser.add_argument("--query", type=str, help="Search query (matches pattern name)")
    parser.add_argument("--limit", type=int, default=5, help="Max results")
    parser.add_argument("--list", action="store_true", help="List all patterns")
    parser.add_argument("--input", type=str, default="/tmp/patterns.json", help="Patterns JSON path")
    args = parser.parse_args()

    if args.list:
        data = load_patterns(args.input)
        print(f"Total patterns: {len(data.get('patterns', []))}")
        for pat in data["patterns"][:30]:
            print(f"  {pat['count']}x | [{pat['type']}] {pat['name'][:50]}")
        return

    if not args.query:
        print("Error: --query required (or --list)", file=sys.stderr)
        sys.exit(1)

    results = lookup(args.query, args.limit, args.input)
    if not results:
        print(f"No patterns found for: {args.query}")
        print("Run: python3 scripts/pattern_extractor.py --scan-done")
        sys.exit(0)

    for pat in results:
        print(f"\n=== Pattern: {pat['name'][:60]} ===")
        print(f"Type: {pat['type']}")
        print(f"Count: {pat['count']} occurrences")
        print(f"Category: {pat['category']}")
        print(f"Description: {pat['description']}")
        print(f"Evidence: {pat.get('evidence', '')}")


if __name__ == "__main__":
    main()
