#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
shopify_collection_products.py - For each Shopify collection URL, list its products with title and image URLs.

What it does:
- Reads collection URLs from a CSV (column `page_url`, as written by sitemap_images.py) or a
  plain text file (one URL per line, # comments ok).
- Reads each collection's public /products.json feed (paged, 250 per page), so every product
  in the collection is matched to that collection, with its title, product URL, type, price,
  featured image and (with --all-images) every image.
- Skips collections already present in the output CSV BEFORE making any request
  (use --force to redo them). Writes after each collection, so an interrupted run keeps its work.
- Finds the artwork image: the flat reproduction of the painting, not a product mockup.
  Shopify has no alt text or flag for it, so this uses the store's own convention:
  the artwork is image position 2 on canvas products, unless that file is named like a
  mockup (ArtPrint*, Detail*, *-v5c, Smartist*, ...), in which case the first non-mockup
  image is used. `art_confidence` says which rule fired (high / medium / none; phone cases
  have no flat artwork image, so they are left blank).
- Backs off on HTTP 429/503 (honors Retry-After) and sends a descriptive User-Agent.
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/web/shopify_collection_products.py --input data/inspiraggio-collection-images.csv --output data/inspiraggio-products.csv
    uv run scripts/web/shopify_collection_products.py --input urls.txt --all-images
    uv run scripts/web/shopify_collection_products.py --input urls.txt --force
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request as ur
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

UA = "Claude-Code-agent (read-only catalog matching)"
DELAY = 1.0
COLS = ["collection_url", "collection_title", "position", "product_title", "product_url", "handle",
        "product_type", "min_price", "image_count", "image_url", "art_image_url", "art_image_position", "art_confidence"]

MOCKUP = re.compile(
    r"^(art[-_ ]?print|detail|decorated|front|smartist|mockup|layer|comfy|feature_wall|stylish|"
    r"art_gallery|clean-and-simple|detalles?_|copy)|-v5c|^\d+_[0-9a-f-]{20,}\.", re.I)


def find_art(product):
    """Return (url, position, confidence) of the artwork image, or ('', '', reason)."""
    if product.get("product_type") != "Canvas":
        return "", "", "n/a (no flat artwork image)"
    imgs = product.get("images", [])
    name = lambda i: i["src"].rsplit("/", 1)[1]
    if len(imgs) > 1 and not MOCKUP.search(name(imgs[1])):
        return imgs[1]["src"], 2, "high"
    for i in imgs:
        if not MOCKUP.search(name(i)):
            return i["src"], i["position"], "medium"
    return "", "", "none"


def get_json(url, retries=5):
    wait = 5.0
    for n in range(retries + 1):
        try:
            with ur.urlopen(ur.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and n < retries:
                ra = e.headers.get("Retry-After", "")
                time.sleep(float(ra) if ra.isdigit() else wait)
                wait *= 2
                continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="collection-products.csv")
    ap.add_argument("--all-images", action="store_true", help="one row per image instead of per product")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    start = datetime.now()
    ok, already, skipped, errors, warnings = [], [], [], [], []

    inp = Path(a.input)
    if inp.suffix == ".csv":
        with open(inp, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        titles = {r["page_url"]: r.get("title", "") for r in rows}
        urls = list(titles)
    else:
        urls = [l.strip() for l in inp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        titles = {}

    out = Path(a.output)
    done = set()
    if out.exists() and not a.force:
        with open(out, newline="", encoding="utf-8") as f:
            done = {r["collection_url"] for r in csv.DictReader(f)}
    new_file = not out.exists() or a.force
    fh = open(out, "w" if new_file else "a", newline="", encoding="utf-8")
    w = csv.writer(fh)
    if new_file:
        w.writerow(COLS)

    for url in urls:
        if url in done:
            already.append((url, "already in output"))
            continue
        parts = urlsplit(url)
        if "/collections/" not in parts.path:
            skipped.append((url, "not a /collections/ URL"))
            continue
        base = f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"
        try:
            products, page = [], 1
            while True:
                data = get_json(f"{base}/products.json?limit=250&page={page}")
                batch = data.get("products", [])
                products += batch
                time.sleep(DELAY)
                if len(batch) < 250:
                    break
                page += 1
            if not products:
                warnings.append((url, "collection has no products"))
                w.writerow([url, titles.get(url, ""), "", "", "", "", "", "", "", "", "", "", ""])
                fh.flush()
                continue
            for pos, p in enumerate(products, 1):
                imgs = [i["src"] for i in p.get("images", [])]
                prices = [float(v["price"]) for v in p.get("variants", []) if v.get("price")]
                common = [url, titles.get(url, ""), pos, p["title"], f"{parts.scheme}://{parts.netloc}/products/{p['handle']}",
                          p["handle"], p.get("product_type", ""), min(prices) if prices else "", len(imgs)]
                art = find_art(p)
                if art[2] == "none":
                    warnings.append((p["title"], f"no artwork image found ({url})"))
                if not imgs:
                    warnings.append((p["title"], f"no image ({url})"))
                for src in (imgs if a.all_images else imgs[:1]) or [""]:
                    w.writerow(common + [src, *art])
            fh.flush()
            ok.append((url, f"{len(products)} products"))
        except Exception as e:  # one failed collection never stops the run
            errors.append((url, str(e)[:200]))
    fh.close()

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(t, r):
        return "\n".join([f"{t} ({len(r)})"] + ([f"  {x}\n    {d}" for x, d in r] or ["  (none)"]))

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}", f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {a.input}", f"Output      : {a.output}", "", "SUMMARY", f"  total collections  : {len(urls)}",
        f"  done this run      : {len(ok)}", f"  already done       : {len(already)}", f"  skipped on purpose : {len(skipped)}",
        f"  errors             : {len(errors)}", "", block("SUCCESSFUL: WRITTEN", ok), "",
        block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", already), "", block("SKIPPED ON PURPOSE: not a collection URL", skipped), "",
        block("ERRORS", errors), "", block("WARNINGS", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} collections done, {len(already)} already done, {len(errors)} errors\nCSV: {a.output}\nLog: {log.resolve()}")


if __name__ == "__main__":
    sys.exit(main())
