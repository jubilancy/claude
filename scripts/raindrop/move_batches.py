#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
move_batches.py - turn {bucket: [bookmark ids]} into update_bookmarks calls of at most 150 IDs

The update_bookmarks tool accepts 150 bookmark IDs per call in total, across all its
operations, so small buckets share a call and big ones are split. Input is a JSON object
of bucket name -> list of IDs; --map is a JSON object of bucket name -> sub-collection id.
Prints one JSON array per call, ready to paste as the tool's `updates` argument.

Usage:
    uv run scripts/raindrop/move_batches.py buckets.json --map collections.json
"""

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("buckets")
    ap.add_argument("--map", required=True, help="JSON: bucket name -> collection id")
    a = ap.parse_args()
    buckets = json.load(open(a.buckets, encoding="utf-8"))
    cid = json.load(open(a.map, encoding="utf-8"))
    missing = set(buckets) - set(cid)
    if missing:
        print(f"no collection id for: {sorted(missing)}", file=sys.stderr)
        return 1
    flat = [(i, cid[k]) for k, ids in buckets.items() for i in sorted(set(ids))]
    if len({i for i, _ in flat}) != len(flat):
        print("a bookmark is in more than one bucket", file=sys.stderr)
        return 1
    for n in range(0, len(flat), 150):
        ops = {}
        for i, c in flat[n:n + 150]:
            ops.setdefault(c, []).append(i)
        print(json.dumps([{"bookmark_ids": v, "collection_id": k} for k, v in ops.items()], separators=(",", ":")))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
