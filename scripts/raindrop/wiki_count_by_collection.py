#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
wiki_count_by_collection.py - rank Raindrop collections by how many Wikipedia bookmarks they hold

Reads a dump from extract_bookmarks.py (use collection 0 to dump every collection, from
a search such as link:wikipedia.org). Counts bookmarks whose host is wikipedia.org or a
subdomain, grouped by collection id, most first.

Usage:
    uv run scripts/raindrop/wiki_count_by_collection.py everything.json
    uv run scripts/raindrop/wiki_count_by_collection.py everything.json --all-matches
"""

import argparse
import json
import sys
from collections import Counter
from urllib.parse import urlsplit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("dump")
    ap.add_argument("--all-matches", action="store_true", help="count every bookmark, not just wikipedia hosts")
    a = ap.parse_args()
    items = json.load(open(a.dump, encoding="utf-8"))

    def is_wiki(b):
        h = urlsplit(b["link"]).netloc.lower()
        return h == "wikipedia.org" or h.endswith(".wikipedia.org")

    c = Counter(b["collection_id"] for b in items if a.all_matches or is_wiki(b))
    print(f"{sum(c.values())} bookmarks in {len(c)} collections")
    for cid, n in c.most_common():
        print(f"  {n:5d}  collection {cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
