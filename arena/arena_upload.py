# /// script
# requires-python = ">=3.10"
# ///
"""Upload a pins_to_csv.py CSV to an Are.na channel, one block per row.

ARENA_TOKEN=... uv run arena/arena_upload.py pins.csv --channel your-channel-slug
Add --dry-run to print what would be sent. Re-running skips rows already uploaded.
The token needs write scope.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.are.na/v3/blocks"
FIELDS = ("value", "title", "description", "original_source_url", "original_source_title", "alt_text")


def post(token, payload):
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    while True:
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise RuntimeError(f"{e.code}: {e.read().decode()[:300]}") from None
            reset = e.headers.get("X-RateLimit-Reset")
            wait = max(int(reset) - time.time(), 1) if reset and reset.isdigit() else 60
            print(f"rate limited, waiting {wait:.0f}s", file=sys.stderr)
            time.sleep(wait + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--channel", required=True, help="channel slug or id")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    token = os.environ.get("ARENA_TOKEN")
    if not token and not a.dry_run:
        sys.exit("set ARENA_TOKEN")

    with open(a.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    state = a.csv + ".uploaded"  # one image URL per line, so a re-run resumes
    done = set(open(state, encoding="utf-8").read().split()) if os.path.exists(state) else set()

    sent = 0
    for i, r in enumerate(rows, 1):
        if r["value"] in done:
            continue
        payload = {k: r[k] for k in FIELDS if r.get(k)}
        payload["channel_ids"] = [a.channel]
        if a.dry_run:
            print(i, json.dumps(payload, ensure_ascii=False)[:160])
            continue
        res = post(token, payload)
        with open(state, "a", encoding="utf-8") as f:
            f.write(r["value"] + "\n")
        sent += 1
        print(f"{i}/{len(rows)} block {res.get('id')} {r.get('title', '')[:50]}")
        time.sleep(a.delay)
    print(f"done: {sent} uploaded, {len(done)} already uploaded earlier" if not a.dry_run else "dry run only")


if __name__ == "__main__":
    main()
