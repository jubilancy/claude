#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
List every post under every tag of a WordPress site (via its REST API).

One CSV row per (tag, post): tag, tag_url, post_title, post_url, post_date.
Posts with no tags are skipped (add --include-untagged to keep them).

    uv run wp_tag_posts.py https://longreads.com
    uv run wp_tag_posts.py https://longreads.com --max-pages 2   # quick test

It reads every tag first, then every post in ascending ID order, so new posts
published while it runs land at the end instead of shifting earlier pages.
Requests are retried with backoff. A page that still fails is skipped and listed
at the end, and rows are written as it goes, so a stop never loses what it has.
"""
import argparse, csv, html, sys, time
from urllib.parse import urlsplit

import requests

ap = argparse.ArgumentParser()
ap.add_argument("site")
ap.add_argument("--max-pages", type=int, default=0, help="stop each crawl after N pages (0 = all)")
ap.add_argument("--include-untagged", action="store_true")
ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
args = ap.parse_args()

site = args.site.rstrip("/")
host = urlsplit(site).netloc
s = requests.Session()
s.headers["User-Agent"] = "wp_tag_posts/1.0"
failed_pages = []


def get(endpoint, page, fields):
    """GET one page with retries. Returns (items, total_pages) or (None, None) after giving up."""
    for attempt in range(6):
        try:
            r = s.get(f"{site}/wp-json/wp/v2/{endpoint}", timeout=60,
                      params={"per_page": 100, "page": page, "_fields": fields,
                              "orderby": "id", "order": "asc"})
            if r.status_code == 400 and page > 1:
                return [], page  # past the last page
            if r.status_code == 429 or r.status_code >= 500:
                wait = int(r.headers.get("Retry-After", 0)) or 2 ** (attempt + 1)
            else:
                r.raise_for_status()
                return r.json(), int(r.headers.get("X-WP-TotalPages", page))
        except (requests.ConnectionError, requests.Timeout):
            wait = 2 ** (attempt + 1)
        print(f"  {endpoint} page {page}: retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    failed_pages.append(f"{endpoint} page {page}")
    return None, None


def crawl(endpoint, fields):
    page, pages = 1, 1
    while page <= pages and not (args.max_pages and page > args.max_pages):
        items, total = get(endpoint, page, fields)
        if items is not None:
            pages = max(pages, total)
            yield page, pages, items
            if not items:
                return
        page += 1
        time.sleep(args.delay)


tags = {}
for page, pages, items in crawl("tags", "id,name,link"):
    for t in items:
        tags[t["id"]] = (html.unescape(t["name"]), t["link"])
    print(f"tags  page {page}/{pages}: {len(tags)} tags")

out = f"{host}-tag-posts.csv"
rows = posts_seen = 0
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tag", "tag_url", "post_title", "post_url", "post_date"])
    for page, pages, items in crawl("posts", "id,link,title,tags,date"):
        for p in items:
            posts_seen += 1
            title = html.unescape(p["title"]["rendered"])
            ids = p["tags"] or ([] if not args.include_untagged else [None])
            for tid in ids:
                name, url = tags.get(tid, (f"(tag {tid})", "") if tid else ("", ""))
                w.writerow([name, url, title, p["link"], p["date"]])
                rows += 1
        f.flush()
        print(f"posts page {page}/{pages}: {posts_seen} posts, {rows} rows")

print(f"\nSaved {rows} rows from {posts_seen} posts to {out}")
if failed_pages:
    print(f"{len(failed_pages)} pages failed after retries and were skipped:", *failed_pages, sep="\n  ")
    sys.exit(1)
