#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
tiktok_by_upload_date.py - bucket TikTok video bookmarks by the upload date hidden in the video ID

The number at the end of a tiktokv.com/share/video/<id> link carries the upload time:
shifting the ID right by 32 bits gives a Unix timestamp. Raindrop only knows when you saved
the link, which is the same for a bulk import, so this recovers a real date. Links that are
not /share/video/<id> (profiles, short links) are listed as undated and left alone.

Reads a dump from extract_bookmarks.py. Edit PERIODS to change the buckets. Without --map it
prints counts; with --map (JSON: bucket name -> sub-collection id) and --ops it prints
update_bookmarks operations in batches of at most 150 IDs.

Usage:
    uv run scripts/raindrop/tiktok_by_upload_date.py videos.json                       # counts per period
    uv run scripts/raindrop/tiktok_by_upload_date.py videos.json --map ids.json --ops  # move batches
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

# (bucket name, first day inclusive, first day after the period)
PERIODS = [
    ("Uploaded before Sep 2025", "0000-01-01", "2025-09-01"),
    ("Sep 2025 - Mar 2026", "2025-09-01", "2026-04-01"),
    ("Apr 2026", "2026-04-01", "2026-05-01"),
    ("May 2026 (1-15)", "2026-05-01", "2026-05-16"),
    ("May 2026 (16-31)", "2026-05-16", "2026-06-01"),
    ("Jun - Jul 2026", "2026-06-01", "9999-12-31"),
]
ID_RE = re.compile(r"/share/video/(\d+)")


def upload_day(link: str):
    m = ID_RE.search(link)
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) >> 32, timezone.utc).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("dump")
    ap.add_argument("--map", help="JSON: bucket name -> collection id")
    ap.add_argument("--ops", action="store_true")
    a = ap.parse_args()
    groups, undated = defaultdict(list), []
    days = []
    for b in json.load(open(a.dump, encoding="utf-8")):
        day = upload_day(b["link"])
        if day is None:
            undated.append(b)
            continue
        days.append(day)
        for name, lo, hi in PERIODS:
            if lo <= day < hi:
                groups[name].append(b["bookmark_id"])
                break
    print(f"dated uploads: {min(days)} to {max(days)}", file=sys.stderr)
    for name, _, _ in PERIODS:
        print(f"{len(groups[name]):5d}  {name}", file=sys.stderr)
    print(f"{len(undated):5d}  undated (left alone): " + ", ".join(b["link"] for b in undated[:5]), file=sys.stderr)
    if a.ops and a.map:
        cid = json.load(open(a.map, encoding="utf-8"))
        flat = [(i, cid[n]) for n, _, _ in PERIODS for i in groups[n]]
        for k in range(0, len(flat), 150):
            ops = {}
            for i, c in flat[k:k + 150]:
                ops.setdefault(c, []).append(i)
            print(json.dumps([{"bookmark_ids": v, "collection_id": c} for c, v in ops.items()], separators=(",", ":")))
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
