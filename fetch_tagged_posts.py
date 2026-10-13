#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "markdownify"]
# ///

"""
Tumblr tagged-posts fetcher
---------------------------
Pulls ALL posts from a given blog with a given tag, paginating
through the Tumblr API (max 20 posts per call) until exhausted.
Outputs a rich JSON record (text, media, links, reblog info, metadata)
for each post to a JSON file.

Usage:
    uv run fetch_tagged_posts.py
"""

import json
import re
import time

import requests
from markdownify import markdownify

# ─── EDIT THESE ────────────────────────────────────────────────
BLOG = "garadinervi"        # blog short name (no .tumblr.com needed)
TAG = "book"                # tag to filter by
API_KEY = "KEY"  # your OAuth Consumer Key
# ────────────────────────────────────────────────────────────────

LIMIT = 20  # API max per call, do not change
OUTPUT_FILE = f"{BLOG}-{TAG}-posts.json"


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


def fetch_all_tagged_posts() -> list[dict]:
    results = []
    offset = 0
    total = None

    session = requests.Session()
    url = f"https://api.tumblr.com/v2/blog/{BLOG}.tumblr.com/posts"

    while True:
        params = {
            "tag": TAG,
            "api_key": API_KEY,
            "limit": LIMIT,
            "offset": offset,
            "reblog_info": "true",   # adds reblogged_from_* / reblogged_root_* fields
            "npf": "false",          # legacy format (explicit)
        }

        print(f"Fetching offset={offset} ...")
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


def main():
    if API_KEY in ("YOUR_API_KEY_HERE", "KEY"):
        print("⚠️  Set your API_KEY at the top of this script before running.")
        raise SystemExit(1)

    posts = fetch_all_tagged_posts()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(posts)} posts to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
