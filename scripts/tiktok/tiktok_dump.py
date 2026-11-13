#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["gallery-dl"]
# ///
"""
tiktok_dump.py - get ALL the metadata for TikTok links with gallery-dl, without downloading, into JSON + CSV + theme batches

For every TikTok video link it runs `gallery-dl --dump-json` (metadata only, nothing is
downloaded) and writes:
  <out>.json   the full, untouched metadata for every link: [{"url": ..., "status": ..., "metadata": {...}}]
  <out>.csv    one row per link, TikTok URL in the first column, then a short set of useful columns:
               bookmark_id, status, video_id, author, nickname, caption, hashtags, categories (TikTok's
               own diversificationLabels), language, location, created_utc, duration_s, plays, likes,
               comments, shares, saves, music, author_followers, author_verified, author_bio.
               Add --all-columns to flatten every metadata field into the CSV as well (200+ columns).
  batches/     with --by THEME: one <theme>.txt per theme, one URL per line, plus batches/_index.csv.
               Download a theme later with:  gallery-dl -i batches/<theme>.txt -d downloads/<theme>

Input is a text file of URLs (one per line) or a JSON dump of Raindrop bookmarks (see
scripts/raindrop/extract_bookmarks.py). Profile links are skipped (gallery-dl would fetch a whole account).
Reruns resume: links already in <out>.json are not fetched again; failed ones are retried with --retry.
A rerun with nothing new to fetch just rebuilds the CSV and batches from the JSON.
Every run writes results-log-{timestamp}.txt in the current folder, with a summary, separate lists
for fetched, skipped and errors, and warnings (videos with no caption, hashtags or category).

--by category   first TikTok category label of each video   --by hashtag   first hashtag
--by author     creator                                      --by location  country code
--by language   caption language
Themes with fewer than --min links (default 1) are grouped into _other.txt.

Usage:
    uv run scripts/tiktok/tiktok_dump.py videos.json                         # -> tiktok-dump.json + .csv
    uv run scripts/tiktok/tiktok_dump.py urls.txt -o cats --by category --min 5
    uv run scripts/tiktok/tiktok_dump.py videos.json --retry --workers 4
    uv run scripts/tiktok/tiktok_dump.py videos.json --all-columns           # CSV with every field too
    uv run --with gallery-dl gallery-dl -i batches/Pets.txt -d downloads/Pets   # download one theme later
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

VIDEO_RE = re.compile(r"/(?:share/)?video/(\d+)")
FRONT = ["url", "bookmark_id", "status", "video_id", "author", "nickname", "caption", "hashtags", "categories",
         "language", "location", "created_utc", "duration_s", "plays", "likes", "comments", "shares", "saves",
         "music", "author_followers", "author_verified", "author_bio"]


def load_inputs(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [(str(b["bookmark_id"]), b["link"]) for b in json.loads(text)]
    return [("", l.strip()) for l in text.splitlines() if l.strip().startswith("http")]


def fetch(url: str, tries: int = 3) -> dict:
    last = "unknown error"
    for n in range(tries):
        p = subprocess.run([sys.executable, "-m", "gallery_dl", "--dump-json", url],
                           capture_output=True, text=True, timeout=120)
        try:
            for kind, *rest in json.loads(p.stdout or "[]"):
                if kind == 2:
                    return rest[0]
        except (ValueError, TypeError):
            pass
        err = [l for l in p.stderr.splitlines() if "[error]" in l or "[warning]" in l]
        last = err[-1].split("] ", 1)[-1][:200] if err else "no metadata in output"
        if re.search(r"not available|not found|private|unavailable|removed|404", last, re.I):
            break
        time.sleep(2 * (n + 1))
    raise RuntimeError(last)


def flatten(o, prefix="", out=None):
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            flatten(v, f"{prefix}.{k}" if prefix else k, out)
    elif isinstance(o, list):
        if all(not isinstance(x, (dict, list)) for x in o):
            out[prefix] = "; ".join(str(x) for x in o)
        else:
            out[prefix] = json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    else:
        out[prefix] = "" if o is None else o
    return out


def convenience(rec: dict) -> dict:
    """The short, useful set of columns for one record."""
    m = rec.get("metadata") or {}
    a = m.get("author") if isinstance(m.get("author"), dict) else {}
    st, ast = m.get("stats") or {}, m.get("authorStats") or {}
    ts = m.get("createTime")
    return {
        "url": rec["url"], "bookmark_id": rec.get("bookmark_id", ""), "status": rec["status"],
        "video_id": m.get("id", ""),
        "author": a.get("uniqueId", ""), "nickname": a.get("nickname", ""),
        "caption": (m.get("desc") or "").replace("\n", " "),
        "hashtags": " ".join(t["hashtagName"] for t in m.get("textExtra") or [] if t.get("hashtagName")),
        "categories": "; ".join(m.get("diversificationLabels") or []),
        "language": m.get("textLanguage", ""), "location": m.get("locationCreated", ""),
        "created_utc": datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if str(ts).isdigit() else "",
        "duration_s": (m.get("video") or {}).get("duration", ""),
        "plays": st.get("playCount", ""), "likes": st.get("diggCount", ""), "comments": st.get("commentCount", ""),
        "shares": st.get("shareCount", ""), "saves": st.get("collectCount", ""),
        "music": (m.get("music") or {}).get("title", ""),
        "author_followers": ast.get("followerCount", ""), "author_verified": a.get("verified", ""),
        "author_bio": (a.get("signature") or "").replace("\n", " "),
    }


def theme_of(rec: dict, by: str) -> str:
    c = convenience(rec)
    m = rec.get("metadata") or {}
    value = {"category": c["categories"].split("; ")[0], "hashtag": c["hashtags"].split(" ")[0],
             "author": c["author"], "location": m.get("locationCreated", ""),
             "language": m.get("textLanguage", "")}[by]
    return value or "_unknown"


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|#\s]+', " ", name).strip()[:80] or "_unknown"


def write_outputs(recs: list, out: Path, all_columns: bool = False):
    out.with_suffix(".json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = []
    for r in recs:
        row = convenience(r)
        if all_columns:
            flat = flatten(r.get("metadata") or {})
            row.update({k: v for k, v in flat.items() if k not in row})
        rows.append(row)
    cols = FRONT + sorted({k for row in rows for k in row} - set(FRONT))
    with out.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(rows)
    return len(cols)


def write_batches(recs: list, by: str, min_n: int, folder: Path):
    groups = {}
    for r in recs:
        if r["status"] == "ok":
            groups.setdefault(theme_of(r, by), []).append(r["url"])
    other = [u for k, v in groups.items() if len(v) < min_n for u in v]
    kept = {k: v for k, v in groups.items() if len(v) >= min_n}
    if other:
        kept["_other"] = other
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "_index.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["theme", "count", "file"])
        for k, v in sorted(kept.items(), key=lambda kv: -len(kv[1])):
            fn = f"{safe(k)}.txt"
            (folder / fn).write_text("\n".join(v) + "\n", encoding="utf-8")
            w.writerow([k, len(v), fn])
    return len(kept)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("tiktok-dump"), help="base name for .json and .csv")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="fetch only this many new links (test run)")
    ap.add_argument("--retry", action="store_true", help="refetch links whose status is not ok")
    ap.add_argument("--all-columns", action="store_true", help="put every flattened metadata field in the CSV too")
    ap.add_argument("--by", choices=["category", "hashtag", "author", "location", "language"],
                    help="also write batches/<theme>.txt URL lists")
    ap.add_argument("--min", type=int, default=1, help="themes smaller than this go to _other")
    ap.add_argument("--batches", type=Path, default=Path("batches"), help="folder for the theme lists")
    a = ap.parse_args()

    jpath = a.output.with_suffix(".json")
    recs = {r["url"]: r for r in json.loads(jpath.read_text(encoding="utf-8"))} if jpath.exists() else {}
    todo, skipped = [], 0
    for bid, url in load_inputs(a.input):
        if not VIDEO_RE.search(url):
            skipped += 1
        elif url not in recs or (a.retry and recs[url]["status"] != "ok"):
            todo.append((bid, url))
    todo = todo[: a.limit] if a.limit else todo
    started = datetime.now()
    print(f"{len(todo)} to fetch, {len(recs)} already in {jpath}, {skipped} not video links (skipped)")

    errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(fetch, url): (bid, url) for bid, url in todo}
        for n, f in enumerate(as_completed(futs), 1):
            bid, url = futs[f]
            try:
                recs[url] = {"url": url, "bookmark_id": bid, "status": "ok", "metadata": f.result()}
            except Exception as e:  # noqa: BLE001 - record every failure, keep going
                errors.append((url, str(e)))
                recs[url] = {"url": url, "bookmark_id": bid, "status": f"error: {e}"[:150], "metadata": {}}
            if n % 50 == 0 or n == len(futs):
                write_outputs(list(recs.values()), a.output, a.all_columns)  # checkpoint, so an interrupted run keeps its work
                print(f"  {n}/{len(futs)} ({len(errors)} errors)")

    ncols = write_outputs(list(recs.values()), a.output, a.all_columns)
    nthemes = write_batches(list(recs.values()), a.by, a.min, a.batches) if a.by else 0
    finished = datetime.now()
    ok = sum(1 for r in recs.values() if r["status"] == "ok")
    new_ok = [url for _, url in todo if recs[url]["status"] == "ok"]
    warnings = []
    for url in new_ok:
        c = convenience(recs[url])
        for field, msg in (("caption", "no caption"), ("hashtags", "no hashtags"), ("categories", "no TikTok category")):
            if not c[field]:
                warnings.append(f"  {url}\n    {msg}")
    log = Path(f"results-log-{started:%Y-%m-%d_%H%M%S}.txt")
    lines = [
        "tiktok_dump results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} ({(finished - started).seconds}s)",
        f"Input       : {a.input}",
        f"Output      : {jpath}, {a.output.with_suffix('.csv')} ({ncols} CSV columns{', all fields' if a.all_columns else ''})",
        f"Batches     : {a.batches} by {a.by}, {nthemes} themes (min {a.min})" if a.by else "Batches     : (none)",
        "",
        "SUMMARY",
        f"  Links in output              : {len(recs)}",
        f"  Metadata fetched this run    : {len(new_ok)}",
        f"  Already in output (skipped)  : {len(recs) - len(todo)}",
        f"  Not video links (skipped)    : {skipped}",
        f"  Errors this run              : {len(errors)}",
        f"  Metadata ok in total         : {ok}",
        "",
        f"FETCHED ({len(new_ok)})",
    ]
    for url in new_ok:
        c = convenience(recs[url])
        lines.append(f"  {url}\n    @{c['author']} | {c['categories'] or 'no category'} | {c['hashtags'][:60]}")
    lines += ["  (none)"] if not new_ok else []
    failed = [(u, r["status"].removeprefix("error: ")) for u, r in recs.items() if r["status"] != "ok"]
    lines += ["", f"ERRORS: NO METADATA, INCLUDING EARLIER RUNS ({len(failed)})"] + ([f"  {u}\n    {e}" for u, e in failed] or ["  (none)"])
    lines += ["", f"WARNINGS ({len(warnings)})"] + (warnings or ["  (none)"])
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {jpath} and {a.output.with_suffix('.csv')} ({ncols} columns); {ok}/{len(recs)} ok; log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
