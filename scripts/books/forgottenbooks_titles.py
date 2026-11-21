#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["wordninja"]
# ///
"""
forgottenbooks_titles.py - turn Forgotten Books links into a list of readable book titles

A forgottenbooks.com link ends in the title with the spaces removed, then an ID:
    /en/books/TheWitchcraftDelusioninNewEngland_10005809
This splits the slug back into words and writes the titles to a CSV (title first, then the
Forgotten Books ID, URL, Raindrop bookmark ID, and category tag) and a plain titles list.

Input is a JSON dump of Raindrop bookmarks (see scripts/raindrop/extract_bookmarks.py) or a text
file of URLs, one per line. How the words are found: capital letters start words, and lowercase
joining words glued to the end of a word (of, the, in, and, or, ...) are split off only when
what is left is a real English word, so rare and archaic words (Saducismus, Daimonologia) stay whole.

The title can only be as good as the URL, so some rows are flagged in the "flags" column:
  truncated   the URL slug is cut at 80 characters, so the end of the title is missing
  check       a word is not in the English word list (an archaic spelling, a name, or glued words)
  duplicate   the same title appears under more than one Forgotten Books ID (different editions)
  same-link   the exact same link is saved more than once
Punctuation and apostrophes are not in the URL (PottssDiscoveryofWitches is Pott's Discovery of Witches).

Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/books/forgottenbooks_titles.py library.json                 # -> forgottenbooks-titles.csv + .txt
    uv run scripts/books/forgottenbooks_titles.py urls.txt -o my-books
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import wordninja

COST = wordninja.DEFAULT_LANGUAGE_MODEL._wordcost  # lower cost = more common word
WORDS = set(COST)
FUNCTION = ["of", "the", "in", "and", "or", "to", "a", "an", "for", "on", "with", "by", "from", "upon"]
NOT_SPLIT = {"whereof", "thereof", "hereof", "bathe", "breathe", "soothe", "clothe", "seethe", "loathe", "tithe", "lathe"}
SLUG_RE = re.compile(r"/books/([^/_?#]+)_(\d+)")
SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")


def known(word: str) -> bool:
    return word.lower() in WORDS or word.isdigit()


def as_function_words(s: str):
    """Split s entirely into function words (orthe -> or, the), or return None."""
    if not s:
        return []
    for fw in sorted(FUNCTION, key=len, reverse=True):
        if s.startswith(fw):
            rest = as_function_words(s[len(fw):])
            if rest is not None:
                return [fw] + rest
    return None


def split_chunk(chunk: str):
    """One capital-started chunk -> (words, ok). Peels glued function words off the end.

    First choice is a known English head with function words after it, taken only when the
    pieces are more common than the whole (Christof -> Christ of). Second choice is an unknown
    head (an archaic spelling), split only when it is 5+ letters and the tail is "of"/"the" or
    two or more function words (Anatomieof, Withcraftandthe); words that merely end in -or, -on,
    -an, -and (Doctor, Highland) stay whole. ok is False when a word is left that is not in the
    word list.
    """
    lower = chunk.lower()
    whole_known = known(chunk)
    if len(chunk) <= 3:
        return [chunk], True
    if len(chunk) <= 8 and as_function_words(lower):  # Inthe, Onthe
        return as_function_words(lower), True
    whole_cost = COST.get(lower, 1e9)
    cuts = []
    for k in range(len(chunk) - 1, 2, -1):  # longest head first
        words = as_function_words(lower[k:])
        if words and words != ["a"]:  # a lone trailing "a" is usually the end of a word (Sylva, Galla)
            cuts.append((chunk[:k], lower[k:], words))
    for head, tail, words in cuts:  # known heads first
        if known(head):
            split_cost = COST.get(head.lower(), 0) + sum(COST.get(w, 0) for w in words)
            strong = tail in ("of", "the") and len(head) >= 4 and lower not in NOT_SPLIT
            if not whole_known or strong or split_cost < whole_cost:
                hw, hok = split_chunk(head)
                return hw + words, hok
    if not whole_known:
        for head, tail, words in cuts:  # then unknown heads
            if len(head) >= 5 and (tail in ("of", "the") or len(words) >= 2):
                hw, _ = split_chunk(head)
                return hw + words, len(hw) > 1 and all(known(w) for w in hw)
    return [chunk], whole_known


def title_from_slug(slug: str):
    chunks = [c for c in SPLIT_RE.split(slug) if c]
    words, ok = [], True
    for c in chunks:
        w, good = split_chunk(c)
        words += w
        ok = ok and good
    return " ".join(words), ok


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [(str(b.get("bookmark_id", "")), b["link"], (b.get("tags") or [""])[-1]) for b in json.loads(text)]
    return [("", l.strip(), "") for l in text.splitlines() if l.strip().startswith("http")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", default="forgottenbooks-titles", help="base name for .csv and .txt")
    a = ap.parse_args()
    started = datetime.now()

    rows, skipped, seen_urls, repeated = [], [], set(), []
    for bid, link, cat in load(a.input):
        m = SLUG_RE.search(unquote(urlsplit(link).path))
        if not m:
            skipped.append(link)
            continue
        if link in seen_urls:
            repeated.append(link)
        seen_urls.add(link)
        slug, fid = m.groups()
        title, ok = title_from_slug(slug)
        flags = []
        if len(slug) >= 80:
            flags.append("truncated")
        if not ok:
            flags.append("check")
        rows.append({"title": title, "forgottenbooks_id": fid, "url": link, "bookmark_id": bid, "category": cat,
                     "flags": " ".join(flags)})
    counts = Counter(r["title"].lower() for r in rows)
    links = Counter(r["url"] for r in rows)
    for r in rows:
        if counts[r["title"].lower()] > 1:
            r["flags"] = (r["flags"] + (" same-link" if links[r["url"]] > 1 else " duplicate")).strip()
    rows.sort(key=lambda r: (re.sub(r"^(the|a|an) ", "", r["title"].lower()), r["forgottenbooks_id"]))

    csv_path, txt_path = Path(f"{a.output}.csv"), Path(f"{a.output}.txt")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "forgottenbooks_id", "url", "bookmark_id", "category", "flags"])
        w.writeheader()
        w.writerows(rows)
    txt_path.write_text("\n".join(f"{i}. {r['title']}" for i, r in enumerate(rows, 1)) + "\n", encoding="utf-8")

    finished = datetime.now()
    by = lambda flag: [r for r in rows if flag in r["flags"].split()]
    log = Path(f"results-log-{started:%Y-%m-%d_%H%M%S}.txt")
    lines = [
        "forgottenbooks_titles results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} ({(finished - started).seconds}s)",
        f"Input       : {a.input}",
        f"Output      : {csv_path}, {txt_path}",
        "",
        "SUMMARY",
        f"  Links read                    : {len(rows) + len(skipped)}",
        f"  Titles written                : {len(rows)}",
        f"  Distinct links                : {len(set(links))}",
        f"  Distinct titles               : {len(counts)}",
        f"  Skipped (not a book link)     : {len(skipped)}",
        f"  Warnings (truncated/check)    : {len(by('truncated')) + len(by('check'))}",
        "",
        f"SUCCESSFUL: WRITTEN ({len(rows)})",
    ]
    lines += [f"  {r['url']}\n    {r['title']}" for r in rows]
    lines += ["", f"SKIPPED ON PURPOSE: NOT A FORGOTTEN BOOKS LINK, OR REPEATED ({len(skipped)})"]
    lines += [f"  {s}" for s in skipped] or ["  (none)"]
    lines += ["", "ERRORS (0)", "  (none)", "", f"WARNINGS: TITLE CUT OFF IN THE URL ({len(by('truncated'))})"]
    lines += [f"  {r['url']}\n    {r['title']}" for r in by("truncated")] or ["  (none)"]
    lines += ["", f"WARNINGS: A WORD IS NOT IN THE WORD LIST ({len(by('check'))})"]
    lines += [f"  {r['url']}\n    {r['title']}" for r in by("check")] or ["  (none)"]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} titles ({len(set(links))} distinct links, {len(counts)} distinct titles), "
          f"{len(by('truncated'))} truncated, {len(by('check'))} to check")
    print(f"Wrote {csv_path}, {txt_path}; log: {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
