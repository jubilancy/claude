# /// script
# requires-python = ">=3.11"
# dependencies = ["gallery-dl", "yt-dlp"]
# ///
"""Download Instagram, Twitter/X and TikTok posts listed in urls.txt with
gallery-dl, then write a readable, timestamped manifest next to the media.

Each run creates archive/<timestamp>/ containing:
  media/                  downloaded files + gallery-dl's raw .json sidecars
  manifest-<timestamp>.csv  one row per file; `open` is a clickable link
  index.html              visual gallery of the same rows (open in a browser)
  failed.txt              input URLs that produced no files (only if any)

Usage: uv run social_archive.py [--urls urls.txt] [--cookies cookies.txt]
"""
import argparse
import csv
import html
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Filenames carry the post's identity so a file can always be credited from its name.
CONFIG = {
    "extractor": {
        "instagram": {"filename": "instagram.com-p-{post_shortcode}_{num:>02}.{extension}"},
        "twitter": {"filename": "x.com-{author[name]}-status-{tweet_id}_{num:>02}.{extension}"},
        "tiktok": {"filename": "tiktok.com-{user}-video-{id}{num:?_//>02}.{extension}"},
    }
}

COLUMNS = [
    "platform", "posted_at", "author", "author_name", "text", "kind", "item",
    "open", "file", "post_url", "input_url", "likes", "comments", "shares",
    "views", "saves", "hashtags", "width", "height", "description",
]

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".m4a", ".mp3"}
VIDEO_EXTS = {".mp4", ".mov", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def read_urls(path: Path) -> list[str]:
    lines = (l.strip() for l in path.read_text(encoding="utf-8").splitlines())
    return [l for l in lines if l and not l.startswith("#")]


def platform_of(meta: dict, name: str) -> str:
    cat = meta.get("category")
    if cat in ("instagram", "twitter", "tiktok"):
        return cat
    return next((p for p in ("instagram", "twitter", "tiktok") if name.startswith(p) or name.startswith("x.com")), "")


def g(d, *path, default=""):
    for key in path:
        if not isinstance(d, dict) or d.get(key) is None:
            return default
        d = d[key]
    return d


def extras(meta: dict, lines: dict) -> str:
    """Properties with no column of their own, one `key: value` per line."""
    return "\n".join(f"{k}: {v}" for k, v in lines.items() if v not in ("", None, [], {}, False))


def row_instagram(m: dict) -> dict:
    return {
        "posted_at": m.get("post_date") or m.get("date", ""),
        "author": m.get("username", ""),
        "author_name": m.get("fullname", ""),
        "text": m.get("description", ""),
        "kind": m.get("type", ""),
        "item": f"{m.get('num', '')}/{m.get('count', '')}",
        "post_url": m.get("post_url", ""),
        "likes": m.get("likes", ""),
        "hashtags": " ".join(f"#{t}" for t in m.get("tags", [])),
        "width": m.get("width", ""),
        "height": m.get("height", ""),
        "description": extras(m, {
            "post_id": m.get("post_id"),
            "owner_id": m.get("owner_id"),
            "location": m.get("location_slug"),
            "location_url": m.get("location_url"),
            "coauthors": ", ".join(c.get("username", "") for c in m.get("coauthors", [])),
            "pinned": m.get("pinned"),
            "media_id": m.get("media_id"),
        }),
    }


def row_twitter(m: dict) -> dict:
    handle = g(m, "author", "name")
    return {
        "posted_at": m.get("date", ""),
        "author": handle,
        "author_name": g(m, "author", "nick"),
        "text": m.get("content", ""),
        "kind": "reply" if m.get("reply_id") else ("retweet" if m.get("retweet_id") else "tweet"),
        "item": f"{m.get('num', '')}/{m.get('count', '')}",
        "post_url": f"https://x.com/{handle}/status/{m['tweet_id']}" if m.get("tweet_id") else "",
        "likes": m.get("favorite_count", ""),
        "comments": m.get("reply_count", ""),
        "shares": m.get("retweet_count", ""),
        "views": m.get("view_count", ""),
        "saves": m.get("bookmark_count", ""),
        "hashtags": " ".join(f"#{t}" for t in m.get("hashtags", [])),
        "width": m.get("width", ""),
        "height": m.get("height", ""),
        "description": extras(m, {
            "tweet_id": m.get("tweet_id"),
            "conversation_id": m.get("conversation_id"),
            "quotes": m.get("quote_count"),
            "lang": m.get("lang"),
            "sensitive": m.get("sensitive"),
            "via": m.get("source"),
        }),
    }


def row_tiktok(m: dict) -> dict:
    stats = m.get("stats") or {}
    return {
        "posted_at": m.get("date", ""),
        "author": m.get("user", ""),
        "author_name": g(m, "author", "nickname"),
        "text": m.get("desc", ""),
        "kind": m.get("post_type", ""),
        "item": f"{m.get('num', '')}/" if m.get("num") else "",
        "post_url": f"https://www.tiktok.com/@{m['user']}/video/{m['id']}" if m.get("user") and m.get("id") else "",
        "likes": stats.get("diggCount", ""),
        "comments": stats.get("commentCount", ""),
        "shares": stats.get("shareCount", ""),
        "views": stats.get("playCount", ""),
        "saves": stats.get("collectCount", ""),
        "hashtags": " ".join(f"#{t['hashtagName']}" for t in m.get("textExtra", []) if t.get("hashtagName")),
        "width": m.get("width") or g(m, "video", "width"),
        "height": m.get("height") or g(m, "video", "height"),
        "description": extras(m, {
            "id": m.get("id"),
            "sound": g(m, "music", "title"),
            "sound_by": g(m, "music", "authorName"),
            "duration_s": g(m, "video", "duration"),
            "location": g(m, "locationCreated"),
        }),
    }


ROW_BUILDERS = {"instagram": row_instagram, "twitter": row_twitter, "tiktok": row_tiktok}


def safe_cell(value) -> str:
    """Stop spreadsheets from reading scraped text as a formula."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def hyperlink(rel: str) -> str:
    return '=HYPERLINK("{}","open")'.format(rel.replace('"', '""'))


def sidecar_for(path: Path) -> Path | None:
    for cand in (path.with_name(path.name + ".json"), path.with_suffix(".json")):
        if cand.exists():
            return cand
    return None


def download(urls: list[str], run_dir: Path, cookies: Path | None) -> dict[Path, str]:
    media_dir = run_dir / "media"
    media_dir.mkdir(parents=True)
    config = run_dir / "gallery-dl.conf"
    config.write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    owner: dict[Path, str] = {}
    failed: list[str] = []
    for url in urls:
        before = set(media_dir.iterdir())
        cmd = [sys.executable, "-m", "gallery_dl", "-c", str(config), "-D", str(media_dir),
               "--write-metadata", "--sleep", "2"]
        if cookies:
            cmd += ["-C", str(cookies)]
        print(f"→ {url}", flush=True)
        subprocess.run(cmd + [url], check=False)
        new = [p for p in set(media_dir.iterdir()) - before if p.suffix.lower() in MEDIA_EXTS]
        owner.update({p: url for p in new})
        if not new:
            failed.append(url)
    if failed:
        (run_dir / "failed.txt").write_text("\n".join(failed) + "\n", encoding="utf-8")
        print(f"{len(failed)} URL(s) produced no files; see failed.txt", file=sys.stderr)
    return owner


def build_rows(owner: dict[Path, str], run_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(owner, key=lambda p: p.name):
        sc = sidecar_for(path)
        meta = json.loads(sc.read_text(encoding="utf-8")) if sc else {}
        platform = platform_of(meta, path.name)
        row = dict.fromkeys(COLUMNS, "")
        row.update(ROW_BUILDERS.get(platform, lambda m: {})(meta))
        rel = path.relative_to(run_dir).as_posix()
        row.update(platform=platform, file=rel, open=hyperlink(rel), input_url=owner[path])
        rows.append(row)
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads UTF-8
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (v if k == "open" else safe_cell(v)) for k, v in r.items()})


def write_gallery(rows: list[dict], path: Path, stamp: str) -> None:
    cards = []
    for r in rows:
        ext = Path(r["file"]).suffix.lower()
        src = html.escape(r["file"], quote=True)
        if ext in VIDEO_EXTS:
            media = f'<video src="{src}" controls preload="metadata"></video>'
        elif ext in IMAGE_EXTS:
            media = f'<a href="{src}"><img src="{src}" loading="lazy" alt=""></a>'
        else:
            media = f'<audio src="{src}" controls></audio>'
        stats = " · ".join(f"{label} {html.escape(str(r[k]))}"
                           for k, label in (("likes", "♥"), ("comments", "💬"), ("shares", "↻"), ("views", "▶"))
                           if r[k] != "")
        post = (f'<a href="{html.escape(r["post_url"], quote=True)}">{html.escape(r["post_url"])}</a>'
                if r["post_url"] else "")
        cards.append(
            f'<article>{media}<div class="meta">'
            f'<b>{html.escape(r["platform"])}</b> @{html.escape(str(r["author"]))} · {html.escape(str(r["posted_at"]))}'
            f'<p>{html.escape(str(r["text"]))}</p><small>{stats}</small><small>{post}</small>'
            f'<small>{html.escape(r["file"])}</small></div></article>')
    path.write_text(f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archive {stamp}</title>
<style>
:root{{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--card:#f4f4f5;--mute:#666}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--card:#1c1c1e;--mute:#999}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
article{{background:var(--card);border-radius:8px;overflow:hidden}}
img,video{{display:block;width:100%;max-height:420px;object-fit:contain;background:#000}}
.meta{{padding:10px 12px}} .meta p{{margin:.4em 0;white-space:pre-wrap;overflow-wrap:anywhere}}
small{{display:block;color:var(--mute);overflow-wrap:anywhere}} a{{color:inherit}}
</style>
<h1>Archive {stamp}</h1><main>{''.join(cards)}</main>""", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", type=Path, default=HERE / "urls.txt")
    ap.add_argument("--cookies", type=Path, default=HERE / "cookies.txt")
    ap.add_argument("--out", type=Path, default=HERE / "archive")
    args = ap.parse_args()

    urls = read_urls(args.urls)
    if not urls:
        sys.exit(f"No URLs in {args.urls}")
    cookies = args.cookies if args.cookies.exists() else None
    if not cookies:
        print(f"Warning: {args.cookies} not found; Instagram will likely fail.", file=sys.stderr)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = args.out / stamp
    owner = download(urls, run_dir, cookies)
    rows = build_rows(owner, run_dir)
    write_csv(rows, run_dir / f"manifest-{stamp}.csv")
    write_gallery(rows, run_dir / "index.html", stamp)
    print(f"\n{len(rows)} file(s) → {run_dir}")


if __name__ == "__main__":
    main()
