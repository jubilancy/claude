#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
ia_mediatype.py - archive.org /details/ URLs -> identifier + mediatype (item vs collection).

What it does:
- Reads archive.org URLs from urls.txt (one per line, # comments ok).
- Extracts the identifier from /details/<id> (extra path, query and #fragment are ignored).
- Asks the Metadata API for the item's mediatype (texts, movies, audio, collection, ...).
- Skips @user profile pages on purpose, and identifiers already in the output CSV
  (use --force to redo them).
- Sends the descriptive User-Agent that archive.org asks bots and LLMs for, waits between
  requests, retries on 429/503 and honors Retry-After.
- Writes results-log-{timestamp}.txt in the current folder every run: SUMMARY plus lists
  for written, skipped (already in output), skipped on purpose, errors and warnings.

Usage:
    uv run scripts/archive_org/ia_mediatype.py                      # ./urls.txt -> ./ia-mediatype.csv
    uv run scripts/archive_org/ia_mediatype.py --input links.txt --output out.csv
    uv run scripts/archive_org/ia_mediatype.py --force              # redo identifiers already in output
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request as ur
from datetime import datetime
from pathlib import Path

USER_AGENT = "ia-mediatype/1.0.0 (claude-sonnet-5-5)"
DELAY = 0.5
MAX_RETRIES = 5
BACKOFF = 5.0
COLUMNS = ["identifier", "mediatype", "input_url"]
DETAILS_RE = re.compile(r"archive\.org/details/([^/?#&]+)", re.I)


class SkipOnPurpose(Exception):
    pass


def identifier_of(url):
    m = DETAILS_RE.search(url)
    if not m:
        raise SkipOnPurpose("not an archive.org /details/ URL")
    ident = up.unquote(m.group(1))
    if ident.startswith("@"):
        raise SkipOnPurpose("user profile page, not an item")
    return ident


def fetch_mediatype(ident):
    api = f"https://archive.org/metadata/{up.quote(ident)}/metadata/mediatype"
    for attempt in range(MAX_RETRIES + 1):
        req = ur.Request(api, headers={"User-Agent": USER_AGENT})
        try:
            with ur.urlopen(req, timeout=30) as r:
                data = json.load(r)
            return data.get("result") or "NOT FOUND"
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < MAX_RETRIES:
                wait = float(e.headers.get("Retry-After") or BACKOFF * 2 ** attempt)
                time.sleep(min(wait, 120))
                continue
            raise
    raise RuntimeError("retries exhausted")


def read_done(path):
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["identifier"] for row in csv.DictReader(f)}


def section(title, rows):
    out = [f"{title} ({len(rows)})"]
    out += [x for pair in rows for x in (pair[0], f"    {pair[1]}")] if rows else ["  (none)"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="urls.txt")
    ap.add_argument("--output", default="ia-mediatype.csv")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    started = datetime.now()
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    inp, outp = Path(a.input), Path(a.output)
    written, already, purpose, errors, warnings = [], [], [], [], []
    urls = []
    try:
        urls = [l.strip() for l in inp.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    except OSError as e:
        errors.append((str(inp), f"cannot read input: {e}"))

    done = set() if a.force else read_done(outp)
    seen = set()
    new_file = not outp.exists() or a.force
    with outp.open("w" if a.force else "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(COLUMNS)
        for url in urls:
            try:
                ident = identifier_of(url)
                if ident in done or ident in seen:
                    already.append((url, f"identifier {ident} already handled"))
                    continue
                seen.add(ident)
                mt = fetch_mediatype(ident)
                w.writerow([ident, mt, url])
                f.flush()
                written.append((url, f"{ident} -> {mt}"))
                if mt == "NOT FOUND":
                    warnings.append((url, f"{ident}: no mediatype returned"))
                time.sleep(DELAY)
            except SkipOnPurpose as e:
                purpose.append((url, str(e)))
            except Exception as e:  # one failure never stops the run
                errors.append((url, f"{type(e).__name__}: {e}"))

    finished = datetime.now()
    lines = [
        "ia_mediatype results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} (duration {finished - started})",
        f"Input : {inp}", f"Output: {outp}", "",
        "SUMMARY",
        f"  Total URLs                 : {len(urls)}",
        f"  Done this run              : {len(written)}",
        f"  Already done (skipped)     : {len(already)}",
        f"  Skipped on purpose         : {len(purpose)}",
        f"  Errors                     : {len(errors)}", "",
    ]
    for title, rows in [("SUCCESSFUL: WRITTEN", written), ("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", already),
                        ("SKIPPED ON PURPOSE: profile or non-details URL", purpose),
                        ("ERRORS", errors), ("WARNINGS", warnings)]:
        lines += section(title, rows) + [""]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Done: {len(written)} written, {len(errors)} errors. Log: {log_path}")


if __name__ == "__main__":
    sys.exit(main())
