#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
csv_to_wp_posts.py - book_titles_cleaned.csv -> one WordPress.com post per row.

What it does:
- Reads the CSV (columns: book_title, author, id, url, cover_image, created,
  original_excerpt) and builds one post per row:
    title          = book_title
    featured image = the cover, uploaded to the site's media library
    body           = cover image, "by <author>" (placeholder when blank),
                     the original Pinterest description, and a small
                     lowercase "source" button linking to the Pinterest pin
    category       = book-cover (name or id, see --category)
    date           = the row's "created" value
    status         = draft (see --status)
- DRY RUN BY DEFAULT: builds every post and writes a preview file, but sends
  nothing. Add --live to upload and post. --live needs a WordPress.com OAuth
  token in the WPCOM_TOKEN environment variable.
- Skips rows already posted (their pin id is in the state file) BEFORE making
  any network request. A failure on one row never stops the run.
- Writes the state file (posted-ids CSV) as it goes, so an interrupted run
  can be resumed.
- Writes results-log-{timestamp}.txt in the current folder every run, with
  separate lists for written, skipped, and errors, plus warnings.

Usage:
    uv run scripts/wordpress/csv_to_wp_posts.py --input book_titles_cleaned.csv                 # dry run, 182 posts previewed
    uv run scripts/wordpress/csv_to_wp_posts.py --input book_titles_cleaned.csv --limit 3 --live # try 3 real drafts first
    uv run scripts/wordpress/csv_to_wp_posts.py --input book_titles_cleaned.csv --live          # post everything
    uv run scripts/wordpress/csv_to_wp_posts.py --input book_titles_cleaned.csv --site fromdaysoff.wordpress.com --status draft --live
"""

import argparse
import csv
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://public-api.wordpress.com/rest/v1.1"
PLACEHOLDER_AUTHOR = "author unknown"
STATE_COLUMNS = ["pin_id", "post_id", "post_url", "media_id", "status", "posted_at"]


class SkipRow(Exception):
    """Row skipped on purpose (e.g. no cover image)."""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def build_content(row: dict, image_url: str, image_id) -> str:
    title = row["book_title"].strip()
    author = row["author"].strip() or PLACEHOLDER_AUTHOR
    excerpt = row["original_excerpt"].strip()
    pin_url = row["url"].strip()
    id_attr = f' {{"id":{image_id},"sizeSlug":"large","linkDestination":"none"}}' if image_id else ' {"sizeSlug":"large","linkDestination":"none"}'
    img_class = f"wp-image-{image_id}" if image_id else ""
    parts = [
        f'<!-- wp:image{id_attr} -->\n'
        f'<figure class="wp-block-image size-large"><img src="{esc(image_url)}" alt="{esc(title)} by {esc(author)}"'
        + (f' class="{img_class}"' if img_class else "")
        + "/></figure>\n<!-- /wp:image -->",
        f"<!-- wp:paragraph -->\n<p>by {esc(author)}</p>\n<!-- /wp:paragraph -->",
    ]
    if excerpt:
        parts.append(f"<!-- wp:paragraph -->\n<p>{esc(excerpt)}</p>\n<!-- /wp:paragraph -->")
    if pin_url:
        parts.append(
            '<!-- wp:buttons -->\n<div class="wp-block-buttons">'
            '<!-- wp:button {"style":{"typography":{"fontSize":"0.8rem","textTransform":"lowercase"}}} -->\n'
            '<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" '
            f'href="{esc(pin_url)}" style="font-size:0.8rem;text-transform:lowercase">source</a></div>\n'
            "<!-- /wp:button --></div>\n<!-- /wp:buttons -->"
        )
    return "\n\n".join(parts)


def api_post(path: str, fields: list, token: str, retries: int = 4) -> dict:
    """POST form fields (list of (key, value)) and return the JSON response."""
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"{API}{path}", data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries:
                wait = int(e.headers.get("Retry-After", 0) or 0) or 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {e.code}: {body}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"network error: {e.reason}") from None


def process_row(row: dict, args, token) -> dict:
    title = row["book_title"].strip()
    cover = row["cover_image"].strip()
    if not title:
        raise SkipRow("no book_title")
    if not cover:
        raise SkipRow("no cover_image")
    warnings = []
    if not row["author"].strip():
        warnings.append(f'no author; used placeholder "{PLACEHOLDER_AUTHOR}"')

    fields_base = [("title", title), ("status", args.status), ("categories", args.category)]
    if row["created"].strip():
        fields_base.append(("date", row["created"].strip()))

    if not token:  # dry run
        return {
            "preview": {"fields": dict(fields_base), "content": build_content(row, cover, None), "cover": cover},
            "detail": "dry run", "warnings": warnings,
        }

    media = api_post(f"/sites/{args.site}/media/new", [("media_urls[]", cover)], token)
    if media.get("errors") or not media.get("media"):
        raise RuntimeError(f"image upload failed: {json.dumps(media.get('errors') or media)[:200]}")
    m = media["media"][0]
    media_id, media_url = m["ID"], m["URL"]
    post = api_post(
        f"/sites/{args.site}/posts/new",
        fields_base + [("content", build_content(row, media_url, media_id)), ("featured_image", str(media_id))],
        token,
    )
    if "ID" not in post:
        raise RuntimeError(f"post failed: {json.dumps(post)[:200]}")
    return {
        "state": {"pin_id": row["id"], "post_id": post["ID"], "post_url": post.get("URL", ""),
                  "media_id": media_id, "status": post.get("status", args.status),
                  "posted_at": datetime.now().isoformat(timespec="seconds")},
        "detail": f"post {post['ID']} ({post.get('status', args.status)})", "warnings": warnings,
    }


def write_results_log(log_path: Path, meta: dict, written, skipped_exists, skipped_other, errors, warnings) -> None:
    lines = [
        "csv_to_wp_posts results log",
        f"Run started : {meta['started']}",
        f"Run finished: {meta['finished']}  (duration {meta['duration']})",
        f"Input file  : {meta['input']}",
        f"Output file : {meta['output']}",
        f"Site        : {meta['site']}",
        f"Mode        : {meta['mode']}",
        f"Rows in file: {meta['total']}",
        f"Processed   : {meta['processed']}" + ("  (run was interrupted)" if meta["interrupted"] else ""),
        "",
        "SUMMARY",
        f"  Total rows                          : {meta['total']}",
        f"  Done this run                       : {len(written)}",
        f"  Already done (skipped)              : {len(skipped_exists)}",
        f"  Skipped on purpose                  : {len(skipped_other)}",
        f"  Errors                              : {len(errors)}",
        f"  Warnings                            : {len(warnings)}",
        "",
        f"SUCCESSFUL: {'WRITTEN' if meta['live'] else 'PREVIEWED (DRY RUN)'} ({len(written)})",
    ]
    lines += [f"  {k}\n    {d}" for k, d in written] or ["  (none)"]
    lines += ["", f"SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT ({len(skipped_exists)})"]
    lines += [f"  {k}" for k in skipped_exists] or ["  (none)"]
    lines += ["", f"SKIPPED ON PURPOSE: ROWS WITH NO TITLE OR COVER ({len(skipped_other)})"]
    lines += [f"  {k}\n    {d}" for k, d in skipped_other] or ["  (none)"]
    lines += ["", f"ERRORS ({len(errors)})"]
    lines += [f"  {k}\n    {d}" for k, d in errors] or ["  (none)"]
    lines += ["", f"WARNINGS ({len(warnings)})"]
    lines += [f"  {k}\n    {d}" for k, d in warnings] or ["  (none)"]
    lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="One WordPress.com post per CSV row (dry run unless --live).")
    ap.add_argument("--input", required=True, help="book_titles_cleaned.csv")
    ap.add_argument("--output", default="posted-ids.csv", help="state file of rows already posted (default posted-ids.csv)")
    ap.add_argument("--preview", default="posts-preview.jsonl", help="dry-run preview file (default posts-preview.jsonl)")
    ap.add_argument("--site", default="fromdaysoff.wordpress.com")
    ap.add_argument("--status", default="draft", choices=["draft", "publish", "private", "pending"])
    ap.add_argument("--category", default="book-cover", help="category name or id")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N rows not yet done")
    ap.add_argument("--live", action="store_true", help="really upload and post (needs WPCOM_TOKEN)")
    args = ap.parse_args()

    token = os.environ.get("WPCOM_TOKEN", "").strip() if args.live else ""
    if args.live and not token:
        print("--live needs the WPCOM_TOKEN environment variable.", file=sys.stderr)
        return 2

    with open(args.input, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    output_path = Path(args.output)
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8", newline="") as f:
            done = {r["pin_id"] for r in csv.DictReader(f)}

    started = datetime.now()
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    written, skipped_exists, skipped_other, errors, warnings = [], [], [], [], []
    processed, interrupted, attempted = 0, False, 0

    state_out = preview_out = writer = None
    if args.live:
        fresh = not output_path.exists() or output_path.stat().st_size == 0
        state_out = output_path.open("a", encoding="utf-8", newline="")
        writer = csv.DictWriter(state_out, STATE_COLUMNS)
        if fresh:
            writer.writeheader()
    else:
        preview_out = open(args.preview, "w", encoding="utf-8")

    print(f"{'LIVE' if args.live else 'DRY RUN'}: {len(rows)} row(s) -> {args.site}\n")
    try:
        for i, row in enumerate(rows, 1):
            key = f"{row.get('id', '?')}  {row.get('book_title', '')[:60]}"
            processed = i
            if row.get("id") in done:
                skipped_exists.append(key)
                continue
            if args.limit and attempted >= args.limit:
                processed = i - 1
                break
            attempted += 1
            print(f"[{i}/{len(rows)}] {key}")
            try:
                result = process_row(row, args, token)
                written.append((key, result["detail"]))
                warnings += [(key, w) for w in result["warnings"]]
                if args.live:
                    writer.writerow(result["state"])
                    state_out.flush()
                else:
                    preview_out.write(json.dumps({"pin_id": row["id"], **result["preview"]}, ensure_ascii=False) + "\n")
            except SkipRow as e:
                skipped_other.append((key, str(e)))
            except Exception as e:  # one bad row never stops the run
                errors.append((key, str(e)))
                print(f"  ERROR: {e}")
            if args.live:
                time.sleep(0.5)
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted; writing log.")
    finally:
        for fh in (state_out, preview_out):
            if fh:
                fh.close()
        finished = datetime.now()
        write_results_log(
            log_path,
            {"started": started.isoformat(sep=" ", timespec="seconds"),
             "finished": finished.isoformat(sep=" ", timespec="seconds"),
             "duration": str(finished - started).split(".")[0],
             "input": args.input, "output": args.output if args.live else args.preview,
             "site": args.site, "mode": f"LIVE, status={args.status}" if args.live else "DRY RUN (nothing sent)",
             "live": args.live, "total": len(rows), "processed": processed, "interrupted": interrupted},
            written, skipped_exists, skipped_other, errors, warnings,
        )
    print(f"\nDone: {len(written)} {'posted' if args.live else 'previewed'}, {len(skipped_exists)} already done, "
          f"{len(skipped_other)} skipped, {len(errors)} errors.\nLog: {log_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
