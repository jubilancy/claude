# /// script
# requires-python = ">=3.10"
# ///
"""Convert the Flickr metadata CSV (the one with photo_id, image_url, attribution... columns)
into an Are.na-ready CSV for arena_upload.py.

uv run arena/flickr_csv_to_arena.py flickr_metadata.csv arena.csv [--channel my-channel-slug]

The block's source is the Flickr page, not the image file. Tags, license, attribution, creator
and the albums / groups / galleries are merged into the description.
"""
import argparse
import csv
import html
import re

LINK_ITEM = re.compile(r"^(.*?)\s*\((https?://[^)\s]+)\)$")
ANCHOR = re.compile(r'<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def plain(text):
    """Flickr descriptions hold HTML: keep links as markdown, drop the rest."""
    text = ANCHOR.sub(lambda m: f"[{re.sub(r'<[^>]+>', '', m[2]).strip() or m[1]}]({m[1]})", text or "")
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()


def links(cell):
    """'Title (url) | Title (url)' -> markdown links, one per entry."""
    out = []
    for item in (cell or "").split(" | "):
        item = item.strip()
        if not item:
            continue
        m = LINK_ITEM.match(item)
        out.append(f"[{m[1] or m[2]}]({m[2]})" if m else item)
    return out


def row(r):
    creator = r.get("creator", "").strip()
    profile = r.get("creator_profile", "").strip()
    page = r.get("flickr_url", "").strip()
    lines = [plain(r.get("description"))]
    attribution = r.get("attribution", "").strip()
    lines.append(attribution)
    if creator and not attribution:  # the attribution line already credits the creator
        lines.append(f"by [{creator}]({profile})" if profile else f"by {creator}")
    if r.get("tags", "").strip():
        lines.append("Tags: " + r["tags"].strip())
    if r.get("license", "").strip():
        lines.append("License: " + r["license"].strip())
    for label, key in (("Albums", "albums"), ("Groups", "groups"), ("Galleries", "galleries")):
        items = links(r.get(key))
        if items:
            lines.append(f"{label}: " + " · ".join(items))
    if page:
        lines.append(f"photo [source]({page})")
    title = plain(r.get("title"))
    return {
        "value": r["image_url"].strip(),
        "title": title,
        "description": "\n\n".join(l for l in lines if l),
        "original_source_url": page,
        "original_source_title": f"Flickr · {creator}" if creator else "Flickr",
        "alt_text": title,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--channel", help="channel slug/id, adds a channel_ids column")
    a = ap.parse_args()

    with open(a.src, newline="", encoding="utf-8-sig") as f:
        src = list(csv.DictReader(f))

    rows, seen, skipped = [], set(), 0
    for r in src:
        key = (r.get("photo_id") or "").strip() or r.get("image_url", "")
        if not (r.get("image_url") or "").strip():
            skipped += 1
            continue
        if key in seen:  # the same photo is listed once per source URL it came from
            continue
        seen.add(key)
        rows.append(row(r))

    cols = ["value", "title", "description", "original_source_url", "original_source_title", "alt_text"]
    if a.channel:
        cols.append("channel_ids")
        for r in rows:
            r["channel_ids"] = a.channel
    with open(a.dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} photos -> {a.dst}" + (f" ({skipped} rows without an image URL skipped)" if skipped else ""))


if __name__ == "__main__":
    main()
