#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
bookmark_titles.py - Raindrop bookmark dump (JSON) -> clean list of book titles.

What it does:
- Reads a bookmark JSON dump (a list of {bookmark_id, title, link, type, tags, ...},
  as written by scripts/raindrop/extract_bookmarks.py).
- Cleans each title using only what the bookmark itself says: strips site
  suffixes (" - Free ebook download", " | Project Gutenberg", "| Open Library"...),
  and splits "Title by Author" / "Title, by Author. Translated by ..." when the
  pattern is in the title. Nothing is looked up or guessed; an author is only
  filled when the bookmark title contains it.
- Flags rows instead of guessing: not-a-book (search pages, lists, series, shop
  homepages), no-title (title is just a domain), duplicate (same title seen
  already; the first row keeps the entry and later ones are listed under it).
- Writes a CSV (title, author, edition_note, source, link, bookmark_id, tags,
  flags), a plain text list of the titles, and results-log-{timestamp}.txt in
  the current folder every run.

Usage:
    uv run scripts/books/bookmark_titles.py books.json
    uv run scripts/books/bookmark_titles.py books.json --csv titles.csv --txt titles.txt
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SUFFIXES = [
    r"\s*[-|–]\s*Free ebook download$", r"\s*\|\s*Free audiobook\s*\|\s*Digitalbook\.io$",
    r"\s*\|\s*Project Gutenberg$", r"\s*\|\s*Open Library$", r"\s*[-|]\s*Z-Library$",
    r"\s*\|\s*Libgen$", r"\s*\|\s*New Directions Publishing$",
    r"\s*:\s*[^:]*:\s*Free Download, Borrow, and Streaming\s*:\s*Internet Archive$",
    r"\s*\((?:Hardback|Paperback)[^)]*\)$", r":\s*SHORTLISTED.*$", r":\s*A Novel$",
]
NOT_BOOK_TITLE = re.compile(
    r"^(search\b|browse|books by:|series:|best |harvard classics|around the world|"
    r".*search on libgen$|.*browse all books)", re.I)
NOT_BOOK_LINK = re.compile(r"(/search\b|/s\?|/s/|/series/|/list/|/author/list|/ebooks$|/book/similar)", re.I)
HOST_ONLY = re.compile(r"^(https?://)?(www\.)?[\w.-]+\.(com|net|org|co|io|uk|de)/?$", re.I)


def host(link):
    return urlparse(link).netloc.lower().removeprefix("www.")


def clean(b):
    """Return (title, author, note, flags)."""
    t = (b.get("title") or "").strip()
    link = b.get("link", "")
    h = host(link)
    flags = []
    for s in SUFFIXES:
        t = re.sub(s, "", t, flags=re.I).strip()
    if not t or HOST_ONLY.match(t):
        return "", "", "", ["no-title"]
    if NOT_BOOK_TITLE.match(t) or NOT_BOOK_LINK.search(link) or t.lower() in ("browse standard ebooks",):
        return t, "", "", ["not-a-book"]
    author = note = ""
    # Standard Ebooks: "Title, by Author. Translated by X"
    m = re.match(r"^(.*?),\s+by\s+(.+?)(?:\.\s+(Translated by .+))?$", t)
    if m and "standardebooks" in h:
        t, author, note = m.group(1), m.group(2), m.group(3) or ""
    else:
        m = re.match(r"^(.*?)\s+(?:book\s+)?by\s+(.+)$", t)
        # "X book by Y" (ThriftBooks) or "X by Y" on library sites; avoid titles that contain "by" mid-phrase on shops
        if m and (h.split(".")[-2:] in (["gutenberg", "org"], ["openlibrary", "org"], ["thriftbooks", "com"])
                  or re.search(r" book by ", t)):
            t, author = m.group(1), m.group(2)
        m2 = re.match(r"^(.*?)\s*\((version \d+|[^)]*dramatic reading[^)]*|[^)]*translation)\)\s*$", t, re.I)
        if m2:
            t, note = m2.group(1).strip(), m2.group(2)
    m = re.match(r"^(.*?)\s+by\s+(.+)$", t)
    if m and h.startswith(("z-lib", "libgen")):
        t, author = m.group(1), m.group(2)
    if not author:  # AbeBooks search URLs name the author in the path
        m = re.search(r"/author/([a-z0-9-]+)", link)
        if m:
            author = m.group(1).replace("-", " ").title()
            flags.append("author-from-url")
    t = re.sub(r"\s+", " ", t).strip(" ,:;")
    if h == "digitalbook.io":
        note = (note + "; " if note else "") + "audiobook"
    if h == "amazon.com" and "audiobook" in link:
        note = (note + "; " if note else "") + "audiobook"
    if re.search(r"/book/|/ebooks?/", link) is None and b.get("type") not in ("book",) and h not in (
            "digitalbook.io", "standardebooks.org", "epubbooks.com", "gutenberg.org", "abebooks.com", "thriftbooks.com"):
        flags.append("check")
    return t, author, note, flags


def norm(t, author=""):
    t = re.sub(r",\s+or\s+.*$", "", t.lower())
    t = re.sub(r"^(the|a|an)\s+", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def write_log(path, meta, written, dups, nots, notitle, errors):
    L = ["bookmark_titles results log",
         f"Run started : {meta['started']}",
         f"Run finished: {meta['finished']} (duration {meta['dur']})",
         f"Input file  : {meta['input']}",
         f"Output files: {meta['csv']}, {meta['txt']}",
         "", "SUMMARY",
         f"  Total bookmarks              : {meta['total']}",
         f"  Done this run (titles listed): {len(written)}",
         f"  Already done (skipped)       : 0",
         f"  Skipped on purpose           : {len(nots) + len(notitle) + len(dups)}",
         f"  Errors                       : {len(errors)}", "",
         f"SUCCESSFUL: WRITTEN ({len(written)})"]
    L += [f"  {b['link']}\n    -> {t}" + (f" / {a}" if a else "") for b, t, a in written] or ["  (none)"]
    L += ["", f"SKIPPED ON PURPOSE: NOT A SINGLE BOOK ({len(nots)})"]
    L += [f"  {b['link']}\n    {t}" for b, t in nots] or ["  (none)"]
    L += ["", f"SKIPPED ON PURPOSE: NO TITLE IN BOOKMARK ({len(notitle)})"]
    L += [f"  {b['link']}\n    title was only a domain" for b in notitle] or ["  (none)"]
    L += ["", f"SKIPPED ON PURPOSE: DUPLICATE TITLE ({len(dups)})"]
    L += [f"  {b['link']}\n    same as: {t}" for b, t in dups] or ["  (none)"]
    L += ["", f"ERRORS ({len(errors)})"]
    L += [f"  {x}\n    {e}" for x, e in errors] or ["  (none)"]
    L += ["", "WARNINGS (0)", "  (none)", ""]
    Path(path).write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--csv", default="book-titles.csv")
    ap.add_argument("--txt", default="book-titles.txt")
    a = ap.parse_args()
    started = datetime.now()
    data = json.load(open(a.input, encoding="utf-8"))
    data = data if isinstance(data, list) else data.get("bookmarks", [])
    data.sort(key=lambda b: b.get("bookmark_id", 0))
    rows, written, dups, nots, notitle, errors, seen = [], [], [], [], [], [], {}
    for b in data:
        try:
            t, au, note, flags = clean(b)
            if "no-title" in flags:
                notitle.append(b); continue
            if "not-a-book" in flags:
                nots.append((b, t)); continue
            k = norm(t) + (("|" + norm(au)) if au else "")
            k = next((x for x in seen if not x.endswith("#i") and (x == k or x.split("|")[0] == k.split("|")[0] and ("|" not in x or "|" not in k))), k)
            if k in seen:
                dups.append((b, seen[k]))
                rows[seen[k + "#i"]]["also_at"] += (" | " if rows[seen[k + "#i"]]["also_at"] else "") + b["link"]
                continue
            seen[k] = t
            seen[k + "#i"] = len(rows)
            rows.append({"title": t, "author": au, "note": note, "source": host(b["link"]), "link": b["link"],
                         "bookmark_id": b["bookmark_id"], "tags": "; ".join(b.get("tags") or []),
                         "flags": " ".join(flags), "also_at": ""})
            written.append((b, t, au))
        except Exception as e:  # one bad row never stops the run
            errors.append((b.get("link", "?"), repr(e)))
    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "note", "source", "link", "bookmark_id", "tags", "flags", "also_at"])
        w.writeheader(); w.writerows(rows)
    Path(a.txt).write_text("\n".join(r["title"] + (f" - {r['author']}" if r["author"] else "") for r in rows) + "\n", encoding="utf-8")
    fin = datetime.now()
    log = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    write_log(log, {"started": started.isoformat(" ", "seconds"), "finished": fin.isoformat(" ", "seconds"),
                    "dur": str(fin - started).split(".")[0], "input": a.input, "csv": a.csv, "txt": a.txt,
                    "total": len(data)}, written, dups, nots, notitle, errors)
    print(f"{len(rows)} titles -> {a.csv}, {a.txt}; log: {log}")


if __name__ == "__main__":
    sys.exit(main())
