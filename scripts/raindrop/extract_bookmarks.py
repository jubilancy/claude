#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
extract_bookmarks.py - save Raindrop find_bookmarks results from a Claude Code session transcript as JSON

The Raindrop MCP tools return results inline, so scripts cannot read them. Claude Code
records every tool result in the session transcript (a .jsonl file). This walks every
string in it, parses the ones that look like {"bookmarks":[...]} and writes the
bookmarks to a JSON list, de-duplicated by bookmark_id. Use collection 0 for all collections.

A long session may have fetched the same collection several times, and bookmarks moved since
then would still show up. Use --last N to read only the N most recent find_bookmarks results
(for example --last 3 for the three pages you just fetched).

Usage:
    uv run scripts/raindrop/extract_bookmarks.py TRANSCRIPT.jsonl 75935771 -o bookmarks.json
    uv run scripts/raindrop/extract_bookmarks.py TRANSCRIPT.jsonl 0 -o everything.json
    uv run scripts/raindrop/extract_bookmarks.py TRANSCRIPT.jsonl 77012342 --last 3 -o bookmarks.json
"""

import argparse
import json
import sys
from pathlib import Path


def walk(o, results):
    """Collect every parsed {"bookmarks": [...]} result found in o into the dict results."""
    if isinstance(o, str):
        if o.startswith('{"bookmarks":['):
            try:
                results[o] = json.loads(o)["bookmarks"]  # keyed by raw text: the transcript can repeat a result
            except (ValueError, KeyError):
                pass
    elif isinstance(o, list):
        for x in o:
            walk(x, results)
    elif isinstance(o, dict):
        for x in o.values():
            walk(x, results)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("transcript", type=Path)
    ap.add_argument("collection", type=int, help="collection id, or 0 for all")
    ap.add_argument("-o", "--output", type=Path, default=Path("bookmarks.json"))
    ap.add_argument("--last", type=int, help="only the N most recent find_bookmarks results")
    a = ap.parse_args()
    results = {}
    for line in a.transcript.open(encoding="utf-8"):
        try:
            walk(json.loads(line), results)
        except ValueError:
            continue
    found = {}
    order = list(results.values())  # each distinct result once, oldest first
    for res in order[-a.last:] if a.last else order:
        for b in res:
            if a.collection == 0 or b.get("collection_id") == a.collection:
                found[b["bookmark_id"]] = b
    a.output.write_text(json.dumps(list(found.values()), ensure_ascii=False), encoding="utf-8")
    print(f"{len(found)} bookmarks -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
