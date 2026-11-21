#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
superstock_curated_csv.py - Turn a curated SuperStock SKU list into a CSV with checked preview images.

What it does:
- Reads a pipe-separated seeds file (theme | group | sku | title | supplier | collection |
  license | width | height; "#" lines are comments), as written in curated-seeds.txt.
- Builds each picture's page link and its thumbnail and preview (watermarked comp) image URLs
  from the SKU: https://www.superstock.com/cdn/{prefix}/Thumb/{sku}.webp and .../Comp/{sku}.webp.
- Checks every thumbnail and preview URL over HTTP (must answer 200 with an image type) and
  records the result per row. Rows whose images do not resolve are still written, flagged.
- Skips SKUs already in the output CSV BEFORE making any request (use --force to redo).
  Duplicate SKUs inside the seeds file are skipped on purpose.
- Writes the CSV after every row, so an interrupted run keeps its work.
- Writes results-log-{timestamp}.txt in the current folder every run.

Preview and thumbnail images are watermarked comps for browsing and layout review only.
Final use of a picture needs a licence from SuperStock.

Usage:
    uv run scripts/superstock/superstock_curated_csv.py --input scripts/superstock/curated-seeds.txt --output data/superstock-curated.csv
    uv run scripts/superstock/superstock_curated_csv.py --input seeds.txt --force
"""

import argparse
import csv
import sys
import time
import urllib.request as ur
from datetime import datetime
from pathlib import Path

UA = "Mozilla/5.0 (curated-list link check)"
COLS = ["theme", "group", "sku", "title", "supplier", "collection", "license", "width", "height",
        "orientation", "asset_url", "thumb_url", "preview_url", "thumb_ok", "preview_ok"]


def check(url):
    """Return 'ok' if the URL answers 200 with an image type, else a short reason."""
    try:
        with ur.urlopen(ur.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            ct = r.headers.get("Content-Type", "")
            return "ok" if r.status == 200 and ct.startswith("image/") else f"HTTP {r.status} {ct}"
    except Exception as e:
        return f"error: {str(e)[:80]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="superstock-curated.csv")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    start = datetime.now()
    ok, already, skipped, errors, warnings = [], [], [], [], []

    out = Path(a.output)
    done = set()
    if out.exists() and not a.force:
        with open(out, newline="", encoding="utf-8") as f:
            done = {r["sku"] for r in csv.DictReader(f)}
    new_file = not out.exists() or a.force
    fh = open(out, "w" if new_file else "a", newline="", encoding="utf-8")
    w = csv.writer(fh)
    if new_file:
        w.writerow(COLS)

    seen, total = set(), 0
    for line in Path(a.input).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        total += 1
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 9:
            errors.append((line[:80], f"expected 9 fields, got {len(parts)}"))
            continue
        theme, group, sku, title, supplier, coll, lic, width, height = parts
        if sku in seen:
            skipped.append((sku, "duplicate SKU in seeds file"))
            continue
        seen.add(sku)
        if sku in done:
            already.append((sku, "already in output"))
            continue
        prefix = sku.split("-")[0]
        base = f"https://www.superstock.com/cdn/{prefix}"
        thumb, prev = f"{base}/Thumb/{sku}.webp", f"{base}/Comp/{sku}.webp"
        t_ok, p_ok = check(thumb), check(prev)
        time.sleep(0.3)
        if t_ok != "ok" or p_ok != "ok":
            warnings.append((sku, f"thumb: {t_ok}; preview: {p_ok}"))
        try:
            w_i, h_i = int(width), int(height)
            orient = "square" if abs(w_i - h_i) / max(w_i, h_i) < 0.05 else ("landscape" if w_i > h_i else "portrait")
        except ValueError:
            orient = ""
        w.writerow([theme, group, sku, title, supplier, coll, lic, width, height, orient,
                    f"https://www.superstock.com/asset/{sku}", thumb, prev, t_ok, p_ok])
        fh.flush()
        ok.append((sku, f"{theme} / {group}: {title[:70]}"))
    fh.close()

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(t, r):
        return "\n".join([f"{t} ({len(r)})"] + ([f"  {x}\n    {d}" for x, d in r] or ["  (none)"]))

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}", f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {a.input}", f"Output      : {a.output}", "", "SUMMARY", f"  total seeds        : {total}",
        f"  done this run      : {len(ok)}", f"  already done       : {len(already)}", f"  skipped on purpose : {len(skipped)}",
        f"  errors             : {len(errors)}", "", block("SUCCESSFUL: WRITTEN", ok), "",
        block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", already), "", block("SKIPPED ON PURPOSE: duplicate SKUs", skipped), "",
        block("ERRORS", errors), "", block("WARNINGS (image links that did not resolve)", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} written, {len(already)} already done, {len(errors)} errors, {len(warnings)} image warnings\nCSV: {a.output}\nLog: {log.resolve()}")


if __name__ == "__main__":
    sys.exit(main())
