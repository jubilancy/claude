#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
extract_bookmarks.py - save Raindrop find_bookmarks results from a Claude Code session transcript as JSON

The Raindrop MCP tools return results inline, so scripts cannot read them. Claude Code
records every tool result in the session transcript (a .jsonl file). This walks every
string in it, parses the ones that look like {"bookmarks":[...]} and writes the
bookmarks for one collection to a JSON list, de-duplicated by bookmark_id.

Usage:
    uv run scripts/raindrop/extract_bookmarks.py TRANSCRIPT.jsonl 75935771 -o bookmarks.json
"""

import argparse
import json
import sys
from pathlib import Path


def walk(o, found, collection):
    if isinstance(o, str):
        if o.startswith('{"bookmarks":['):
            try:
                for b in json.loads(o)["bookmarks"]:
                    if b.get("collection_id") == collection:
                        found[b["bookmark_id"]] = b
            except (ValueError, KeyError):
                pass
    elif isinstance(o, list):
        for x in o:
            walk(x, found, collection)
    elif isinstance(o, dict):
        for x in o.values():
            walk(x, found, collection)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("transcript", type=Path)
    ap.add_argument("collection", type=int)
    ap.add_argument("-o", "--output", type=Path, default=Path("bookmarks.json"))
    a = ap.parse_args()
    found = {}
    for line in a.transcript.open(encoding="utf-8"):
        try:
            walk(json.loads(line), found, a.collection)
        except ValueError:
            continue
    a.output.write_text(json.dumps(list(found.values()), ensure_ascii=False), encoding="utf-8")
    print(f"{len(found)} bookmarks from collection {a.collection} -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
