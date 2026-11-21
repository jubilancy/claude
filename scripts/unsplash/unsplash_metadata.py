#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
unsplash_metadata.py - Unsplash photo URLs or IDs -> CSV of metadata (title, description, photographer, tags, image URLs ...).

What it does:
- Reads Unsplash photo URLs (or bare IDs), one per line, "#" comments ok. The ID is taken from
  .../photos/<id>... so /download?force=true links work; no download is triggered.
- Calls the official API, GET https://api.unsplash.com/photos/<id>, with the access key from the
  UNSPLASH_ACCESS_KEY environment variable (header "Authorization: Client-ID <key>"). The key
  is never printed or written to the log.
- Writes one CSV row per photo: id, source_url (the photo page), title (the description, else
  the alt text), description, alt_description, photographer, photographer_username,
  photographer_url, portfolio_url, tags, topics (topic_submissions, when the API returns it),
  image_raw/full/regular/small/thumb, download_link, width, height, color, created_at,
  updated_at, downloads, likes, public_domain, location (name, city, country, lat, lon),
  camera (make, model, exposure, aperture, focal length, ISO), license_url.
  The photo response documents tags but no "categories" field; topics is the closest.
- Skips IDs already in the output CSV BEFORE making any request (use --force to redo them).
  Duplicate IDs in the input are skipped on purpose.
- Stops cleanly when the hourly rate limit is used up (demo apps get 50 requests per hour) and
  lists the rest as not done, so a later run continues where this one stopped.
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    UNSPLASH_ACCESS_KEY is read from the environment (add it in the cloud environment settings).
    uv run scripts/unsplash/unsplash_metadata.py --input scripts/unsplash/urls.txt --output data/unsplash-metadata.csv
    uv run scripts/unsplash/unsplash_metadata.py --input urls.txt --force
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request as ur
from datetime import datetime
from pathlib import Path

API = "https://api.unsplash.com/photos/"
UA = "unsplash-metadata/1.0 (personal catalogue tooling)"
LICENSE_URL = "https://unsplash.com/license"
COLS = ["id", "source_url", "title", "description", "alt_description", "photographer", "photographer_username",
        "photographer_url", "portfolio_url", "tags", "topics", "image_raw", "image_full", "image_regular",
        "image_small", "image_thumb", "download_link", "width", "height", "color", "created_at", "updated_at",
        "downloads", "likes", "public_domain", "location", "latitude", "longitude", "camera", "exposure",
        "aperture", "focal_length", "iso", "license_url"]
ID_RE = re.compile(r"/photos/([A-Za-z0-9_-]+)")


class RateLimited(Exception):
    pass


def photo_id(line):
    m = ID_RE.search(line)
    if m:
        return m.group(1)
    return line if re.fullmatch(r"[A-Za-z0-9_-]{6,}", line) else None


def fetch(pid, key):
    req = ur.Request(API + pid, headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1", "User-Agent": UA})
    try:
        with ur.urlopen(req, timeout=40) as r:
            return json.load(r), r.headers.get("X-Ratelimit-Remaining")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and "rate" in (e.read().decode("utf-8", "ignore") + str(e.headers)).lower():
            raise RateLimited()
        raise


def row(p):
    g = lambda d, *ks: (d or {}).get(ks[0]) if len(ks) == 1 else g((d or {}).get(ks[0]) or {}, *ks[1:])
    u, links, user = p.get("urls") or {}, p.get("links") or {}, p.get("user") or {}
    loc, exif = p.get("location") or {}, p.get("exif") or {}
    topics = p.get("topic_submissions") or {}
    return [p.get("id"), links.get("html", ""), p.get("description") or p.get("alt_description") or "",
            p.get("description") or "", p.get("alt_description") or "", user.get("name", ""), user.get("username", ""),
            (user.get("links") or {}).get("html", ""), user.get("portfolio_url") or "",
            ", ".join(t.get("title", "") for t in p.get("tags") or []), ", ".join(topics.keys()) if isinstance(topics, dict) else "",
            u.get("raw", ""), u.get("full", ""), u.get("regular", ""), u.get("small", ""), u.get("thumb", ""),
            links.get("download", ""), p.get("width", ""), p.get("height", ""), p.get("color", ""),
            p.get("created_at", ""), p.get("updated_at", ""), p.get("downloads", ""), p.get("likes", ""),
            p.get("public_domain", ""), loc.get("name") or ", ".join(x for x in (loc.get("city"), loc.get("country")) if x),
            g(loc, "position", "latitude") or "", g(loc, "position", "longitude") or "",
            exif.get("name") or " ".join(x for x in (exif.get("make"), exif.get("model")) if x), exif.get("exposure_time") or "",
            exif.get("aperture") or "", exif.get("focal_length") or "", exif.get("iso") or "", LICENSE_URL]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="unsplash-metadata.csv")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    start = datetime.now()
    ok, already, skipped, errors, warnings, notdone = [], [], [], [], [], []
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()

    lines = [l.strip() for l in Path(a.input).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    out = Path(a.output)
    done = set()
    if out.exists() and not a.force:
        with open(out, newline="", encoding="utf-8") as f:
            done = {r["id"] for r in csv.DictReader(f)}
    new_file = not out.exists() or a.force
    fh = open(out, "w" if new_file else "a", newline="", encoding="utf-8")
    w = csv.writer(fh)
    if new_file:
        w.writerow(COLS)

    if not key:
        errors.append(("UNSPLASH_ACCESS_KEY", "not set in this session's environment; nothing was requested"))
    seen, stop = set(), not key
    for line in lines:
        pid = photo_id(line)
        if not pid:
            errors.append((line[:80], "no photo ID found"))
            continue
        if pid in seen:
            skipped.append((pid, "duplicate ID in input"))
            continue
        seen.add(pid)
        if pid in done:
            already.append((pid, "already in output"))
            continue
        if stop:
            notdone.append((pid, "not requested (no key or rate limit reached)"))
            continue
        try:
            p, remaining = fetch(pid, key)
            w.writerow(row(p))
            fh.flush()
            ok.append((pid, (p.get("description") or p.get("alt_description") or "(no description)")[:80]))
            if not (p.get("description") or p.get("alt_description")):
                warnings.append((pid, "photo has no description or alt text"))
            if remaining is not None and remaining.isdigit() and int(remaining) == 0:
                stop = True
                warnings.append((pid, "rate limit used up; remaining IDs left for the next run"))
            time.sleep(0.5)
        except RateLimited:
            stop = True
            notdone.append((pid, "rate limit reached"))
        except Exception as e:  # one failed photo never stops the run
            errors.append((pid, str(e)[:200]))
    fh.close()

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(t, r):
        return "\n".join([f"{t} ({len(r)})"] + ([f"  {x}\n    {d}" for x, d in r] or ["  (none)"]))

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}", f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {a.input}", f"Output      : {a.output}", "", "SUMMARY", f"  total in input     : {len(lines)}",
        f"  done this run      : {len(ok)}", f"  already done       : {len(already)}", f"  skipped on purpose : {len(skipped)}",
        f"  errors             : {len(errors)}", f"  not done (limit)   : {len(notdone)}", "", block("SUCCESSFUL: WRITTEN", ok), "",
        block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", already), "", block("SKIPPED ON PURPOSE: duplicate IDs", skipped), "",
        block("NOT DONE: no key or rate limit", notdone), "", block("ERRORS", errors), "", block("WARNINGS", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} written, {len(already)} already done, {len(errors)} errors, {len(notdone)} not done\nCSV: {a.output}\nLog: {log.resolve()}")
    return 1 if errors and not ok and not already else 0


if __name__ == "__main__":
    sys.exit(main())
