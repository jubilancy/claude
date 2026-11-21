#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
shopify_new_products.py - List a Shopify store's products and pick out the ones not seen before.

What it does:
- Reads the store's public /products.json feed (newest first, paged, 250 per page).
- Compares each product's handle with a "seen" file (one handle per line, or the handle
  column of an earlier CSV) and writes only the new ones. With no seen file, everything is new.
- Each row has: detected_at, status, title, url, handle, created_at, product_type, min_price,
  art_image_url, art_confidence, tags. The artwork image is the flat painting, found with the
  same rule as shopify_collection_products.py (image 2 on canvas products unless it looks
  like a mockup).
- --status sets the label in the status column ("new" for alerts, "seed" for the first load).
- Pauses between pages, backs off on HTTP 429/503, sends a descriptive User-Agent.
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/web/shopify_new_products.py --store https://www.inspiraggio.com --status seed --output seed.csv
    uv run scripts/web/shopify_new_products.py --store https://www.inspiraggio.com --seen seen.txt --output new.csv
    uv run scripts/web/shopify_new_products.py --store https://www.inspiraggio.com --seen alerts.csv --seen-column handle
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shopify_collection_products import find_art, get_json  # noqa: E402

COLS = ["detected_at", "status", "title", "url", "handle", "created_at", "product_type",
        "min_price", "art_image_url", "art_confidence", "tags"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, help="e.g. https://www.inspiraggio.com")
    ap.add_argument("--seen", help="text file of handles, or a CSV (see --seen-column)")
    ap.add_argument("--seen-column", default="handle")
    ap.add_argument("--status", default="new")
    ap.add_argument("--output", default="new-products.csv")
    a = ap.parse_args()
    start = datetime.now()
    ok, already, errors, warnings = [], [], [], []
    store = a.store.rstrip("/")

    seen = set()
    if a.seen and Path(a.seen).exists():
        text = Path(a.seen).read_text(encoding="utf-8")
        if a.seen.endswith(".csv"):
            import io
            seen = {r[a.seen_column] for r in csv.DictReader(io.StringIO(text))}
        else:
            seen = {l.strip() for l in text.splitlines() if l.strip()}

    products, page = [], 1
    try:
        while True:
            batch = get_json(f"{store}/products.json?limit=250&page={page}").get("products", [])
            products += batch
            time.sleep(1.0)
            if len(batch) < 250:
                break
            page += 1
    except Exception as e:
        errors.append((f"{store}/products.json page {page}", str(e)[:200]))

    stamp = start.strftime("%Y-%m-%d %H:%M")
    rows = []
    for p in products:
        if p["handle"] in seen:
            already.append((p["handle"], "already seen"))
            continue
        art = find_art(p)
        if art[2] == "none":
            warnings.append((p["title"], "no artwork image found"))
        prices = [float(v["price"]) for v in p.get("variants", []) if v.get("price")]
        rows.append([stamp, a.status, p["title"], f"{store}/products/{p['handle']}", p["handle"],
                     p["created_at"][:10], p.get("product_type", ""), min(prices) if prices else "",
                     art[0], art[2], ", ".join(p.get("tags", []))])
        ok.append((p["handle"], p["title"]))
    rows.sort(key=lambda r: r[5], reverse=True)  # newest first

    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(t, r):
        return "\n".join([f"{t} ({len(r)})"] + ([f"  {x}\n    {d}" for x, d in r] or ["  (none)"]))

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}", f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {store}/products.json (seen file: {a.seen or 'none'})", f"Output      : {a.output}", "",
        "SUMMARY", f"  total products     : {len(products)}", f"  done this run (new): {len(ok)}",
        f"  already done       : {len(already)}", "  skipped on purpose : 0", f"  errors             : {len(errors)}", "",
        block("SUCCESSFUL: WRITTEN", ok), "", block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", already), "",
        block("SKIPPED ON PURPOSE", []), "", block("ERRORS", errors), "", block("WARNINGS", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} new, {len(already)} already seen, {len(errors)} errors\nCSV: {a.output}\nLog: {log.resolve()}")


if __name__ == "__main__":
    sys.exit(main())
