#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["gallery-dl"]
# ///
"""
tiktok_meta.py - fetch TikTok video metadata (caption, hashtags, category, stats) with gallery-dl into a CSV

Runs `gallery-dl --dump-json` on each TikTok video link, which prints the video's metadata
without downloading the video. Input is a text file of URLs (one per line) or a JSON dump
of Raindrop bookmarks (see scripts/raindrop/extract_bookmarks.py). Only /share/video/<id> and
/@user/video/<id> links are fetched; profile links are skipped because gallery-dl would
download a whole account.

CSV columns: bookmark_id, url, video_id, author, nickname, caption, hashtags, categories
(TikTok's own diversificationLabels), language, location, created_utc, plays, likes,
comments, shares, music, status. Rows already in the output are skipped, so a rerun
resumes. Failed videos (deleted, private, blocked) get a status and are retried with --retry.
Writes fetch-log-{timestamp}.txt every run.

Usage:
    uv run scripts/tiktok/tiktok_meta.py videos.json                     # -> tiktok-meta.csv
    uv run scripts/tiktok/tiktok_meta.py urls.txt -o meta.csv --workers 3 --limit 20
    uv run scripts/tiktok/tiktok_meta.py videos.json --retry             # redo failed rows
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

COLS = ["bookmark_id", "url", "video_id", "author", "nickname", "caption", "hashtags", "categories",
        "language", "location", "created_utc", "plays", "likes", "comments", "shares", "music", "status"]
VIDEO_RE = re.compile(r"/(?:share/)?video/(\d+)")


def load_inputs(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [(str(b["bookmark_id"]), b["link"]) for b in json.loads(text)]
    return [("", l.strip()) for l in text.splitlines() if l.strip().startswith("http")]


def fetch(url: str, tries: int = 3):
    """Return the metadata dict for one video, or raise RuntimeError(reason)."""
    last = "unknown error"
    for n in range(tries):
        p = subprocess.run([sys.executable, "-m", "gallery_dl", "--dump-json", url],
                           capture_output=True, text=True, timeout=120)
        if p.returncode == 0 and p.stdout.strip():
            try:
                for kind, *rest in json.loads(p.stdout):
                    if kind == 2:
                        return rest[0]
            except (ValueError, TypeError):
                pass
            err = [l for l in p.stderr.splitlines() if "[error]" in l or "[warning]" in l]
            last = err[-1].split("] ", 1)[-1][:200] if err else "no metadata in output"
            if re.search(r"not available|not found|private|unavailable|removed|404", last, re.I):
                break
        else:
            last = (p.stderr.strip().splitlines() or ["no output"])[-1][:200]
            if re.search(r"404|not found|private|unavailable|removed", last, re.I):
                break
        time.sleep(2 * (n + 1))
    raise RuntimeError(last)


def row_for(bid: str, url: str, m: dict) -> dict:
    s = m.get("stats") or {}
    a = m.get("author") or {}
    created = int(m["createTime"]) if str(m.get("createTime", "")).isdigit() else None
    return {
        "bookmark_id": bid, "url": url, "video_id": m.get("id", ""),
        "author": a.get("uniqueId", "") if isinstance(a, dict) else str(a),
        "nickname": a.get("nickname", "") if isinstance(a, dict) else "",
        "caption": (m.get("desc") or "").replace("\n", " "),
        "hashtags": " ".join(t["hashtagName"] for t in m.get("textExtra") or [] if t.get("hashtagName")),
        "categories": "; ".join(m.get("diversificationLabels") or []),
        "language": m.get("textLanguage", ""), "location": m.get("locationCreated", ""),
        "created_utc": datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created else "",
        "plays": s.get("playCount", ""), "likes": s.get("diggCount", ""),
        "comments": s.get("commentCount", ""), "shares": s.get("shareCount", ""),
        "music": (m.get("music") or {}).get("title", ""), "status": "ok",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("tiktok-meta.csv"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, help="only fetch this many new rows (for a test run)")
    ap.add_argument("--retry", action="store_true", help="refetch rows whose status is not ok")
    a = ap.parse_args()

    done = {}
    if a.output.exists():
        for r in csv.DictReader(a.output.open(encoding="utf-8")):
            done[r["url"]] = r
    items, skipped = [], 0
    for bid, url in load_inputs(a.input):
        if not VIDEO_RE.search(url):
            skipped += 1
        elif url not in done or (a.retry and done[url]["status"] != "ok"):
            items.append((bid, url))
    items = items[: a.limit] if a.limit else items
    started = datetime.now()
    print(f"{len(items)} to fetch, {len(done)} already in {a.output}, {skipped} not video links (skipped)")

    results, errors = {}, []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(fetch, url): (bid, url) for bid, url in items}
        for n, f in enumerate(as_completed(futs), 1):
            bid, url = futs[f]
            try:
                results[url] = row_for(bid, url, f.result())
            except Exception as e:  # noqa: BLE001 - record every failure, keep going
                errors.append((url, str(e)))
                results[url] = {**{c: "" for c in COLS}, "bookmark_id": bid, "url": url, "status": f"error: {e}"[:150]}
            if n % 25 == 0 or n == len(futs):
                print(f"  {n}/{len(futs)} ({len(errors)} errors)")

    done.update(results)
    with a.output.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(done.values())

    log = Path(f"fetch-log-{started:%Y-%m-%d_%H%M%S}.txt")
    lines = ["tiktok_meta results log", f"Run started : {started:%Y-%m-%d %H:%M:%S}", f"Input       : {a.input}",
             f"Output      : {a.output}", "", "SUMMARY", f"  Fetched ok : {len(results) - len(errors)}",
             f"  Errors     : {len(errors)}", f"  Not videos : {skipped}", "", f"ERRORS ({len(errors)})"]
    lines += [f"  {u}\n    {e}" for u, e in errors] or ["  (none)"]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {a.output}; log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
