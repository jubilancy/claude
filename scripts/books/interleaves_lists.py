#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["beautifulsoup4", "lxml"]
# ///
"""
interleaves_lists.py - turn Robert Teeter's Great Books lists on interleaves.org into one big CSV

Downloads each list page (politely, one at a time, with a pause, and keeps a copy in a cache folder
so reruns do not hit the site), reads the books out of it, and writes one row per book. The page's
own headings travel with every row, so nothing has to be checked by hand:

    list, header, subheader, subsubheader, position, title, author, year, entry, flags, list_url

  header / subheader / subsubheader   the h2 / h3 / h4-h5 headings above the book on the page
  position                            the number in a numbered list (1, 2, 3 ...), blank otherwise
  title / author / year               best guess from the entry's italics and wording
  entry                               the entry exactly as printed, so nothing is lost
  flags                               no-italics (no italic title found, so the whole entry is the title),
                                      no-author, multi-title, table-row

Input is a JSON dump of Raindrop bookmarks (scripts/raindrop/extract_bookmarks.py) or a text file of
URLs. Only the list pages are read: index pages (author-title A-Z, period tables), the FAQ and
site-navigation pages are skipped unless you pass --all.

Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/books/interleaves_lists.py library.json                       # -> interleaves-lists.csv
    uv run scripts/books/interleaves_lists.py urls.txt -o great-books --delay 2
    uv run scripts/books/interleaves_lists.py urls.txt --all                     # try every page
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

# File names of the pages that are actual book lists (the rest are indexes and site pages).
LIST_PAGES = {
    "gbww", "grtgood", "grtlubbock", "grtinfluential", "grtadler", "grtbloom", "grtcol37", "grtcollh",
    "grtfad3", "grtfad4", "grtcolcc", "grthungry", "grt99", "grttls", "grtlat", "grtbomc", "MedReading",
    "grtward", "grtrex", "grtrexmo", "grtasian", "grtorien", "grtmwasian",
}
COLS = ["list", "header", "subheader", "subsubheader", "position", "title", "author", "year", "entry", "flags", "list_url"]
TITLE_TAGS = ("cite", "em", "i")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def own_text(li) -> str:
    """Text of an element without its nested li/dd/ul/ol children."""
    parts = []
    for node in li.children:
        if getattr(node, "name", None) in ("ul", "ol", "dd", "dl", "li"):
            continue
        parts.append(node.get_text(" ") if hasattr(node, "get_text") else str(node))
    return clean(" ".join(parts))


def split_entry(el):
    """(title, author, year, flags) for one entry element, best effort."""
    flags = []
    cites = [clean(t.get_text(" ")) for t in el.find_all(TITLE_TAGS, recursive=True)
             if not t.find_parent(["dd", "ul", "ol"]) or t.find_parent(["dd", "ul", "ol"]) is el.find_parent(["dd", "ul", "ol"])]
    text = own_text(el) if el.name == "li" else clean(el.get_text(" "))
    year = ""
    m = re.search(r"\((?:c\. ?)?(\d{3,4}(?:[-–]\d{2,4})?)\)\s*$", text)
    if m:
        year, text = m.group(1), clean(text[: m.start()])
    if cites:
        title = cites[0] if len(cites) == 1 else " | ".join(cites)
        if len(cites) > 1:
            flags.append("multi-title")
        rest = text
        for c in cites:
            rest = rest.replace(c, " ", 1)
        rest = re.sub(r"\bby\b", " ", rest, count=1, flags=re.I)
        rest = re.sub(r"\(\s*\)|\[\s*\]", " ", rest)  # empty brackets left where an italic was removed
        author = clean(rest.strip(" ,.;:-–—"))
        author = re.sub(r"^(and|with|of)\s+|[,\s]+(and|with)$", "", author, flags=re.I).strip(" ,.;:-")
        if not author:
            flags.append("no-author")
        return title, author, year, flags
    m = re.match(r"^([^.]{2,40}?)\.\s+(.+)$", text)  # "Plato. The Republic"
    if m and len(m.group(1).split()) <= 4 and not re.search(r"\b(vol|ed|trans|St|Mr|Dr)$", m.group(1)):
        return clean(m.group(2)), clean(m.group(1)), year, flags
    flags += ["no-italics"]
    return text, "", year, flags


def parse_page(html: bytes, url: str):
    soup = BeautifulSoup(html, "lxml")
    root = soup.find(id="contentwside") or soup.find(id="container") or soup.body
    h1 = root.find("h1")
    list_name = clean(h1.get_text(" ")) if h1 else clean(soup.title.get_text()) if soup.title else url
    heads = {2: "", 3: "", 4: ""}
    rows = []
    n_in_list = {}
    table_cols = {}
    for el in root.descendants:
        name = getattr(el, "name", None)
        if name in ("h2", "h3", "h4", "h5"):
            level = min(int(name[1]), 4)
            heads[level] = clean(el.get_text(" "))
            for deeper in range(level + 1, 5):
                heads[deeper] = ""
            continue
        if name == "li" and not el.find_parent("li"):
            if el.find_parent(["h1", "h2", "h3", "h4", "h5"]):
                continue  # a heading written as <h2><li>...</li></h2>; the heading itself is handled above
            if re.search(r"rules|how/why|^notes?\b|about this", heads[2], re.I):
                continue  # explanatory text, not books
            label = own_text(el)
            nxt = el.find_next_sibling()
            if label.endswith(":") and (el.find(["ul", "ol"]) or (nxt is not None and nxt.name in ("ul", "ol"))):
                heads[4] = label.rstrip(":")
                continue
            if el.find_parent(["nav"]) or el.find("a") and not el.find(TITLE_TAGS) and len(own_text(el)) < 25:
                continue  # link-only navigation items
            parent = el.find_parent(["ol", "ul"])
            ordered = parent is not None and parent.name == "ol"
            key = id(parent)
            n_in_list[key] = n_in_list.get(key, 0) + 1
            pos = str(n_in_list[key]) if ordered else ""
            dds = el.find_all("dd")
            if dds:  # an author or volume with works underneath
                head_text = own_text(el)
                for dd in dds:
                    title, author, year, flags = split_entry(dd)
                    if "no-italics" in flags:
                        flags.remove("no-italics")
                    rows.append((heads.copy(), pos, title, author or head_text, year, f"{head_text} | {clean(dd.get_text(' '))}", flags))
            else:
                title, author, year, flags = split_entry(el)
                rows.append((heads.copy(), pos, title, author, year, own_text(el) or clean(el.get_text(" ")), flags))
        elif name == "tr" and not el.find_parent("li"):
            if el.find("th"):
                table_cols[id(el.find_parent("table"))] = [clean(c.get_text(" ")).lower() for c in el.find_all(["th", "td"])]
                continue
            cells = [clean(td.get_text(" ")) for td in el.find_all("td")]
            if len([c for c in cells if c]) < 2:
                continue
            cols = table_cols.get(id(el.find_parent("table")), [])
            get = lambda *names: next((cells[i] for i, c in enumerate(cols) if c in names and i < len(cells)), "")
            title = get("title") or cells[0]
            author = get("author") or (cells[1] if len(cells) > 1 else "")
            year = get("date", "year") or ""
            heads_now = heads.copy()
            if re.search(r"rules|how/why|^notes?\b|about this", heads_now[2], re.I):
                heads_now[2] = ""  # the heading above belongs to the intro text, not to the table
                caption = el.find_parent("table").find("caption")
                heads_now[3] = clean(caption.get_text(" ")) if caption else ""
            rows.append((heads_now, "", title, author, year, " | ".join(cells), ["table-row"]))
    out = []
    for h, pos, title, author, year, entry, flags in rows:
        if not title:
            continue
        out.append({"list": list_name, "header": h[2], "subheader": h[3], "subsubheader": h[4], "position": pos,
                    "title": title, "author": author, "year": year, "entry": entry, "flags": " ".join(flags),
                    "list_url": url})
    return list_name, out


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [b["link"] for b in json.loads(text)]
    return [l.strip() for l in text.splitlines() if l.strip().startswith("http")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", default="interleaves-lists", help="base name for the CSV")
    ap.add_argument("--cache", type=Path, default=Path("interleaves-pages"), help="folder for downloaded pages")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait between downloads")
    ap.add_argument("--all", action="store_true", help="read every page, not only the known list pages")
    a = ap.parse_args()
    started = datetime.now()

    a.cache.mkdir(parents=True, exist_ok=True)
    done, skipped, errors, warnings, all_rows = [], [], [], [], []
    for url in dict.fromkeys(load(a.input)):
        stem = Path(urlsplit(url).path).stem
        if not a.all and stem not in LIST_PAGES:
            skipped.append((url, "not a list page (index or site page)"))
            continue
        cached = a.cache / f"{stem}.html"
        try:
            if not cached.exists():
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (book-list reader)"})
                cached.write_bytes(urllib.request.urlopen(req, timeout=30).read())
                time.sleep(a.delay)
            name, rows = parse_page(cached.read_bytes(), url)
        except Exception as e:  # noqa: BLE001 - one bad page must not stop the run
            errors.append((url, f"{type(e).__name__}: {e}"))
            continue
        if not rows:
            errors.append((url, "no books found on the page"))
            continue
        flagged = sum(1 for r in rows if r["flags"])
        if flagged:
            warnings.append((url, f"{name}: {flagged} of {len(rows)} rows flagged ({', '.join(sorted({f for r in rows for f in r['flags'].split()}))})"))
        done.append((url, name, len(rows)))
        all_rows += rows

    csv_path = Path(f"{a.output}.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(all_rows)

    finished = datetime.now()
    log = Path(f"results-log-{started:%Y-%m-%d_%H%M%S}.txt")
    lines = [
        "interleaves_lists results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} ({(finished - started).seconds}s)",
        f"Input       : {a.input}",
        f"Output      : {csv_path} ({len(all_rows)} rows); pages cached in {a.cache}/",
        "",
        "SUMMARY",
        f"  Pages read                    : {len(done)}",
        f"  Book rows written             : {len(all_rows)}",
        f"  Skipped on purpose            : {len(skipped)}",
        f"  Errors                        : {len(errors)}",
        f"  Warnings                      : {len(warnings)}",
        "",
        f"SUCCESSFUL: WRITTEN ({len(done)})",
    ]
    lines += [f"  {u}\n    {n}: {c} rows" for u, n, c in done] or ["  (none)"]
    lines += ["", f"SKIPPED ON PURPOSE: NOT A LIST PAGE ({len(skipped)})"]
    lines += [f"  {u}\n    {why}" for u, why in skipped] or ["  (none)"]
    lines += ["", f"ERRORS ({len(errors)})"] + ([f"  {u}\n    {e}" for u, e in errors] or ["  (none)"])
    lines += ["", f"WARNINGS ({len(warnings)})"] + ([f"  {u}\n    {w}" for u, w in warnings] or ["  (none)"])
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(all_rows)} rows from {len(done)} lists; {len(skipped)} pages skipped, {len(errors)} errors")
    print(f"Wrote {csv_path}; log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
