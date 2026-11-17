#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
pin_to_wp_post.py - Pinterest pin markdown notes -> WordPress-ready post files.

What it does:
- Takes a .zip of notes, a folder of .md files, or a single .md file.
  Zips are extracted into a fresh folder next to the output, never into the
  current folder.
- For each note, reads the pin heading ("## 1. Title | tag, tag, tag"), the
  Source URL and the image, and writes <slug>.md where the slug comes from the
  title (gawaine-arthurian-knight.md).
- Category and tags go in YAML front matter (WordPress metadata), not in the
  post body. Output layout:
      ---
      title: "Gawaine Arthurian Knight"
      slug: gawaine-arthurian-knight
      categories: ["Arthurian Legend"]
      tags: ["Howard pyle", "Arthurian legend", "Green knight"]
      ---

      # Gawaine Arthurian Knight

      ![alt](image url)

      [view-source](https://www.pinterest.com/pin/...)
- Title = text before the first " | ", Title Cased. Tags = the comma list after
  it. Category = chosen from keywords: categories.txt (next to this script, or
  --categories FILE) has one "Category: keyword, keyword" line per category.
  The category with the most keyword hits in the title + tags wins (ties go to
  the earlier line). No hit -> "Uncategorized" and a warning in the log.
- --scan prints every tag with its count (most common first) so you can build
  categories.txt from the real data. It writes no posts.
- Skips notes whose output file already exists (use --force to redo them).
  Two notes with the same title get -2, -3 ... on the slug.
- Never stops on one bad file; every outcome goes in the log.
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/pinterest/pin_to_wp_post.py notes.zip
    uv run scripts/pinterest/pin_to_wp_post.py notes/ --output posts
    uv run scripts/pinterest/pin_to_wp_post.py pin.md --force
"""

import argparse
import re
import sys
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs"}


def title_case(s: str) -> str:
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if 0 < i < len(words) - 1 and lw in SMALL:
            out.append(lw)
        else:
            out.append(w[:1].upper() + w[1:].lower() if not w.isupper() or len(w) > 3 else w)
    return " ".join(out)


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def parse_note(text: str, fallback: str):
    src = re.search(r"Source URL:\s*<?\[?[^\s<>\]]*?(https?://[^\s<>\])]+)", text)
    url = src.group(1) if src else ""
    img = re.search(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)", text)
    alt, img_url = (img.group(1), img.group(2)) if img else ("", "")
    head = re.search(r"^##\s*(?:\d+\.\s*)?(.+)$", text, re.M)
    raw = head.group(1).strip() if head else (alt or fallback)
    title_raw, _, tag_part = raw.partition(" | ")
    tags = [t.strip() for t in tag_part.split(",") if t.strip()]
    return {"title": title_case(title_raw.strip()), "url": url, "alt": alt or raw,
            "img": img_url, "tags": tags}


def load_categories(path: Path):
    cats = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            name, _, kws = line.partition(":")
            cats.append((name.strip(), [k.strip().lower() for k in kws.split(",") if k.strip()]))
    return cats


def pick_category(p: dict, cats):
    hay = " ".join([p["title"]] + p["tags"]).lower()
    best, score = "", 0
    for name, kws in cats:
        n = sum(1 for k in kws if k in hay)
        if n > score:
            best, score = name, n
    return best


def render(p: dict) -> str:
    q = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    lines = ["---", f"title: {q(p['title'])}", f"slug: {p['slug']}",
             f"categories: [{q(p['category'])}]",
             "tags: [" + ", ".join(q(t) for t in p["tags"]) + "]", "---", "",
             f"# {p['title']}", ""]
    if p["img"]:
        lines += [f"![{p['alt']}]({p['img']})", ""]
    if p["url"]:
        lines += [f"[view-source]({p['url']})", ""]
    return "\n".join(lines)


def collect(inp: Path, work: Path):
    if inp.is_dir():
        return sorted(inp.rglob("*.md"))
    if inp.suffix.lower() == ".zip":
        dest = work / (inp.stem + "-extracted")
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(inp) as z:
            for m in z.infolist():  # guard against path traversal
                if not (dest / m.filename).resolve().is_relative_to(dest.resolve()):
                    raise ValueError(f"unsafe path in zip: {m.filename}")
            z.extractall(dest)
        return sorted(p for p in dest.rglob("*.md") if "__MACOSX" not in p.parts)
    return [inp]


def write_log(path, started, inp, out, done, skipped, warnings, errors, total):
    fin = datetime.now()
    L = ["pin_to_wp_post results log", "",
         f"Run started : {started:%Y-%m-%d %H:%M:%S}",
         f"Run finished: {fin:%Y-%m-%d %H:%M:%S} (duration {(fin - started).total_seconds():.1f}s)",
         f"Input       : {inp}", f"Output      : {out}", "",
         "SUMMARY", f"  Total notes          : {total}", f"  Written this run     : {len(done)}",
         f"  Already done (skipped): {len(skipped)}", "  Skipped on purpose   : 0",
         f"  Errors               : {len(errors)}", f"  Warnings             : {len(warnings)}", ""]
    for name, items in [("SUCCESSFUL: WRITTEN", done), ("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", skipped),
                        ("ERRORS", errors), ("WARNINGS", warnings)]:
        L.append(f"{name} ({len(items)})")
        L += [f"  {a}\n    {b}" for a, b in items] or ["  (none)"]
        L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Pin notes -> WordPress post files")
    ap.add_argument("input", help=".zip, folder or .md file")
    ap.add_argument("--output", default="wp-posts", help="output folder (default wp-posts)")
    ap.add_argument("--categories", default=str(Path(__file__).with_name("categories.txt")))
    ap.add_argument("--scan", action="store_true", help="list tag counts and exit")
    ap.add_argument("--force", action="store_true", help="overwrite existing output files")
    a = ap.parse_args()

    started = datetime.now()
    inp, out = Path(a.input), Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    log = Path(f"results-log-{started:%Y-%m-%d_%H%M%S}.txt")
    done, skipped, warnings, errors = [], [], [], []
    files = []
    try:
        files = collect(inp, out.parent)
    except Exception as e:
        errors.append((str(inp), f"{type(e).__name__}: {e}"))

    if a.scan:
        from collections import Counter
        c = Counter()
        for f in files:
            c.update(t.lower() for t in parse_note(f.read_text(encoding="utf-8-sig"), f.stem)["tags"])
        for t, n in c.most_common():
            print(f"{n}\t{t}")
        return
    cats = load_categories(Path(a.categories))
    used = set()
    for f in files:
        try:
            p = parse_note(f.read_text(encoding="utf-8-sig"), f.stem)
            p["category"] = pick_category(p, cats) or "Uncategorized"
            if p["category"] == "Uncategorized":
                warnings.append((f.name, "no category keyword matched"))
            slug = slugify(p["title"]) or slugify(f.stem)
            if not slug:
                raise ValueError("could not make a slug")
            base, n = slug, 2
            while slug in used:
                slug, n = f"{base}-{n}", n + 1
            used.add(slug)
            p["slug"] = slug
            for field in ("url", "img", "tags"):
                if not p[field]:
                    warnings.append((f.name, f"no {field} found"))
            dest = out / f"{slug}.md"
            if dest.exists() and not a.force:
                skipped.append((f.name, f"{dest} exists"))
                continue
            dest.write_text(render(p), encoding="utf-8")
            done.append((f.name, f"-> {dest}"))
        except Exception as e:
            errors.append((str(f), f"{type(e).__name__}: {e}"))

    write_log(log, started, inp, out, done, skipped, warnings, errors, len(files))
    print(f"written {len(done)}, skipped {len(skipped)}, warnings {len(warnings)}, errors {len(errors)}")
    print(f"log: {log}")


if __name__ == "__main__":
    sys.exit(main())
