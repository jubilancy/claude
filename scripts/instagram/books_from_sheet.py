#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
books_from_sheet.py - join a hand-checked list of book mentions to the saved-posts table.

What it does:
- Reads the saved-posts category CSV (one row per post, as uploaded to the
  Google Sheet) and a curated books CSV with the columns
  sheet_row, title, author, notes, mention_source.  sheet_row is the row
  number in the sheet (header = row 1, first post = row 2).
- Checks every curated title against the text of the post it points at
  (caption + hashtags, ignoring case, accents, punctuation and spacing).
  Titles it cannot find are listed under WARNINGS so a typo or a wrong row
  number shows up instead of passing silently.
- Writes books-mentioned.csv: one row per book with the post's link, owner,
  saved date, collections and caption next to it.
- Writes posts-without-books.csv: every post with NO extracted book (sheet
  row, link, owner), used to colour those rows in the sheet.
- Writes results-log-{timestamp}.txt in the current folder every run, with
  separate lists for written, skipped, and errors, plus warnings.

Usage:
    uv run scripts/instagram/books_from_sheet.py POSTS.csv BOOKS.csv
    uv run scripts/instagram/books_from_sheet.py POSTS.csv BOOKS.csv --outdir out
"""

import argparse
import csv
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


def norm(s):
    """Lowercase, strip accents/punctuation and collapse spaces for matching."""
    s = unicodedata.normalize("NFKD", s or "").casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser(description="Join curated book mentions to the saved-posts table")
    ap.add_argument("posts", help="category CSV (same rows/order as the sheet)")
    ap.add_argument("books", help="curated books CSV (sheet_row,title,author,notes,mention_source)")
    ap.add_argument("--outdir", default=".", help="folder for the output CSVs (default .)")
    args = ap.parse_args()

    started = datetime.now()
    outdir = Path(args.outdir)
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    written, skipped_dupes, errors, warnings = [], [], [], []

    posts, books = [], []
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        with open(args.posts, encoding="utf-8-sig", newline="") as f:
            posts = list(csv.DictReader(f))
        with open(args.books, encoding="utf-8-sig", newline="") as f:
            books = list(csv.DictReader(f))
    except Exception as e:
        errors.append((f"{args.posts} / {args.books}", f"could not read input: {e}"))

    out_rows, seen, rows_with_books = [], set(), set()
    for b in books:
        label = f"row {b.get('sheet_row')}: {b.get('title')}"
        try:
            n = int(b["sheet_row"])
            if not 2 <= n <= len(posts) + 1:
                errors.append((label, f"sheet_row {n} is outside the table (2..{len(posts) + 1})"))
                continue
            p = posts[n - 2]
            key = (n, norm(b["title"]))
            if key in seen:
                skipped_dupes.append((label, "same title already listed for this row"))
                continue
            seen.add(key)
            haystack = norm(p.get("caption", "") + " " + p.get("hashtags", ""))
            # also try with spaces removed, so a title written as a hashtag (#catcherintherye) matches
            if norm(b["title"]) not in haystack and norm(b["title"]).replace(" ", "") not in haystack.replace(" ", ""):
                warnings.append((label, "title not found verbatim in the post's caption/hashtags (check spelling or row)"))
            rows_with_books.add(n)
            out_rows.append({
                "book_title": b["title"], "author": b.get("author", ""), "notes": b.get("notes", ""),
                "mention_source": b.get("mention_source", ""), "sheet_row": n,
                "post_url": p.get("post_url", ""), "owner": p.get("owner", ""),
                "saved_at": p.get("saved_at", ""), "collections": p.get("collections", ""),
                "caption": p.get("caption", ""),
            })
            written.append((label, p.get("post_url", "")))
        except Exception as e:
            errors.append((label, str(e)))

    no_books = [{"sheet_row": i + 2, "shortcode": p.get("shortcode", ""), "post_url": p.get("post_url", ""),
                 "owner": p.get("owner", "")} for i, p in enumerate(posts) if (i + 2) not in rows_with_books]

    def write_csv(name, cols, rows):
        path = outdir / name
        try:
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
        except Exception as e:
            errors.append((str(path), f"could not write: {e}"))

    write_csv("books-mentioned.csv", ["book_title", "author", "notes", "mention_source", "sheet_row",
                                       "post_url", "owner", "saved_at", "collections", "caption"], out_rows)
    write_csv("posts-without-books.csv", ["sheet_row", "shortcode", "post_url", "owner"], no_books)

    finished = datetime.now()
    lines = [
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} (duration {(finished - started).total_seconds():.1f}s)",
        f"Input       : {args.posts} + {args.books}",
        f"Output      : {outdir / 'books-mentioned.csv'}, {outdir / 'posts-without-books.csv'}",
        "",
        "SUMMARY",
        f"  Total curated book mentions     : {len(books)}",
        f"  Done this run (written)         : {len(out_rows)}",
        "  Already done (skipped)          : 0",
        f"  Skipped on purpose              : {len(skipped_dupes)}",
        f"  Errors                          : {len(errors)}",
        f"  Warnings                        : {len(warnings)}",
        f"  Posts in the table              : {len(posts)}",
        f"  Posts with at least one book    : {len(rows_with_books)}",
        f"  Posts with no book extracted    : {len(no_books)}",
        "",
    ]

    def section(title, items):
        lines.append(f"{title} ({len(items)})")
        if not items:
            lines.append("  (none)")
        for a, b in items:
            lines.append(f"  {a}")
            lines.append(f"      {b}")
        lines.append("")

    section("SUCCESSFUL: WRITTEN", written)
    section("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", [])
    section("SKIPPED ON PURPOSE: DUPLICATE TITLE FOR THE SAME ROW", skipped_dupes)
    section("ERRORS", errors)
    section("WARNINGS", warnings)
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(out_rows)} book mentions from {len(rows_with_books)} posts; {len(no_books)} posts with no book")
    print(f"Results log: {log_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
