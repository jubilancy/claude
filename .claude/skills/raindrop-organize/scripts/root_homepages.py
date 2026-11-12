#!/usr/bin/env python3
"""Find bare front-page bookmarks whose site has another link in the same collection.

Input: one or more JSON files holding Raindrop `find_bookmarks` output
({"bookmarks": [...]}), either raw or wrapped as [{"type":"text","text":"{...}"}]
(the format of saved tool-result files). Pass `-` to read one file from stdin.

A bookmark is a root front page when its URL has no path (or just "/"), no query
and no fragment. A site "has another link" when a different bookmark in the same
collection has the same host (case-insensitive, leading "www." ignored).

Output (stdout): JSON {collection_id: {"move_ids": [...], "roots": [...]}}.
With --target ID, prints ready-to-use update_bookmarks operations instead.

Run with: uv run python -I root_homepages.py FILE [FILE ...] [--target ID]
"""
import argparse
import json
import sys
from collections import defaultdict
from urllib.parse import urlsplit


def load(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    data = json.loads(raw)
    if isinstance(data, list):  # saved tool-result wrapper
        data = json.loads("".join(p.get("text", "") for p in data))
    return data.get("bookmarks", [])


def host(url):
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def is_root(url):
    u = urlsplit(url)
    return bool(u.hostname) and u.path in ("", "/") and not u.query and not u.fragment


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--target", type=int, help="emit update_bookmarks operations moving roots to this collection id")
    ap.add_argument("--min-others", type=int, default=1, help="other links required from the same host (default 1)")
    args = ap.parse_args()

    seen, items = set(), []
    for f in args.files:
        for b in load(f):
            if b["bookmark_id"] not in seen:
                seen.add(b["bookmark_id"])
                items.append(b)

    by_coll = defaultdict(list)
    for b in items:
        by_coll[b["collection_id"]].append(b)

    result = {}
    for cid, bms in by_coll.items():
        count = defaultdict(int)
        for b in bms:
            count[host(b["link"])] += 1
        roots = [
            {"bookmark_id": b["bookmark_id"], "link": b["link"], "others": count[host(b["link"])] - 1}
            for b in bms
            if is_root(b["link"]) and count[host(b["link"])] - 1 >= args.min_others
        ]
        if roots:
            result[cid] = {"move_ids": [r["bookmark_id"] for r in roots], "roots": roots}

    if args.target:
        ids = [i for v in result.values() for i in v["move_ids"]]
        ops = [{"bookmark_ids": ids[i:i + 150], "collection_id": args.target} for i in range(0, len(ids), 150)]
        print(json.dumps(ops))  # one update_bookmarks call per element (150-id limit)
    else:
        print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
