# /// script
# requires-python = ">=3.10"
# ///
"""Flatten gallery-dl Flickr JSON (-j output) into an Are.na-ready CSV.

uv run arena/flickr_to_csv.py flickr_2026-10-11_09-30-00.json photos.csv [--channel my-channel-slug]

Same columns as pins_to_csv.py, so arena_upload.py takes the result unchanged. Works with the
dump written by classify_flickr_urls.py (galleries, albums, group pools, favorites, user
photostreams, search results and single photos).
"""
import argparse
import csv
import html
import json
import re
import unicodedata

FLICKR = "https://www.flickr.com"


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def text_of(value):
    """Flickr wraps some strings as {"_content": "..."}."""
    if isinstance(value, dict):
        value = value.get("_content")
    return clean(str(value)) if value else ""


def owner_of(photo):
    owner = photo.get("owner") or {}
    if not isinstance(owner, dict):
        owner = {"username": str(owner)}
    ident = owner.get("path_alias") or owner.get("nsid") or ""
    name = owner.get("username") or owner.get("realname") or ident
    return ident, name


def context_of(photo):
    """Where gallery-dl found the photo: gallery, album or group pool."""
    out = []
    for key, label in (("gallery", "Gallery"), ("album", "Album")):
        title = text_of((photo.get(key) or {}).get("title"))
        if title:
            out.append(f"{label}: {title}")
    group = (photo.get("group") or {}).get("groupname")
    if group:
        out.append(f"Group: {text_of(group)}")
    return out


def row(photo, url):
    ident, name = owner_of(photo)
    page = f"{FLICKR}/photos/{ident}/{photo['id']}/" if ident else f"{FLICKR}/photo.gne?id={photo['id']}"
    lines = [text_of(photo.get("description")), f"photo [source]({page})"]
    if name:
        lines.append(f"by [{name}]({FLICKR}/photos/{ident}/)" if ident else f"by {name}")
    tags = photo.get("tags") or []
    if tags:
        lines.append("Tags: " + ", ".join(tags))
    lines += context_of(photo)
    if photo.get("date"):
        lines.append(f"Uploaded: {str(photo['date'])[:10]}")
    return {
        "value": url,
        "title": text_of(photo.get("title")),
        "description": "\n\n".join(l for l in lines if l),
        "original_source_url": page,
        "original_source_title": f"Flickr · {name}" if name else "Flickr",
        "alt_text": text_of(photo.get("title")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--channel", help="channel slug/id, adds a channel_ids column")
    a = ap.parse_args()

    # gallery-dl -j -i urls.txt prints one JSON array per URL, back to back
    with open(a.src, encoding="utf-8") as f:
        text = f.read()
    dec, pos, data = json.JSONDecoder(), 0, []
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        chunk, pos = dec.raw_decode(text, pos)
        data.extend(chunk if isinstance(chunk, list) else [chunk])

    rows, seen, videos, queued = [], set(), 0, 0
    for e in data:
        # gallery-dl -j: [2, {dir meta}], [3, "file url", {file meta}], [6, "url", {meta}] for queued sub-URLs
        if isinstance(e, list) and e and e[0] == 6:
            queued += 1
            continue
        if not (isinstance(e, list) and e and e[0] == 3 and len(e) >= 3 and isinstance(e[2], dict)):
            continue
        photo = e[2]
        url = photo.get("url") or ""  # the sized image URL; e[1] is the forced-download (_d) variant
        if not url.startswith("https://") or photo.get("media") == "video" or "/video/" in url:
            videos += 1  # a video gives a player address, not a file Are.na can fetch
            continue
        if url in seen:  # the same photo can sit in several galleries or albums
            continue
        seen.add(url)
        rows.append(row(photo, url))

    cols = ["value", "title", "description", "original_source_url", "original_source_title", "alt_text"]
    if a.channel:
        cols.append("channel_ids")
        for r in rows:
            r["channel_ids"] = a.channel
    with open(a.dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} photos -> {a.dst}")
    if videos:
        print(f"skipped {videos} videos or entries without an image URL")
    if queued:
        print(f"{queued} queued sub-URLs were not followed (an all-albums URL lists album links); run those album URLs through gallery-dl too")


if __name__ == "__main__":
    main()
