#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
flickr_sort.py - sort a list of Flickr URLs by type into a markdown file

Reads one URL per line (anything not starting with http is ignored), drops duplicates,
and groups them by what the path points at: single photos, albums, collections,
galleries, photographer profiles, groups, tag pages, searches, people pages, site pages.
Writes a markdown file with a heading and count per type and prints the counts.

Usage:
    uv run scripts/web/flickr_sort.py urls.txt
    uv run scripts/web/flickr_sort.py urls.txt -o flickr_sorted.md
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ORDER = ["Single photos", "Albums", "Collections", "Galleries", "Photographer profiles", "Groups",
         "Tag pages", "Searches", "People and group-membership pages", "Site pages (home, about, help, services)"]


def kind(url: str) -> str:
    seg = [s for s in urlsplit(url).path.split("/") if s]
    if not seg:
        return ORDER[-1]
    if seg[0] == "search":
        return "Searches"
    if seg[0] == "groups":
        return "Groups"
    if seg[0] == "people":
        return "People and group-membership pages"
    if seg[0] == "photos":
        if len(seg) > 1 and seg[1] == "tags":
            return "Tag pages"
        if len(seg) == 2:
            return "Photographer profiles"
        if len(seg) > 2:
            third = seg[2]
            if third == "tags":
                return "Tag pages"
            if third == "galleries":
                return "Galleries"
            if third in ("albums", "sets"):
                return "Albums"
            if third == "collections":
                return "Collections"
            if third.isdigit():
                return "Single photos"
            if third == "in":
                return "Photographer profiles"
    return ORDER[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("urls", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("flickr_sorted.md"))
    a = ap.parse_args()
    urls = [l.strip() for l in a.urls.read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")]
    uniq = list(dict.fromkeys(urls))
    groups = defaultdict(list)
    for u in uniq:
        groups[kind(u)].append(u)
    lines = [f"# Flickr URLs by type ({len(uniq)} unique of {len(urls)})", ""]
    for k in ORDER:
        if k in groups:
            lines += [f"## {k} ({len(groups[k])})", ""] + [f"- {u}" for u in sorted(groups[k])] + [""]
            print(f"{len(groups[k]):4d}  {k}")
    a.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
