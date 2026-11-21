#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
sitemap_images.py - Match page URLs to their <image:image> URLs from a sitemap (Shopify style).

What it does:
- Reads a sitemap (a URL or a local .xml file) with <url><loc> entries that carry
  <image:image><image:loc> children (the Google image sitemap extension).
- Reads your list of page URLs (one per line, # comments ok; the two XML namespace
  URLs are skipped on purpose) and matches each to its sitemap entry.
- Writes a CSV: page_url, title, image_url, lastmod. Image URLs are kept exactly as in
  the sitemap (the ?v= cache-busting suffix may be cut off by the sitemap itself).
- Pages in the sitemap that are not in your list are reported as warnings.
- Writes results-log-{timestamp}.txt in the current folder every run: summary, written,
  skipped on purpose, errors, warnings.

Usage:
    uv run scripts/web/sitemap_images.py --sitemap "https://www.inspiraggio.com/sitemap_collections_1.xml?from=608917193035&to=647521698123" --urls urls.txt
    uv run scripts/web/sitemap_images.py --sitemap collections.xml --urls urls.txt --output matched.csv
"""

import argparse
import csv
import sys
import urllib.request as ur
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "i": "http://www.google.com/schemas/sitemap-image/1.1"}
UA = "Mozilla/5.0 (sitemap-images helper)"


def load(src):
    if src.startswith("http"):
        with ur.urlopen(ur.Request(src, headers={"User-Agent": UA}), timeout=40) as r:
            return r.read()
    return Path(src).read_bytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap", required=True)
    ap.add_argument("--urls", required=True)
    ap.add_argument("--output", default="sitemap-images.csv")
    a = ap.parse_args()
    start = datetime.now()
    ok, skipped, errors, warnings = [], [], [], []

    entries = {}
    try:
        root = ET.fromstring(load(a.sitemap))
        for u in root.findall("s:url", NS):
            loc = u.findtext("s:loc", "", NS).strip()
            imgs = [(im.findtext("i:loc", "", NS).strip(), im.findtext("i:title", "", NS).strip())
                    for im in u.findall("i:image", NS)]
            entries[loc] = (u.findtext("s:lastmod", "", NS), imgs)
    except Exception as e:
        errors.append((a.sitemap, f"cannot read sitemap: {e}"))

    wanted = [l.strip() for l in Path(a.urls).read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    rows = []
    for url in wanted:
        if "/schemas/" in url:
            skipped.append((url, "XML namespace, not a page"))
            continue
        e = entries.get(url)
        if not e:
            errors.append((url, "not found in sitemap"))
            continue
        lastmod, imgs = e
        if not imgs:
            warnings.append((url, "in sitemap but has no image"))
            continue
        for img, title in imgs:
            rows.append([url, title, img, lastmod])
            ok.append((url, f"{title} -> {img}"))
    for loc in entries:
        if loc not in wanted:
            warnings.append((loc, "in sitemap but not in your list"))

    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["page_url", "title", "image_url", "lastmod"])
        w.writerows(rows)

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(t, r):
        return "\n".join([f"{t} ({len(r)})"] + ([f"  {x}\n    {d}" for x, d in r] or ["  (none)"]))

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}", f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {a.sitemap} + {a.urls}", f"Output      : {a.output}", "", "SUMMARY",
        f"  total in your list : {len(wanted)}", f"  done this run      : {len(ok)}",
        "  already done       : 0", f"  skipped on purpose : {len(skipped)}", f"  errors             : {len(errors)}", "",
        block("SUCCESSFUL: WRITTEN", ok), "", block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", []), "",
        block("SKIPPED ON PURPOSE: XML namespaces", skipped), "", block("ERRORS", errors), "",
        block("WARNINGS", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} matched, {len(skipped)} skipped, {len(errors)} errors, {len(warnings)} warnings\nCSV: {a.output}\nLog: {log.resolve()}")


if __name__ == "__main__":
    sys.exit(main())
