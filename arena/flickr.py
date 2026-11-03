# /// script
# requires-python = ">=3.10"
# dependencies = ["gallery-dl"]
# ///
"""Flickr -> Are.na in one script.

    uv run arena/flickr.py run     urls.txt --channel your-channel-slug      # all three steps
    uv run arena/flickr.py fetch   urls.txt [flickr_metadata.csv]            # 1. look up the photos
    uv run arena/flickr.py convert [flickr_metadata.csv] [flickr_arena.csv] [--channel SLUG]  # 2. make the upload CSV
    uv run arena/flickr.py upload  [flickr_arena.csv] --channel SLUG         # 3. upload (arena_upload.py)

urls.txt takes anything gallery-dl's Flickr extractor takes (photos, albums, galleries, group
pools, favorites, user photostreams, search results). Nothing is downloaded: gallery-dl only looks
up each photo's information.

Every step can be stopped with Ctrl+C and run again:
  fetch   skips photos already in the metadata CSV (no API calls spent on them)
  upload  skips rows already uploaded (arena_upload.py keeps <csv>.uploaded)

Settings for gallery-dl go in gallery-dl.conf next to this script (or in the current folder). By
default this script asks gallery-dl for each photo's license and the albums / groups it is in.
The token for the upload is read by arena_upload.py: ARENA_TOKEN, or TOKEN at the top of that file.
"""

import argparse
import csv
import html
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

META_COLUMNS = [
    "photo_id", "title", "description", "creator", "creator_profile",
    "tags", "image_url", "flickr_url", "license", "attribution",
    "albums", "groups", "galleries", "source_url",
]
ARENA_COLUMNS = ["value", "title", "description", "original_source_url", "original_source_title", "alt_text"]

# ───────────────────────── Step 1: look up the photos ─────────────────────────


def text_of(value):
    """Flickr sometimes wraps text as {"_content": "..."}."""
    if isinstance(value, dict):
        return value.get("_content", "")
    return value or ""


def join_items(items):
    """['Title (url)', ...] -> one cell separated by ' | '."""
    return " | ".join(i for i in items if i)


def fmt(title, url):
    return f"{title} ({url})" if url else str(title)


def build_row(photo, galleries, source_url):
    owner = photo.get("owner")
    if not isinstance(owner, dict):
        owner = {"nsid": owner or photo.get("user", {}).get("nsid", "")}
    nsid = owner.get("nsid", "")
    username = owner.get("username") or photo.get("user", {}).get("username", "")
    creator = owner.get("realname") or username or nsid
    profile_id = owner.get("path_alias") or nsid
    profile = f"https://www.flickr.com/photos/{profile_id}/" if profile_id else ""

    photo_id = photo.get("id", "")
    flickr_url = f"https://www.flickr.com/photos/{profile_id}/{photo_id}/"

    title = text_of(photo.get("title"))
    lic = photo.get("license_name") or ""
    if lic == "All Rights Reserved":
        attribution = f"© {creator}, all rights reserved ({flickr_url})"
    elif lic:
        attribution = f'"{title}" by {creator} ({flickr_url}), {lic}'
    else:  # license unknown: do not claim one
        attribution = f'"{title}" by {creator} ({flickr_url})'

    albums = [
        fmt(s.get("title", ""), f"https://www.flickr.com/photos/{profile_id}/albums/{s.get('id')}")
        for s in photo.get("set", [])
    ]
    groups = [
        fmt(p.get("title", ""), "https://www.flickr.com" + p["url"] if p.get("url", "").startswith("/") else p.get("url", ""))
        for p in photo.get("pool", [])
    ]
    tags = photo.get("tags", [])
    if isinstance(tags, list):
        tags = ", ".join(str(t) for t in tags)

    return {
        "photo_id": photo_id,
        "title": title,
        "description": text_of(photo.get("description")),
        "creator": creator,
        "creator_profile": profile,
        "tags": tags,
        "image_url": photo.get("url", ""),
        "flickr_url": flickr_url,
        "license": lic,
        "attribution": attribution,
        "albums": join_items(albums),
        "groups": join_items(groups),
        "galleries": join_items(galleries),
        "source_url": source_url,
    }


def get_galleries(ex, photo_id):
    """Galleries a photo is in (gallery-dl doesn't fetch these itself)."""
    try:
        data = ex.api._call("galleries.getListForPhoto", {"photo_id": photo_id})
        return [
            fmt(text_of(g.get("title")), g.get("url", ""))
            for g in data.get("galleries", {}).get("gallery", [])
        ]
    except Exception as exc:
        print(f"    (galleries lookup failed for {photo_id}: {exc})")
        return []


def load_seen(path):
    """Photo IDs already in an existing CSV. A row cut off by Ctrl+C is dropped (the file is
    rewritten without it) so it gets fetched again. Returns (seen_ids, needs_header)."""
    if not path.exists() or path.stat().st_size == 0:
        return set(), True
    ends_cleanly = path.read_bytes().endswith(b"\n")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    good = [r for r in rows
            if r.get("photo_id") and r.get("source_url")
            and None not in r and None not in r.values()]
    if len(good) != len(rows) or not ends_cleanly:
        print(f"Cleaning up {len(rows) - len(good)} incomplete row(s) in {path}")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=META_COLUMNS)
            writer.writeheader()
            writer.writerows({k: r[k] for k in META_COLUMNS} for r in good)
    return {str(r["photo_id"]) for r in good}, False


def skip_lookups_for_seen(seen):
    """Stop gallery-dl from spending its per-photo info/contexts requests on photos that are
    already in the CSV."""
    from gallery_dl.extractor.flickr import FlickrAPI

    original = FlickrAPI._extract_metadata

    def patched(self, photo, info=True):
        if str(photo.get("id")) in seen:
            return
        return original(self, photo, info)

    FlickrAPI._extract_metadata = patched


def configure_gallery_dl(conf=None):
    """Ask for the license and the albums / groups of every photo, then let gallery-dl.conf
    override that."""
    from gallery_dl import config

    config.set(("extractor", "flickr"), "metadata", True)  # license, date taken, original format...
    config.set(("extractor", "flickr"), "contexts", True)  # the albums and groups a photo is in
    for path in ([Path(conf)] if conf else [HERE / "gallery-dl.conf", Path("gallery-dl.conf")]):
        if path.exists():
            config.load([str(path)])
            print(f"Using settings from {path}")
            return


def fetch(urls_file, out_file, conf=None):
    from gallery_dl import extractor
    from gallery_dl.extractor.message import Message

    urls_file, out_file = Path(urls_file), Path(out_file)
    configure_gallery_dl(conf)

    urls = [
        line.strip() for line in urls_file.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    print(f"{len(urls)} URL(s) found in {urls_file}")

    seen, need_header = load_seen(out_file)
    if seen:
        print(f"Resuming: {len(seen)} photo(s) already in {out_file}")
    skip_lookups_for_seen(seen)

    added = 0
    with open(out_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=META_COLUMNS)
        if need_header:
            writer.writeheader()

        try:
            for n, url in enumerate(urls, 1):
                print(f"[{n}/{len(urls)}] {url}")
                ex = extractor.find(url)
                if ex is None:
                    print("    unsupported URL, skipping")
                    continue
                skipped = 0
                try:
                    for msg in ex:
                        if msg[0] != Message.Url:
                            continue
                        photo = msg[2]
                        pid = str(photo.get("id"))
                        if pid in seen:
                            skipped += 1
                            continue
                        seen.add(pid)
                        galleries = get_galleries(ex, pid)
                        writer.writerow(build_row(photo, galleries, url))
                        f.flush()
                        added += 1
                        print(f"    + {pid}  {str(text_of(photo.get('title')))[:50]}  (new: {added})")
                except Exception as exc:
                    print(f"    failed: {exc}")
                    print("    (run again to retry; finished photos are kept)")
                if skipped:
                    print(f"    skipped {skipped} already in CSV")
        except KeyboardInterrupt:
            print("\nStopped. Run the same command again to resume.")
            return False

    print(f"Added {added} new photo(s); {len(seen)} total in {out_file}")
    return True


# ───────────────────────── Step 2: make the upload CSV ─────────────────────────

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


def arena_row(r):
    creator = r.get("creator", "").strip()
    profile = r.get("creator_profile", "").strip()
    page = r.get("flickr_url", "").strip()
    attribution = r.get("attribution", "").strip()
    lines = [plain(r.get("description")), attribution]
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
        "original_source_url": page,  # the Flickr page, not the image file
        "original_source_title": f"Flickr · {creator}" if creator else "Flickr",
        "alt_text": title,
    }


def convert(src, dst, channel=None):
    with open(src, newline="", encoding="utf-8-sig") as f:
        source_rows = list(csv.DictReader(f))

    rows, seen, skipped = [], set(), 0
    for r in source_rows:
        key = (r.get("photo_id") or "").strip() or r.get("image_url", "")
        if not (r.get("image_url") or "").strip():
            skipped += 1
            continue
        if key in seen:  # the same photo is listed once per source URL it came from
            continue
        seen.add(key)
        rows.append(arena_row(r))

    cols = list(ARENA_COLUMNS)
    if channel:
        cols.append("channel_ids")
        for r in rows:
            r["channel_ids"] = channel
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} photos -> {dst}" + (f" ({skipped} rows without an image URL skipped)" if skipped else ""))


# ───────────────────────── Step 3: upload ─────────────────────────


def upload(csv_file, channel, delay=1.0, dry_run=False):
    """arena_upload.py is shared with the Pinterest scripts, so this calls it instead of copying it."""
    spec = importlib.util.spec_from_file_location("arena_upload", HERE / "arena_upload.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = ["arena_upload.py", str(csv_file), "--channel", channel, "--delay", str(delay)]
    if dry_run:
        argv.append("--dry-run")
    saved, sys.argv = sys.argv, argv
    try:
        module.main()
    finally:
        sys.argv = saved


# ───────────────────────── Command line ─────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Flickr -> Are.na", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="look up the photos in urls.txt and write the metadata CSV")
    p.add_argument("urls", nargs="?", default="urls.txt")
    p.add_argument("out", nargs="?", default="flickr_metadata.csv")
    p.add_argument("--config", help="gallery-dl.conf to use (default: next to this script, then the current folder)")

    p = sub.add_parser("convert", help="turn the metadata CSV into the Are.na upload CSV")
    p.add_argument("src", nargs="?", default="flickr_metadata.csv")
    p.add_argument("dst", nargs="?", default="flickr_arena.csv")
    p.add_argument("--channel", help="channel slug/id, adds a channel_ids column")

    p = sub.add_parser("upload", help="upload the Are.na CSV (calls arena_upload.py)")
    p.add_argument("csv", nargs="?", default="flickr_arena.csv")
    p.add_argument("--channel", required=True)
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("run", help="fetch, convert and upload")
    p.add_argument("urls", nargs="?", default="urls.txt")
    p.add_argument("--channel", required=True)
    p.add_argument("--metadata", default="flickr_metadata.csv", help="metadata CSV to write (default flickr_metadata.csv)")
    p.add_argument("--arena-csv", default="flickr_arena.csv", help="upload CSV to write (default flickr_arena.csv)")
    p.add_argument("--config")
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--dry-run", action="store_true", help="fetch and convert, but only print what would be uploaded")

    a = ap.parse_args()
    if a.cmd == "fetch":
        sys.exit(0 if fetch(a.urls, a.out, a.config) else 1)
    if a.cmd == "convert":
        convert(a.src, a.dst, a.channel)
    elif a.cmd == "upload":
        upload(a.csv, a.channel, a.delay, a.dry_run)
    elif a.cmd == "run":
        if not fetch(a.urls, a.metadata, a.config):
            sys.exit(1)
        convert(a.metadata, a.arena_csv)
        upload(a.arena_csv, a.channel, a.delay, a.dry_run)


if __name__ == "__main__":
    main()
