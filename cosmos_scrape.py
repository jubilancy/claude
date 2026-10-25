#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///

"""
Cosmos.so scraper
-----------------
Reads a text file of cosmos.so URLs (one per line), runs the matching in-page scraper
in headless Chromium, and writes JSON + CSV per URL to cosmos-output/. URLs whose output
already exists are skipped, so you can re-run the same file as you add lines.

    uv run cosmos_scrape.py                 # reads cosmos-urls.txt
    uv run cosmos_scrape.py my-links.txt    # or any file
    uv run cosmos_scrape.py --force         # re-scrape everything

URL file format (blank lines and # comments ignored):

    https://www.cosmos.so/e/556978292                   # element page -> every collection it is in
    https://www.cosmos.so/design/the-best-band-posters  # collection/brand/explore page -> its own elements
    https://www.cosmos.so/e/853905883 | grid            # force a mode: "| grid" or "| collections"

The scraping itself is cosmos-scraper.js (grid mode) and cosmos-collections.js (collections
mode), read from next to this file. They pull element data out of the React fibers behind
each tile, because the grid is virtualized and the tiles have no <a href>.

Chromium: uses /opt/pw-browsers/chromium if present (Claude Code cloud sessions), otherwise
Playwright's own browser: run `uv run --with playwright playwright install chromium` once.
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PRESET_CHROMIUM = Path("/opt/pw-browsers/chromium")


def slug_of(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path) or "cosmos"


def read_urls(path: Path) -> list[tuple[str, str | None]]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        url, _, hint = (p.strip() for p in line.partition("|"))
        if not url.startswith("http"):
            print(f"skip   not a URL: {line}")
            continue
        out.append((url, hint if hint in ("grid", "collections") else None))
    return out


def run_in_page(page, js_source: str):
    """Run a scraper script (an async IIFE) in the page and return (rows, summary)."""
    body = js_source.strip().rstrip(";")
    return page.evaluate(
        "async () => { const rows = await (" + body + ");"
        " return { rows, summary: window.__cosmosSummary || null }; }"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls_file", nargs="?", default="cosmos-urls.txt")
    ap.add_argument("--force", action="store_true", help="re-scrape URLs that already have output")
    ap.add_argument("--out", default="cosmos-output", help="output directory (default: cosmos-output)")
    args = ap.parse_args()

    urls_path = Path(args.urls_file)
    if not urls_path.exists():
        print(f"{urls_path} not found. Create it with one cosmos.so URL per line.", file=sys.stderr)
        return 1
    scripts = {
        "grid": (HERE / "cosmos-scraper.js").read_text(encoding="utf-8"),
        "collections": (HERE / "cosmos-collections.js").read_text(encoding="utf-8"),
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    done = skipped = failed = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=str(PRESET_CHROMIUM) if PRESET_CHROMIUM.exists() else None,
            args=["--no-sandbox"],
        )
        for url, hint in read_urls(urls_path):
            json_path = out_dir / f"{slug_of(url)}.json"
            if json_path.exists() and not args.force:
                print(f"skip   {url}  (already scraped)")
                skipped += 1
                continue
            mode = hint or ("collections" if urlparse(url).path.startswith("/e/") else "grid")
            print(f"run    {url}  [{mode}]")
            started = time.time()
            # Desktop viewport matters: Cosmos' phone layout does not render the tile grid.
            ctx = browser.new_context(viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            page.on("console", lambda m: print("       " + m.text) if m.text.startswith("[cosmos]") and "so far" not in m.text else None)
            try:
                page.goto(url, wait_until="networkidle", timeout=60_000)
                page.wait_for_timeout(2500)
                result = run_in_page(page, scripts[mode])
                rows = result["rows"]
                if not rows:
                    raise RuntimeError("0 elements found")
                json_path.write_text(json.dumps({
                    "source": url, "mode": mode,
                    "scrapedAt": datetime.now(timezone.utc).isoformat(),
                    "summary": result["summary"], "elements": rows,
                }, indent=2, ensure_ascii=False), encoding="utf-8")
                with open(json_path.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
                print(f"done   {len(rows)} elements in {round(time.time() - started)}s -> {json_path}")
                done += 1
            except Exception as err:  # keep going; failed URLs have no output so the next run retries them
                print(f"fail   {url}: {str(err).splitlines()[0][:160]}")
                failed += 1
            finally:
                ctx.close()
        browser.close()

    print(f"\n{done} scraped, {skipped} skipped, {failed} failed. Output in {out_dir}/")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
