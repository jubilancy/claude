#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
List every tag on a WordPress site (via its REST API), no posts fetched.

One CSV row per tag: tag, tag_url, title, count.
`title` is the tag page's SEO title (e.g. "Zoë Bernard Archives - Longreads")
when the site runs Yoast SEO, otherwise the tag name.

    uv run wp_tags.py https://longreads.com
    uv run wp_tags.py https://longreads.com --max-pages 2   # quick test

Requests are retried with backoff. A page that still fails is skipped and listed
at the end, and rows are written as it goes, so a stop never loses what it has.
"""
import argparse, csv, html, sys, time
from urllib.parse import urlsplit

import requests

ap = argparse.ArgumentParser()
ap.add_argument("site")
ap.add_argument("--max-pages", type=int, default=0, help="stop after N pages (0 = all)")
ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
args = ap.parse_args()

site = args.site.rstrip("/")
host = urlsplit(site).netloc
s = requests.Session()
s.headers["User-Agent"] = "wp_tags/1.0"
failed_pages = []


def get(page):
    """GET one page of tags with retries. Returns (items, total_pages) or (None, None) after giving up."""
    for attempt in range(6):
        try:
            r = s.get(f"{site}/wp-json/wp/v2/tags", timeout=60,
                      params={"per_page": 100, "page": page, "orderby": "id", "order": "asc",
                              "_fields": "id,name,link,count,yoast_head_json.title"})
            if r.status_code == 400 and page > 1:
                return [], page  # past the last page
            if r.status_code == 429 or r.status_code >= 500:
                wait = int(r.headers.get("Retry-After", 0)) or 2 ** (attempt + 1)
            else:
                r.raise_for_status()
                return r.json(), int(r.headers.get("X-WP-TotalPages", page))
        except (requests.ConnectionError, requests.Timeout):
            wait = 2 ** (attempt + 1)
        print(f"  page {page}: retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    failed_pages.append(page)
    return None, None


out = f"{host}-tags.csv"
rows, page, pages = 0, 1, 1
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tag", "tag_url", "title", "count"])
    while page <= pages and not (args.max_pages and page > args.max_pages):
        items, total = get(page)
        if items is not None:
            pages = max(pages, total)
            for t in items:
                name = html.unescape(t["name"])
                title = html.unescape((t.get("yoast_head_json") or {}).get("title") or name)
                w.writerow([name, t["link"], title, t["count"]])
            rows += len(items)
            f.flush()
            print(f"page {page}/{pages}: {rows} tags")
            if not items:
                break
        page += 1
        time.sleep(args.delay)

print(f"\nSaved {rows} tags to {out}")
if failed_pages:
    print(f"{len(failed_pages)} pages failed after retries and were skipped: {failed_pages}")
    sys.exit(1)
