#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
classify_by_rules.py - sort a Raindrop bookmark dump into buckets with a JSON rules file and print move batches

Each rule is a bucket with an optional Raindrop sub-collection id and any of: "tags"
(case-insensitive, any match), "domains" (host equals or ends with), "host_regex",
"url_regex", "title_regex". Rules are checked top to bottom and the first match wins, so
put specific buckets before broad ones. Bookmarks that match nothing are listed as left
over. With --ops it prints update_bookmarks operations in batches of at most 150 IDs,
the tool's limit per call. See scripts/raindrop/rules/ for examples.

Usage:
    uv run scripts/raindrop/classify_by_rules.py bookmarks.json rules/books_misc.json            # counts + leftovers
    uv run scripts/raindrop/classify_by_rules.py bookmarks.json rules/books_misc.json --ops      # move batches as JSON lines
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from urllib.parse import urlsplit


def matches(rule, b, host, tags):
    if rule.get("tags") and tags & {t.lower() for t in rule["tags"]}:
        return True
    if any(host == d or host.endswith("." + d) for d in rule.get("domains", [])):
        return True
    for key, text in (("host_regex", host), ("url_regex", b["link"]), ("title_regex", b.get("title", ""))):
        if rule.get(key) and re.search(rule[key], text, re.I):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("dump")
    ap.add_argument("rules")
    ap.add_argument("--ops", action="store_true", help="print update_bookmarks batches")
    a = ap.parse_args()
    items = json.load(open(a.dump, encoding="utf-8"))
    rules = json.load(open(a.rules, encoding="utf-8"))["rules"]
    got, left = defaultdict(list), []
    for b in items:
        host = urlsplit(b["link"]).netloc.lower().removeprefix("www.")
        tags = {t.lower() for t in b.get("tags") or []}
        for r in rules:
            if matches(r, b, host, tags):
                got[r["bucket"]].append(b["bookmark_id"])
                break
        else:
            left.append(b)
    for r in rules:
        print(f"{len(got[r['bucket']]):5d}  {r['bucket']}  (collection {r.get('collection_id', '?')})", file=sys.stderr)
    print(f"{len(left):5d}  left over", file=sys.stderr)
    for b in left[:50]:
        print(f"        {b['bookmark_id']}  {urlsplit(b['link']).netloc}  {b.get('title', '')[:50]}", file=sys.stderr)
    if a.ops:
        n = 0
        for r in rules:
            ids, cid = got[r["bucket"]], r.get("collection_id")
            for i in range(0, len(ids), 150):
                n += 1
                print(json.dumps({"batch": n, "bucket": r["bucket"],
                                  "updates": [{"bookmark_ids": ids[i:i + 150], "collection_id": cid}]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
