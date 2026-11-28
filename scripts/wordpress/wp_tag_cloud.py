#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
wp_tag_cloud.py - fetch every tag of a WordPress.com site and write a paste-ready HTML tag cloud.

What it does:
- Pages through the WordPress.com REST API (100 tags per page) for one site.
- Sizes each tag's font between --min-size and --max-size from its post count
  (logarithmic, so one huge tag doesn't flatten the rest).
- Writes one HTML file: a <div> of inline-styled links, alphabetical. Paste it
  into a Custom HTML block. No theme CSS needed.
- Private sites (like fromdaysoff.wordpress.com) refuse anonymous requests, so
  pass a WordPress.com OAuth token in the WPCOM_TOKEN environment variable.
  Public sites work with no token.
- Skips tags below --min-count, and duplicate tag IDs, on purpose.
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    WPCOM_TOKEN=xxxx uv run scripts/wordpress/wp_tag_cloud.py fromdaysoff.wordpress.com
    uv run scripts/wordpress/wp_tag_cloud.py example.wordpress.com --output cloud.html
    uv run scripts/wordpress/wp_tag_cloud.py SITE --min-count 2 --min-size 12 --max-size 36
    uv run scripts/wordpress/wp_tag_cloud.py SITE --from-json tags.json   # offline: JSON list of tag objects
"""

import argparse
import html
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request as ur
from datetime import datetime
from pathlib import Path

USER_AGENT = "wp-tag-cloud/1.0"
API = "https://public-api.wordpress.com/wp/v2/sites/{site}/tags"
MAX_RETRIES = 5


def get_page(site: str, page: int, token: str):
    """Return (tags, total_pages) for one page. Retries on 429/5xx."""
    qs = up.urlencode({"per_page": 100, "page": page, "orderby": "count", "order": "desc",
                       "hide_empty": "true", "_fields": "id,name,link,count"})
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    delay = 3.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            with ur.urlopen(ur.Request(f"{API.format(site=site)}?{qs}", headers=headers), timeout=40) as r:
                return json.load(r), int(r.headers.get("X-WP-TotalPages", 1))
        except urllib.error.HTTPError as e:
            if (e.code == 429 or e.code >= 500) and attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            body = e.read().decode("utf-8", "replace")[:200]
            hint = " (private site? set WPCOM_TOKEN)" if e.code in (400, 401, 403) else ""
            raise RuntimeError(f"HTTP {e.code} on page {page}{hint}: {body}")
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"network problem on page {page}: {e.reason}")


def font_size(count: int, lo: int, hi: int, min_size: float, max_size: float) -> float:
    if hi == lo:
        return (min_size + max_size) / 2
    t = (math.log(count) - math.log(lo)) / (math.log(hi) - math.log(lo)) if lo > 0 else 0
    return min_size + t * (max_size - min_size)


def build_html(tags, min_size, max_size) -> str:
    counts = [t["count"] for t in tags]
    lo, hi = min(counts), max(counts)
    parts = ['<div class="tag-cloud" style="line-height:1.8;text-align:center;">']
    for t in sorted(tags, key=lambda t: t["name"].lower()):
        size = font_size(t["count"], lo, hi, min_size, max_size)
        name = html.escape(html.unescape(t["name"]))
        parts.append(
            f'<a href="{html.escape(t["link"], quote=True)}" title="{t["count"]} post'
            f'{"" if t["count"] == 1 else "s"}" style="font-size:{size:.1f}px;margin:0 6px;'
            f'display:inline-block;">{name}</a>')
    parts.append("</div>")
    return "\n".join(parts) + "\n"


def write_log(path: Path, meta, written, dup, low, errors):
    L = ["wp_tag_cloud results log",
         f"Run started : {meta['started']}",
         f"Run finished: {meta['finished']} (took {meta['secs']:.1f}s)",
         f"Input       : {meta['input']}",
         f"Output file : {meta['output']}",
         "",
         "SUMMARY",
         f"  Total tags fetched                 : {meta['total']}",
         f"  Written to cloud                   : {len(written)}",
         f"  Already done (duplicate IDs)       : {len(dup)}",
         f"  Skipped on purpose (below min)     : {len(low)}",
         f"  Errors                             : {len(errors)}",
         "",
         f"SUCCESSFUL: WRITTEN ({len(written)})"]
    L += [f"  {n}\n    count {c}, {s:.1f}px" for n, c, s in written] or ["  (none)"]
    L += ["", f"SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT ({len(dup)})"]
    L += [f"  {n}\n    duplicate tag ID" for n in dup] or ["  (none)"]
    L += ["", f"SKIPPED ON PURPOSE: BELOW --min-count ({len(low)})"]
    L += [f"  {n}\n    count {c}" for n, c in low] or ["  (none)"]
    L += ["", f"ERRORS ({len(errors)})"]
    L += [f"  {w}\n    {e}" for w, e in errors] or ["  (none)"]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="WordPress.com tags -> paste-ready HTML tag cloud.")
    ap.add_argument("site", help="site domain, e.g. fromdaysoff.wordpress.com")
    ap.add_argument("--output", default="tag-cloud.html")
    ap.add_argument("--min-count", type=int, default=1, help="skip tags with fewer posts (default 1)")
    ap.add_argument("--min-size", type=float, default=13)
    ap.add_argument("--max-size", type=float, default=34)
    ap.add_argument("--from-json", help="read tags from a JSON file instead of the API")
    a = ap.parse_args()

    site = a.site.replace("https://", "").replace("http://", "").strip("/")
    token = os.environ.get("WPCOM_TOKEN", "")
    started = datetime.now()
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    raw, errors = [], []

    if a.from_json:
        try:
            data = json.loads(Path(a.from_json).read_text(encoding="utf-8"))
            raw = data["data"] if isinstance(data, dict) else data
        except Exception as e:
            errors.append((a.from_json, str(e)))
    else:
        page, pages = 1, 1
        while page <= pages:
            print(f"page {page}/{pages}")
            try:
                tags, pages = get_page(site, page, token)
                raw += tags
            except Exception as e:
                errors.append((f"page {page}", str(e)))
                print(f"  ERROR: {e}", file=sys.stderr)
                break
            page += 1
            time.sleep(0.3)

    seen, dup, low, keep = set(), [], [], []
    for t in raw:
        if t["id"] in seen:
            dup.append(t["name"])
        elif t["count"] < max(a.min_count, 1):
            seen.add(t["id"])
            low.append((t["name"], t["count"]))
        else:
            seen.add(t["id"])
            keep.append(t)

    written = []
    if keep:
        Path(a.output).write_text(build_html(keep, a.min_size, a.max_size), encoding="utf-8")
        lo, hi = min(t["count"] for t in keep), max(t["count"] for t in keep)
        written = [(t["name"], t["count"], font_size(t["count"], lo, hi, a.min_size, a.max_size))
                   for t in sorted(keep, key=lambda t: t["name"].lower())]
    finished = datetime.now()
    write_log(log_path, {"started": started.strftime("%Y-%m-%d %H:%M:%S"),
                         "finished": finished.strftime("%Y-%m-%d %H:%M:%S"),
                         "secs": (finished - started).total_seconds(),
                         "input": a.from_json or API.format(site=site),
                         "output": a.output, "total": len(raw)},
              written, dup, low, errors)
    print(f"\nDone: {len(written)} tags in {a.output}, {len(dup)} duplicate, "
          f"{len(low)} below min, {len(errors)} errors.\nResults log: {log_path}")


if __name__ == "__main__":
    main()
