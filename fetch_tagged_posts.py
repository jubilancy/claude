#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "markdownify"]
# ///

"""
Tumblr post fetcher
-------------------
Two modes, same rich JSON record per post (text, media, links, reblog
info, metadata):

1. Tag mode (default): pulls ALL posts from BLOG with each tag in TAGS,
   paginating through the Tumblr API (max 20 posts per call).

       uv run fetch_tagged_posts.py

2. URL mode: reads a text file with one Tumblr URL per line, from any
   blog, and fetches the info for each. Blank lines and lines starting
   with # are ignored; anything after the URL on a line is ignored.

       uv run fetch_tagged_posts.py --urls urls.txt

   Supported URL types (see parse_tumblr_url):
     https://staff.tumblr.com/post/123456789[/slug]    post, tumblr.com blog
     https://example.com/post/123456789[/slug]         post, custom domain
     https://example.com/123456789[/slug]              post, custom domain (no /post/)
     https://www.tumblr.com/staff/123456789[/slug]     post, www.tumblr.com form
     https://www.tumblr.com/@staff/123456789[/slug]    post, @name form
     https://tmblr.co/...                              short link (redirect is followed)
     https://staff.tumblr.com/tagged/some+tag          every post with that tag
     https://www.tumblr.com/staff/tagged/some+tag      every post with that tag

   Posts that can't be fetched are listed in the *-failed.txt file, which
   can be passed back in as a urls file to retry them.

Put your API key in API_KEY below (keep this file private if you do).
If API_KEY is left empty, the TUMBLR_API_KEY environment variable is used.
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import unquote_plus, urlsplit

import requests
from markdownify import markdownify

# ─── EDIT THESE ────────────────────────────────────────────────
BLOG = "garadinervi"        # blog short name (no .tumblr.com needed)
TAGS = ["book"]             # tags to fetch; one JSON file is written per tag
API_KEY = ""                # paste your OAuth Consumer Key between the quotes
# ────────────────────────────────────────────────────────────────

API_KEY = API_KEY.strip() or os.environ.get("TUMBLR_API_KEY", "").strip()

LIMIT = 20  # API max per call, do not change
HEADERS = {"User-Agent": "fetch_tagged_posts/1.0"}  # Tumblr asks for a consistent User-Agent
SHORT_LINK_HOSTS = {"tmblr.co"}


def blog_identifier(blog: str) -> str:
    """A bare name becomes name.tumblr.com; a hostname (custom domain) is kept as is."""
    return blog if "." in blog else f"{blog}.tumblr.com"


def output_file(tag: str, blog: str = BLOG) -> str:
    safe_tag = re.sub(r"[^\w-]+", "_", tag).strip("_")
    safe_blog = re.sub(r"[^\w.-]+", "_", blog)
    return f"{safe_blog}-{safe_tag}-posts.json"


def strip_html(raw: str | None) -> str:
    raw = re.sub(r"<[^>]*>", " ", raw or "")  # strip HTML tags
    return re.sub(r"\s+", " ", raw).strip()   # collapse whitespace


def extract_description(post: dict) -> str:
    """Legacy format: prefer summary, then body/caption stripped of HTML."""
    raw = post.get("summary") or post.get("body") or post.get("caption") or post.get("description") or ""
    return strip_html(raw)


def html_to_md(raw: str | None) -> str:
    """HTML -> Markdown, keeping links, emphasis, lists and paragraph breaks."""
    md = markdownify(raw or "", heading_style="ATX", bullets="-")
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def extract_photos(post: dict) -> list[dict]:
    photos = []
    for p in post.get("photos") or []:
        original = p.get("original_size") or {}
        photos.append({
            "url": original.get("url"),
            "width": original.get("width"),
            "height": original.get("height"),
            "caption": strip_html(p.get("caption")),
            "caption_md": html_to_md(p.get("caption")),
            "alt_text": p.get("alt_text"),
        })
    return photos


def extract_reblog(post: dict) -> dict:
    """Reblog provenance (populated because we request reblog_info=true)."""
    return {
        "is_reblog": bool(post.get("reblogged_from_id") or post.get("reblogged_root_id")),
        "reblogged_from_name": post.get("reblogged_from_name"),
        "reblogged_from_url": post.get("reblogged_from_url"),
        "reblogged_root_name": post.get("reblogged_root_name"),
        "reblogged_root_url": post.get("reblogged_root_url"),
    }


def build_record(post: dict) -> dict:
    return {
        # identity
        "id": post.get("id_string") or str(post.get("id")),
        "type": post.get("type"),
        "blog_name": post.get("blog_name"),
        "url": post.get("post_url"),
        "short_url": post.get("short_url"),
        "slug": post.get("slug"),
        # time
        "date": post.get("date"),
        "timestamp": post.get("timestamp"),
        # text
        "title": post.get("title"),
        "description": extract_description(post),
        "description_md": html_to_md(post.get("body") or post.get("caption") or post.get("description")),
        "body_html": post.get("body"),
        "caption_html": post.get("caption"),
        "format": post.get("format"),
        "tags": post.get("tags"),
        # media
        "photos": extract_photos(post),
        "image_permalink": post.get("image_permalink"),
        "video_url": post.get("video_url"),
        "audio_url": post.get("audio_url"),
        "audio_source_url": post.get("audio_source_url"),
        "track_name": post.get("track_name"),
        "artist": post.get("artist"),
        "album": post.get("album"),
        # links / sources
        "link_url": post.get("url") if post.get("type") == "link" else post.get("link_url"),
        "link_publisher": post.get("publisher"),
        "source_url": post.get("source_url"),
        "source_title": post.get("source_title"),
        # engagement / state
        "note_count": post.get("note_count"),
        "state": post.get("state"),
        # reblog provenance
        **extract_reblog(post),
    }


def fetch_all_tagged_posts(tag: str, blog: str = BLOG) -> list[dict]:
    results = []
    offset = 0
    total = None

    session = requests.Session()
    session.headers.update(HEADERS)
    url = f"https://api.tumblr.com/v2/blog/{blog_identifier(blog)}/posts"

    while True:
        params = {
            "tag": tag,
            "api_key": API_KEY,
            "limit": LIMIT,
            "offset": offset,
            "reblog_info": "true",   # adds reblogged_from_* / reblogged_root_* fields
            "npf": "false",          # legacy format (explicit)
        }

        print(f"[{tag}] Fetching offset={offset} ...")
        res = session.get(url, params=params, timeout=30)

        if not res.ok:
            raise RuntimeError(f"Request failed ({res.status_code}): {res.text}")

        response = res.json().get("response", {})
        posts = response.get("posts", [])
        # NB: with a tag filter, Tumblr's total_posts is the blog total, not the tag total,
        # so it is shown for context only and not used to stop pagination.
        total = response.get("total_posts", total)

        if not posts:
            print("No more posts. Done.")
            break

        results.extend(build_record(post) for post in posts)

        print(f"  got {len(posts)} posts (total so far: {len(results)}; blog has {total} posts overall)")

        offset += LIMIT
        time.sleep(0.3)  # be polite to the API

    return results


# ─── URL mode ──────────────────────────────────────────────────


class RateLimited(Exception):
    pass


def parse_tumblr_url(raw: str) -> dict | None:
    """
    Turn one URL into {"kind": "post", "blog", "id"} or {"kind": "tag", "blog", "tag"},
    or None if it isn't a recognised Tumblr post/tag URL.

    - On tumblr.com the blog is the first path segment (optionally with a leading @).
    - On <name>.tumblr.com or a custom domain the blog is the hostname, and the path
      is [/post]/<id>[/<slug>] or /tagged/<tag>.
    """
    if "://" not in raw:
        raw = "https://" + raw
    u = urlsplit(raw)
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]
    if not host or not parts:
        return None

    if host in ("tumblr.com", "www.tumblr.com"):
        if parts[0] in ("post", "blog", "dashboard", "tagged", "search"):
            return None  # no blog named in the URL
        blog, parts = parts[0].lstrip("@"), parts[1:]
    else:
        blog = host
        if parts[0] == "post":
            parts = parts[1:]

    if not blog or not parts:
        return None
    if parts[0].isdigit():
        return {"kind": "post", "blog": blog, "id": parts[0]}
    if parts[0] == "tagged" and len(parts) > 1:
        return {"kind": "tag", "blog": blog, "tag": unquote_plus(parts[1])}
    return None


def read_urls(path: str) -> list[str]:
    urls, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            url = line.split()[0]  # allow trailing notes, e.g. a failed-file reason
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def resolve_short_link(session: requests.Session, url: str) -> str:
    res = session.get(url, allow_redirects=True, timeout=30, stream=True)
    final = res.url
    res.close()
    return final


def fetch_post(session: requests.Session, blog: str, post_id: str) -> dict | None:
    """One post by ID, or None if Tumblr says 404 (deleted, private, or wrong blog)."""
    res = session.get(
        f"https://api.tumblr.com/v2/blog/{blog_identifier(blog)}/posts",
        params={"id": post_id, "api_key": API_KEY, "reblog_info": "true", "npf": "false"},
        timeout=30,
    )
    if res.status_code == 404:
        return None
    if res.status_code == 429:
        raise RateLimited(res.text)
    if not res.ok:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:200]}")
    posts = res.json().get("response", {}).get("posts", [])
    return posts[0] if posts else None


def run_urls(path: str, out: str) -> int:
    session = requests.Session()
    session.headers.update(HEADERS)
    records, failed = [], []
    urls = read_urls(path)
    print(f"Read {len(urls)} unique URLs from {path}")

    try:
        for n, url in enumerate(urls, 1):
            label = f"[{n}/{len(urls)}]"
            try:
                host = (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower()
                target = url
                if host in SHORT_LINK_HOSTS:
                    target = resolve_short_link(session, url)
                    print(f"{label} {url} -> {target}")
                info = parse_tumblr_url(target)
                if info is None:
                    failed.append((url, "unrecognised URL format"))
                    print(f"{label} skipped (unrecognised format): {url}")
                    continue

                if info["kind"] == "tag":
                    posts = fetch_all_tagged_posts(info["tag"], info["blog"])
                    found = [build_record(p) for p in posts]
                else:
                    post = fetch_post(session, info["blog"], info["id"])
                    found = [build_record(post)] if post else []
                if not found:
                    failed.append((url, "not found (deleted, private, or wrong blog)"))
                    print(f"{label} not found: {url}")
                    continue
                for rec in found:
                    rec["requested_url"] = url
                records.extend(found)
                print(f"{label} ok ({len(found)} post{'s' if len(found) != 1 else ''}): {url}")
            except RateLimited:
                failed.append((url, "rate limited"))
                raise
            except Exception as e:  # keep going; the failed file records why
                failed.append((url, f"{type(e).__name__}: {e}"[:300].replace("\n", " ")))
                print(f"{label} failed: {url} ({e})")
            time.sleep(0.3)  # be polite to the API
    except RateLimited:
        done = {r for r, _ in failed} | {r.get("requested_url") for r in records}
        failed.extend((u, "not attempted (stopped by rate limit)") for u in urls if u not in done)
        print("\nHit Tumblr's rate limit; saving what was fetched so far. "
              "Re-run with the failed file later.")

    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(records)} posts to {out}")

    if failed:
        failed_path = re.sub(r"\.json$", "", out) + "-failed.txt"
        with open(failed_path, "w", encoding="utf-8") as f:
            f.writelines(f"{u}\t# {why}\n" for u, why in failed)
        print(f"{len(failed)} URLs failed; listed in {failed_path}")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="Fetch Tumblr posts by tag, or from a file of URLs.")
    ap.add_argument("--urls", metavar="FILE", help="text file with one Tumblr URL per line (any blog)")
    ap.add_argument("--out", metavar="FILE", default="urls-posts.json",
                    help="output JSON for --urls mode (default: %(default)s)")
    args = ap.parse_args()

    if not API_KEY or API_KEY in ("YOUR_API_KEY_HERE", "KEY"):
        print('⚠️  Paste your key into API_KEY at the top of this script (API_KEY = "...") before running.')
        raise SystemExit(1)

    if args.urls:
        raise SystemExit(run_urls(args.urls, args.out))

    for tag in TAGS:
        posts = fetch_all_tagged_posts(tag)
        out = output_file(tag)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(posts)} posts to {out}\n")


if __name__ == "__main__":
    main()
