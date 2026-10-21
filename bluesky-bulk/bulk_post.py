# /// script
# requires-python = ">=3.10"
# dependencies = ["atproto>=0.0.73", "httpx"]
# ///
"""Bulk-post to Bluesky from a CSV.

Columns: text (required; [label](https://...) and bare URLs become links), post_at (optional, ISO 8601 UTC), image_url
(optional), image_alt (optional), posted (filled in by this script).
Rows with a future post_at are skipped; re-run later to send them.

Env: BSKY_HANDLE, BSKY_APP_PASSWORD (create one under Settings > Privacy and security > App passwords).
"""
import argparse, csv, os, re, sys, time
from datetime import datetime, timezone

import httpx
from atproto import Client, client_utils

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)|(https?://[^\s]+)")
FIELDS = ["text", "post_at", "image_url", "image_alt", "posted"]


def build_text(text: str) -> client_utils.TextBuilder:
    tb, pos = client_utils.TextBuilder(), 0
    for m in LINK_RE.finditer(text):
        label, url = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(3))
        tb.text(text[pos:m.start()]).link(label, url)
        pos = m.end()
    return tb.text(text[pos:])


def due(row: dict, now: datetime) -> bool:
    if row.get("posted"):
        return False
    when = (row.get("post_at") or "").strip()
    return not when or datetime.fromisoformat(when.replace("Z", "+00:00")) <= now


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between posts")
    args = ap.parse_args()

    with open(args.csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    now = datetime.now(timezone.utc)
    todo = [r for r in rows if due(r, now)]
    for r in todo:
        shown = build_text(r["text"]).build_text()
        if not shown.strip() or len(shown) > 300:
            sys.exit(f"Bad text (empty or >300 chars): {shown[:40]!r}")
    print(f"{len(todo)} of {len(rows)} rows due")
    if args.dry_run:
        for r in todo:
            print("-", r["text"][:70], "[image]" if r.get("image_url") else "")
        return

    client = Client()
    client.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
    for r in todo:
        text = build_text(r["text"])
        if r.get("image_url"):
            img = httpx.get(r["image_url"], follow_redirects=True, timeout=30)
            img.raise_for_status()
            client.send_image(text, image=img.content, image_alt=r.get("image_alt") or "")
        else:
            client.send_post(text)
        r["posted"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(args.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print("posted:", r["text"][:60])
        time.sleep(args.delay)


if __name__ == "__main__":
    main()
