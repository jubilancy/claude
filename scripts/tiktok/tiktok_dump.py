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
  <out>.csv    one row per link, TikTok URL in the first column, then every metadata field flattened
               to its own column (nested keys joined with dots, lists joined with "; ").
               Convenience columns come right after the URL: bookmark_id, status, author, hashtags,
               categories (TikTok's diversificationLabels), caption, created_utc.
  batches/     with --by THEME: one <theme>.txt per theme, one URL per line, plus batches/_index.csv.
               Download a theme later with:  gallery-dl -i batches/<theme>.txt -d downloads/<theme>

Input is a text file of URLs (one per line) or a JSON dump of Raindrop bookmarks (see
scripts/raindrop/extract_bookmarks.py). Profile links are skipped (gallery-dl would fetch a whole account).
Reruns resume: links already in <out>.json are not fetched again; failed ones are retried with --retry.
Every run writes dump-log-{timestamp}.txt.

--by category   first TikTok category label of each video   --by hashtag   first hashtag
--by author     creator                                      --by location  country code
--by language   caption language
Themes with fewer than --min links (default 1) are grouped into _other.txt.

Usage:
    uv run scripts/tiktok/tiktok_dump.py videos.json                         # -> tiktok-dump.json + .csv
    uv run scripts/tiktok/tiktok_dump.py urls.txt -o cats --by category --min 5
    uv run scripts/tiktok/tiktok_dump.py videos.json --retry --workers 4
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
FRONT = ["url", "bookmark_id", "status", "author", "hashtags", "categories", "caption", "created_utc"]


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
    m = rec.get("metadata") or {}
    a = m.get("author") if isinstance(m.get("author"), dict) else {}
    ts = m.get("createTime")
    return {
        "url": rec["url"], "bookmark_id": rec.get("bookmark_id", ""), "status": rec["status"],
        "author": a.get("uniqueId", ""),
        "hashtags": " ".join(t["hashtagName"] for t in m.get("textExtra") or [] if t.get("hashtagName")),
        "categories": "; ".join(m.get("diversificationLabels") or []),
        "caption": (m.get("desc") or "").replace("\n", " "),
        "created_utc": datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if str(ts).isdigit() else "",
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


def write_outputs(recs: list, out: Path):
    out.with_suffix(".json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = []
    for r in recs:
        row = convenience(r)
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
                write_outputs(list(recs.values()), a.output)  # checkpoint, so an interrupted run keeps its work
                print(f"  {n}/{len(futs)} ({len(errors)} errors)")

    ncols = write_outputs(list(recs.values()), a.output)
    nthemes = write_batches(list(recs.values()), a.by, a.min, a.batches) if a.by else 0
    ok = sum(1 for r in recs.values() if r["status"] == "ok")
    log = Path(f"dump-log-{started:%Y-%m-%d_%H%M%S}.txt")
    lines = ["tiktok_dump results log", f"Run started : {started:%Y-%m-%d %H:%M:%S}", f"Input       : {a.input}",
             f"Output      : {jpath}, {a.output.with_suffix('.csv')} ({ncols} columns)",
             f"Batches     : {a.batches if a.by else '(none)'}" + (f" by {a.by}, {nthemes} themes" if a.by else ""), "",
             "SUMMARY", f"  Links in output : {len(recs)}", f"  Metadata ok     : {ok}",
             f"  Errors this run : {len(errors)}", f"  Not videos      : {skipped}", "", f"ERRORS ({len(errors)})"]
    lines += [f"  {u}\n    {e}" for u, e in errors] or ["  (none)"]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {jpath} and {a.output.with_suffix('.csv')} ({ncols} columns); {ok}/{len(recs)} ok; log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
