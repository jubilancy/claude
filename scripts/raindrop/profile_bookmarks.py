#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
profile_bookmarks.py - count a Raindrop bookmark dump by tag, domain and link shape

Step 3 of the raindrop-organize skill: look at what a collection holds before choosing
sub-collections. Takes the JSON from extract_bookmarks.py. "Link shape" is the URL path
with digit runs replaced by <id>, so /share/user/123 and /share/user/456 count together.

Usage:
    uv run scripts/raindrop/profile_bookmarks.py bookmarks.json
    uv run scripts/raindrop/profile_bookmarks.py bookmarks.json --top 40
"""

import argparse
import json
import re
import sys
from collections import Counter
from urllib.parse import urlsplit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("dump")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    items = json.load(open(a.dump, encoding="utf-8"))
    tags = Counter(t for b in items for t in (b.get("tags") or ["(untagged)"]))
    hosts = Counter(urlsplit(b["link"]).netloc.lower().removeprefix("www.") for b in items)
    shapes = Counter(re.sub(r"\d{4,}", "<id>", urlsplit(b["link"])._replace(query="", fragment="").geturl()) for b in items)
    created = Counter(b.get("created", "")[:16] for b in items)
    types = Counter(b.get("type", "link") for b in items)
    print(f"{len(items)} bookmarks")
    for name, c in (("TAGS", tags), ("TYPES", types), ("DOMAINS", hosts), ("LINK SHAPES", shapes), ("CREATED (to the minute)", created)):
        print(f"\n{name}")
        for k, v in c.most_common(a.top):
            print(f"  {v:5d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
