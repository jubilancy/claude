#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
saved_to_table.py - Instagram data export -> one CSV table of every saved post.

What it does:
- Reads saved_posts.json and saved_collections.json from an Instagram
  "Download your information" export (JSON format). Both live in
  your_instagram_activity/saved/.
- Builds one row per saved post (saved_posts.json is the master list), with the
  collections it is in (joined with " | ", or "(none)"), caption, hashtags,
  owner username, the date it was saved, and the post type (p / reel / tv).
- Matches posts across the two files by shortcode, so URL variants
  (/p/X/, /username/reel/X/) still match.
- Repairs Instagram's mojibake (UTF-8 text exported as Latin-1), so captions
  and collection names with emoji or accents read correctly.
- Posts that are in a collection but not in saved_posts.json are NOT added to
  the table; they are listed under WARNINGS in the log.
- Writes a UTF-8 CSV (with BOM, so Google Sheets and Excel read it right).
- Writes results-log-{timestamp}.txt in the current folder every run, with
  separate lists for written, skipped, and errors, plus warnings.

Usage:
    uv run scripts/instagram/saved_to_table.py --input /path/to/saved
    uv run scripts/instagram/saved_to_table.py --input /path/to/saved --output saved-posts.csv
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = ["post_url", "shortcode", "type", "collections", "collection_count",
           "caption", "hashtags", "owner", "saved_at"]
POST_RE = re.compile(r"instagram\.com/(?:[^/]+/)?(p|reel|reels|tv)/([^/?#]+)")
NONE_LABEL = "(none)"


def fix(s):
    """Undo Instagram's Latin-1-for-UTF-8 mojibake; leave clean text alone."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def parse_url(url):
    m = POST_RE.search(url or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def label(entry, name):
    for x in entry.get("label_values", []):
        if x.get("label") == name:
            return x
    return {}


def find_urls(node, out):
    """Collect every post-looking URL anywhere inside a collection entry."""
    if isinstance(node, dict):
        if node.get("label") == "URL" and parse_url(node.get("value"))[1]:
            out.append(node["value"])
        for v in node.values():
            find_urls(v, out)
    elif isinstance(node, list):
        for v in node:
            find_urls(v, out)


def dict_block(entry, title):
    for x in entry.get("label_values", []):
        if x.get("title") == title:
            return x.get("dict", [])
    return []


def hashtags(entry):
    tags = []
    for d in dict_block(entry, "Hashtags"):
        for sub in d.get("dict", []):
            if sub.get("label") == "Name" and sub.get("value"):
                tags.append("#" + fix(sub["value"]))
    return " ".join(tags)


def owner(entry):
    for d in dict_block(entry, "Owner"):
        for sub in d.get("dict", []):
            if sub.get("label") == "Username" and sub.get("value"):
                return fix(sub["value"])
    return ""


def iso(ts):
    if not isinstance(ts, int):
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main():
    ap = argparse.ArgumentParser(description="Instagram saved posts -> CSV table")
    ap.add_argument("--input", required=True, help="folder with saved_posts.json and saved_collections.json")
    ap.add_argument("--output", default="saved-posts.csv", help="CSV to write (default ./saved-posts.csv)")
    args = ap.parse_args()

    started = datetime.now()
    in_dir, out_path = Path(args.input), Path(args.output)
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")

    written, skipped_dupes, skipped_nourl, errors, warnings = [], [], [], [], []
    total = 0
    try:
        posts = json.loads((in_dir / "saved_posts.json").read_text(encoding="utf-8"))
        colls = json.loads((in_dir / "saved_collections.json").read_text(encoding="utf-8"))
    except Exception as e:  # unreadable input: still write a log
        errors.append((str(in_dir), f"could not read input: {e}"))
        posts, colls = [], []

    # shortcode -> list of collection names
    member = {}
    for c in colls:
        try:
            name = fix(label(c, "Name").get("value", "")) or "(unnamed)"
            urls = []
            find_urls(c, urls)
            for sc in {parse_url(u)[1] for u in urls}:
                member.setdefault(sc, [])
                if name not in member[sc]:
                    member[sc].append(name)
        except Exception as e:
            errors.append((f"collection entry {c.get('timestamp')}", str(e)))

    seen = set()
    rows = []
    for e in posts:
        total += 1
        try:
            url = label(e, "URL").get("value", "")
            kind, sc = parse_url(url)
            if not sc:
                skipped_nourl.append((url or "(no URL)", "no Instagram post shortcode in URL"))
                continue
            if sc in seen:
                skipped_dupes.append((url, "duplicate shortcode already in table"))
                continue
            seen.add(sc)
            cols = member.get(sc, [])
            rows.append([url, sc, kind, " | ".join(cols) if cols else NONE_LABEL, len(cols),
                         fix(label(e, "Caption").get("value", "")), hashtags(e), owner(e),
                         iso(e.get("timestamp"))])
            written.append((url, f"collections: {len(cols)}"))
        except Exception as ex:
            errors.append((str(label(e, "URL").get("value", "?")), str(ex)))

    for sc, names in member.items():
        if sc not in seen:
            warnings.append((sc, "in collection(s) " + " | ".join(names) + " but not in saved_posts.json"))

    try:
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(rows)
    except Exception as e:
        errors.append((str(out_path), f"could not write CSV: {e}"))

    finished = datetime.now()
    skipped_total = len(skipped_dupes) + len(skipped_nourl)
    lines = [
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} (duration {(finished - started).total_seconds():.1f}s)",
        f"Input       : {in_dir}",
        f"Output      : {out_path}",
        "",
        "SUMMARY",
        f"  Total posts in saved_posts.json : {total}",
        f"  Done this run (written)         : {len(written)}",
        "  Already done (skipped)          : 0",
        f"  Skipped on purpose              : {skipped_total}",
        f"  Errors                          : {len(errors)}",
        f"  Warnings                        : {len(warnings)}",
        f"  Rows with no collection         : {sum(1 for r in rows if r[3] == NONE_LABEL)}",
        "",
    ]

    def section(title, items, limit=None):
        lines.append(f"{title} ({len(items)})")
        if not items:
            lines.append("  (none)")
        for a, b in (items if limit is None else items[:limit]):
            lines.append(f"  {a}")
            lines.append(f"      {b}")
        if limit is not None and len(items) > limit:
            lines.append(f"  ... {len(items) - limit} more not shown")
        lines.append("")

    section("SUCCESSFUL: WRITTEN", written)
    section("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", [])
    section("SKIPPED ON PURPOSE: DUPLICATE SHORTCODE", skipped_dupes)
    section("SKIPPED ON PURPOSE: NO POST URL", skipped_nourl)
    section("ERRORS", errors)
    section("WARNINGS", warnings)
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(written)} rows to {out_path}")
    print(f"Results log: {log_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
