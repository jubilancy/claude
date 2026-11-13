#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
sort_markdown.py - sort wiki_to_markdown.py's .md files into folder/subfolder by their front-matter categories

Reads the `categories:` list from each file's front matter, drops the housekeeping
categories Wikipedia adds (CS1 errors, "Pages with ... IPA", "Wikipedia pages
semi-protected ...", "1875 births", and so on), and picks a main category (folder)
and a second category (subfolder) for the file. Front matter has no field called
"main category", so you choose how it is picked with --by.

Dry run by default: prints the folder tree it would create and moves nothing.
Add --apply to move the files. Every run writes sort-log-{timestamp}.txt, and
--apply also writes sort-moves-{timestamp}.csv so --undo can put everything back.

--by common   (default) a file's main category is the one it shares with the most
              other files in the folder you are sorting; its subfolder is the next
              most shared. Categories on fewer than --min files are ignored, so a
              file that shares nothing goes to _unsorted. Best for big corpora.
--by first    the first category that survives the filter, in the order Wikipedia
              lists them. Works on any corpus, even a single file.

Files with no front matter are left alone (they are probably your own notes).
Nothing is overwritten: if the target name is taken the file is skipped and logged.

Usage:
    uv run scripts/wikimedia/sort_markdown.py corpus                 # dry run: show the plan
    uv run scripts/wikimedia/sort_markdown.py corpus --apply         # move the files
    uv run scripts/wikimedia/sort_markdown.py corpus --by first --depth 1 --apply
    uv run scripts/wikimedia/sort_markdown.py corpus --min 3 --skip "^Plays? " --apply
    uv run scripts/wikimedia/sort_markdown.py --undo sort-moves-2026-11-13_120000.csv
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

# Housekeeping categories that say nothing about the topic. Case-insensitive regexes.
DEFAULT_SKIP = [
    r"^Pages ", r"^CS1", r"^Wikipedia", r"^All ", r"^Use ", r"^Articles ", r"^Webarchive",
    r"^Short description", r"^Commons ", r"^Wikidata", r"^Coordinates ", r"^Biography with",
    r"^Spoken articles", r"^Accuracy disputes", r"^Good articles", r"^Featured articles",
    r"^Vague or ambiguous", r"^Infobox", r"template with ID", r"^Living people$",
    r"^People appearing on", r"template", r"^Date of (birth|death)", r"^\d{1,4}s? (births|deaths)$", r"^\d{1,4}s? BC (births|deaths)$",
    r"^\d+(st|nd|rd|th)-century (births|deaths)$", r"stubs?$", r"^Redirects ",
]
UNSORTED = "_unsorted"


def split_front_matter(text: str):
    """Return the parsed front matter dict, or None if the file has none."""
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def safe_dir(name: str, max_len: int = 80) -> str:
    """Folder name safe on macOS/Windows/Obsidian."""
    for bad, good in {"/": "-", "\\": "-", ":": " -", "*": "", "?": "", '"': "'", "<": "(",
                      ">": ")", "|": "-", "#": "", "^": "", "[": "(", "]": ")"}.items():
        name = name.replace(bad, good)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    name = (name[:max_len].rstrip() if len(name) > max_len else name) or UNSORTED
    return name[0].upper() + name[1:]


def usable(cats, skip_res, title=""):
    """Categories worth sorting by: no housekeeping, and not the article's own category."""
    out, seen = [], set()
    for c in cats or []:
        c = str(c).strip()
        if c and c.lower() != str(title).strip().lower() and c not in seen \
                and not any(r.search(c) for r in skip_res):
            seen.add(c)
            out.append(c)
    return out


def plan_destinations(files, args, skip_res):
    """files: {path: [usable categories]} -> {path: (main, sub)}"""
    freq = Counter(c for cats in files.values() for c in cats)
    result = {}
    if args.by == "first":
        for p, cats in files.items():
            main = cats[0] if cats else None
            sub = cats[1] if args.depth >= 2 and len(cats) > 1 else None
            result[p] = (main, sub)
        return result

    def rank(cats, pool=None):
        ok = [c for c in cats if freq[c] >= args.min and (pool is None or c in pool)]
        # most shared first; ties by name, so files that share categories land together
        return sorted(ok, key=lambda c: (-freq[c], c.lower()))

    mains = {p: (rank(cats) or [None])[0] for p, cats in files.items()}
    group = defaultdict(list)
    for p, m in mains.items():
        group[m].append(p)
    for m, members in group.items():
        sub_freq = Counter(c for p in members for c in files[p] if c != m)
        for p in members:
            sub = None
            if m and args.depth >= 2:
                cand = sorted((c for c in files[p] if c != m and sub_freq[c] >= args.min),
                              key=lambda c: (-sub_freq[c], c.lower()))
                sub = cand[0] if cand else None
            result[p] = (m, sub)
    return result


def run_undo(log_csv: Path) -> int:
    rows = list(csv.DictReader(log_csv.open(encoding="utf-8")))
    done = skipped = 0
    dirs = set()
    for r in reversed(rows):
        src, dst = Path(r["from"]), Path(r["to"])
        if not dst.exists() or src.exists():
            print(f"skip: {dst} (missing, or {src} already exists)")
            skipped += 1
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.rename(src)
        dirs.add(dst.parent)
        done += 1
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        for q in (d, *d.parents):
            try:
                q.rmdir()
            except OSError:
                break
    print(f"Restored {done} file(s); skipped {skipped}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sort wiki markdown files into folders by front-matter category.")
    ap.add_argument("folder", nargs="?", default="corpus", help="folder of .md files (default: corpus)")
    ap.add_argument("--apply", action="store_true", help="move the files (default is a dry run)")
    ap.add_argument("--by", choices=["common", "first"], default="common")
    ap.add_argument("--depth", type=int, choices=[1, 2], default=2, help="1 = folders only, 2 = folder/subfolder")
    ap.add_argument("--min", type=int, default=2, help="a category must be on at least this many files (--by common)")
    ap.add_argument("--skip", action="append", default=[], metavar="REGEX",
                    help="extra category regex to ignore (repeatable)")
    ap.add_argument("--undo", type=Path, metavar="MOVES_CSV", help="reverse a previous --apply")
    args = ap.parse_args()

    if args.undo:
        return run_undo(args.undo)

    root = Path(args.folder)
    if not root.is_dir():
        print(f"Folder not found: {root}", file=sys.stderr)
        return 1
    skip_res = [re.compile(p, re.I) for p in DEFAULT_SKIP + args.skip]

    started = datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M%S")
    log_path, moves_path = Path(f"sort-log-{stamp}.txt"), Path(f"sort-moves-{stamp}.csv")

    files, no_front, errors = {}, [], []
    for p in sorted(root.rglob("*.md")):
        try:
            fm = split_front_matter(p.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append((p, f"could not read: {e}"))
            continue
        if fm is None:
            no_front.append(p)
            continue
        files[p] = usable(fm.get("categories"), skip_res, fm.get("title", p.stem))

    dest = plan_destinations(files, args, skip_res)
    moved, already, collisions = [], [], []
    tree = Counter()
    taken = {}
    for p, (main_cat, sub_cat) in dest.items():
        parts = [safe_dir(main_cat) if main_cat else UNSORTED]
        if sub_cat and main_cat:
            parts.append(safe_dir(sub_cat))
        target = root.joinpath(*parts, p.name)
        tree["/".join(parts)] += 1
        if target == p:
            already.append(p)
        elif target.exists() or taken.get(target) not in (None, p):
            collisions.append((p, target))
        else:
            taken[target] = p
            moved.append((p, target))

    print(f"{len(files)} file(s) with front matter in {root}/ "
          f"({'APPLYING' if args.apply else 'dry run, nothing moved'}; --by {args.by}, depth {args.depth})\n")
    for folder, n in sorted(tree.items(), key=lambda kv: (kv[0] == UNSORTED, kv[0])):
        print(f"  {n:4d}  {folder}/")

    if args.apply:
        with moves_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["from", "to"])
            for src, dst in moved:
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    src.rename(dst)
                    w.writerow([src, dst])
                except OSError as e:
                    errors.append((src, str(e)))
        moved = [(s, d) for s, d in moved if d.exists()]
        for d in sorted({s.parent for s, _ in moved}, key=lambda q: len(q.parts), reverse=True):
            q = d
            while q != root and q.is_dir():  # tidy folders emptied by the moves
                try:
                    q.rmdir()
                except OSError:
                    break
                q = q.parent

    lines = [
        "sort_markdown results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Folder      : {root}",
        f"Mode        : {'apply' if args.apply else 'dry run (nothing moved)'}; --by {args.by}; depth {args.depth}; min {args.min}",
        "",
        "SUMMARY",
        f"  Files with front matter        : {len(files)}",
        f"  {'Moved' if args.apply else 'Would move'}                          : {len(moved)}",
        f"  Already in the right folder    : {len(already)}",
        f"  Skipped (target name taken)    : {len(collisions)}",
        f"  Left alone (no front matter)   : {len(no_front)}",
        f"  Errors                         : {len(errors)}",
        "",
        f"FOLDERS ({len(tree)})",
    ]
    lines += [f"  {n:4d}  {folder}/" for folder, n in sorted(tree.items())] or ["  (none)"]
    lines += ["", f"{'MOVED' if args.apply else 'WOULD MOVE'} ({len(moved)})"]
    lines += [f"  {s.relative_to(root)}\n    -> {d.relative_to(root)}" for s, d in moved] or ["  (none)"]
    lines += ["", f"SKIPPED: TARGET NAME TAKEN ({len(collisions)})"]
    lines += [f"  {s.relative_to(root)}\n    -> {d.relative_to(root)}" for s, d in collisions] or ["  (none)"]
    lines += ["", f"LEFT ALONE: NO FRONT MATTER ({len(no_front)})"]
    lines += [f"  {p.relative_to(root)}" for p in no_front] or ["  (none)"]
    lines += ["", f"ERRORS ({len(errors)})"]
    lines += [f"  {p}\n    {e}" for p, e in errors] or ["  (none)"]
    lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")

    verb = "Moved" if args.apply else "Would move"
    print(f"\n{verb} {len(moved)}; {len(already)} already in place; {len(collisions)} skipped (name taken); "
          f"{len(no_front)} left alone (no front matter); {len(errors)} failed.")
    print(f"Log: {log_path}")
    if args.apply and moved:
        print(f"Undo with: uv run scripts/wikimedia/sort_markdown.py --undo {moves_path}")
    elif not args.apply and moved:
        print("Run again with --apply to move them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
