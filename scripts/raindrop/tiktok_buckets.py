#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
tiktok_buckets.py - split a TikTok bookmark dump into sub-collection buckets by tag and link type

Reads a JSON list of Raindrop bookmarks (see extract_bookmarks.py), puts each one in a
bucket by its tags first (cats, animals, ...) and, when untagged, by link shape
(tiktok.com/share/user = profile, otherwise video). Prints one update_bookmarks
operation per bucket, split into batches of at most 150 IDs (the tool's limit per call).

Edit BUCKETS and the collection IDs for your own sub-collections.

Usage:
    uv run scripts/raindrop/tiktok_buckets.py bookmarks.json            # counts only
    uv run scripts/raindrop/tiktok_buckets.py bookmarks.json --ops      # batches of operations as JSON
"""

import argparse
import json
import sys
from collections import defaultdict

# bucket name -> (sub-collection id, tags that put a bookmark in it)
BUCKETS = {
    "Cats": (77178782, {"cats"}),
    "Other animals": (77178783, {"animals"}),
    "Politics, religion & esoterica": (77178784, {"politics", "religion", "esoteric"}),
    "Memes, media & art": (77178785, {"memes", "music", "art", "film & cinema", "fashion"}),
    "History & tools": (77178786, {"history", "tools"}),
}
PROFILES = ("Untagged profiles", 77178787)
VIDEOS = ("Untagged videos", 77178788)


def bucket_of(b):
    tags = {t.lower() for t in b.get("tags") or []}
    for name, (cid, wanted) in BUCKETS.items():  # first match wins, in order
        if tags & wanted:
            return name, cid
    return PROFILES if "/share/user/" in b["link"] else VIDEOS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("dump")
    ap.add_argument("--ops", action="store_true", help="print update_bookmarks batches")
    a = ap.parse_args()
    groups = defaultdict(list)
    ids = {}
    for b in json.load(open(a.dump, encoding="utf-8")):
        name, cid = bucket_of(b)
        groups[name].append(b["bookmark_id"])
        ids[name] = cid
    for name, items in groups.items():
        print(f"{len(items):4d}  {name} ({ids[name]})", file=sys.stderr)
    if a.ops:
        n = 0
        for name, items in groups.items():
            for i in range(0, len(items), 150):
                n += 1
                op = [{"bookmark_ids": items[i:i + 150], "collection_id": ids[name]}]
                print(json.dumps({"batch": n, "bucket": name, "updates": op}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
