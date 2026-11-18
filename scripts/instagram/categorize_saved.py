#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
categorize_saved.py - sort the Instagram saved-posts table into categories by hashtag.

What it does:
- Reads one or more CSVs made by saved_to_table.py (saved-posts*.csv).
- Gives every post exactly ONE category, decided by its hashtags:
  each hashtag votes for the categories whose keyword list it matches, the
  category with the most votes wins, and ties go to the category listed first
  in CATEGORIES (specific topics before Memes, Memes before Cats, Cats before
  Animals). Generic tags (#fyp, #cute, #viral ...) vote for nothing.
- Posts with no hashtag, or none that match, go to "Unsorted".
- With --caption-fallback, those leftover posts get a second try on their
  caption words: the same keyword lists, but each caption word must START WITH
  a keyword (so "cat" does not match "category"), and keywords with a space or
  non-Latin letters (e.g. 猫, 고양이) are looked for anywhere in the caption.
  Same voting and tie-break. Posts that still match nothing stay "Unsorted".
- Keeps every original column and adds three: category, matched_tags (the
  hashtags or caption words that decided it) and sorted_by (hashtags, caption,
  or empty for Unsorted).
- Writes one CSV per category (rows newest saved first), named
  {prefix}-NN-{category}.csv, split into -partN files when a category would be
  too big to upload in one go (see --max-rows).
- Writes results-log-{timestamp}.txt in the current folder every run, with
  separate lists for written, skipped, and errors, plus warnings.

Usage:
    uv run scripts/instagram/categorize_saved.py saved-posts-part1.csv saved-posts-part2.csv
    uv run scripts/instagram/categorize_saved.py saved-posts*.csv --outdir by-category --prefix ig-saved
    uv run scripts/instagram/categorize_saved.py saved-posts*.csv --max-rows 6000
    uv run scripts/instagram/categorize_saved.py saved-posts*.csv --caption-fallback   # also sort leftovers by caption words
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# (category name, [keywords]).  A keyword ending in "=" must equal the whole
# hashtag (without the #); any other keyword matches anywhere in the hashtag.
# Order matters: it is the tie-break (earlier wins).
CATEGORIES = [
    ("Politics and news", [
        "politic", "news", "america=", "epstein", "trump", "biden", "election", "government",
        "culturewar", "protest", "palestine", "israel", "ukraine", "immigration", "ice=",
        "history", "propaganda", "dystopian", "democracy", "capitalism", "communis",
        "socialis", "geopolitic", "military", "nato=", "congress", "senate", "maga=",
    ]),
    ("Tech, coding and privacy", [
        "coding", "programming", "programmer", "learntocode", "code=", "tech=", "technology",
        "cybersecurity", "privacy", "surveillance", "linux", "hacking", "hacker", "software",
        "developer", "networkengineer", "python", "javascript", "computerscience", "ai=",
        "chatgpt", "opensource", "devops", "selfhost", "infosec", "gadget", "robot",
    ]),
    ("Books, occult and esoteric", [
        "book", "literature", "dostoevsky", "plath", "lispector", "poetry", "poem", "novel",
        "occult", "esoter", "mystic", "witch", "tarot", "astrolog", "spiritual", "sufi",
        "orthodox", "philosoph", "catholic", "islam", "christian", "buddh", "religio",
        "goth=", "gothic", "vampire", "vamp=", "dark academia", "darkacademia", "horror",
        "macabre", "demon", "schizo", "occultism", "paganism", "satan", "esotericism",
    ]),
    ("Film, TV and music", [
        "movie", "film", "cinema", "cinephile", "scenepack", "netflix", "tvshow", "tvseries",
        "series=", "anime", "music", "song", "album", "concert", "soundtrack", "playlist",
        "rapper", "hiphop", "singer", "band=", "celebrity", "actor", "actress", "trailer",
        "pokemon", "kdrama", "disney", "marvel", "stranger things",
    ]),
    ("Art, design and math", [
        "art=", "artist", "artwork", "design", "illustration", "drawing", "painting",
        "sketch", "digitalart", "graphic", "typograph", "architect", "math", "physics",
        "science", "liminal", "backrooms", "creative", "photography=", "animation",
        "aesthetic", "museum", "sculpture", "craft", "diy=", "interior",
    ]),
    ("Fitness and lifestyle", [
        "fitness", "gym", "workout", "training", "fashion", "outfit", "beauty", "makeup",
        "skincare", "selfcare", "wellness", "yoga", "health", "relationship", "dating",
        "motivation", "lifestyle", "recipe", "food", "cooking", "foodie",
        "wedding", "hair", "nails", "style=", "ootd", "girly", "thrift", "home decor",
    ]),
    ("Memes and shitposts", [
        "meme", "shitpost", "brainrot", "relatable", "dankmemes", "humor", "humour",
        "comedy", "lol=", "lmao", "joke", "sketchcomedy", "cursed=", "unhinged", "satire",
        "ragebait", "trollface", "wojak", "skit",
    ]),
    ("Cats", [
        "cat=", "cats", "cat_", "_cat", "catlover", "catlife", "catstagram", "catsof", "cutecat",
        "catvid", "catoftheday", "catmom", "catdad", "catlady", "catlore", "catlove",
        "catreel", "catsagram", "catsgram", "catgram", "catphoto", "catto", "cattos",
        "kitty", "kitten", "kitties", "meow", "feline", "tabby", "tuxedo", "tuxie",
        "ginger", "orangecat", "blackcat", "siamese", "abyssinian", "abycat", "abykitten",
        "scottishfold", "britishshorthair", "britannia", "maine coon", "mainecoon",
        "ragdoll", "bengalcat", "sphynx", "persiancat", "americancurl", "siberiancat",
        "neko", "ねこ", "ネコ", "猫", "貓", "고양이", "냥", "캣", "야옹", "집사", "кот", "кошк", "gato",
        "katze", "chat=", "chats=", "floppa", "caturday", "purr", "loaf=", "chonk",
        "goob", "meimei", "peanutcat", "johnnythecat", "weirdcats", "aliencat",
        "crampcats", "diorebelcat", "cattomeme", "sillycat", "cursedcat", "adoptdontshop",
        "保護", "cutekitten", "babycat", "ilovemycat", "mycat", "orange_cat",
    ]),
    ("Bunnies and other animals", [
        "bunny", "bunnies", "rabbit", "うさぎ", "兔", "토끼", "ferret", "フェレット",
        "marten", "куниц", "kunitsa", "соболь", "sable=", "weasel", "squirrel", "ジリス",
        "リス=", "richardson", "netherlanddwarf", "fennec", "フェネック", "fox", "otter",
        "seal=", "seals=", "hamster", "guinea", "chicken", "chick=", "bird", "parrot",
        "duck", "goat", "sheep", "cow=", "pig=", "horse", "dog", "puppy", "pupper",
        "animal", "pet=", "pets", "petstagram", "wildlife", "zoo=", "hedgehog",
        "capybara", "raccoon", "possum", "opossum", "frog", "turtle", "tortoise",
        "reptile", "snake", "lizard", "gecko", "mouse=", "rat=", "mice=", "bat=", "bats=",
        "owl=", "deer", "bear=", "panda", "monkey", "lemur", "meerkat", "sloth", "koala",
        "norka", "норка", "хорек", "фретка", "ласка", "mink", "stoat", "ermine", "badger",
        "peanut=", "bunnylife", "bunnydaily", "hyrax", "小動物", "動物", "ペット", "반려",
    ]),
]
UNSORTED = "Unsorted"
SLUG_RE = re.compile(r"[^a-z0-9]+")


def tag_votes(tag):
    """Return the set of category names this hashtag votes for."""
    t = tag.lower().lstrip("#")
    out = set()
    for name, words in CATEGORIES:
        for w in words:
            if w.endswith("="):
                if t == w[:-1]:
                    out.add(name)
                    break
            elif w in t:
                out.add(name)
                break
    return out


def categorize(tags):
    """Pick one category for a list of hashtags. Returns (category, deciding tags)."""
    votes = Counter()
    by_cat = defaultdict(list)
    for tag in tags:
        for cat in tag_votes(tag):
            votes[cat] += 1
            by_cat[cat].append(tag)
    if not votes:
        return UNSORTED, []
    best = max(votes.values())
    for name, _ in CATEGORIES:  # tie-break by CATEGORIES order
        if votes.get(name) == best:
            return name, by_cat[name]
    return UNSORTED, []


WORD_RE = re.compile(r"[^\W_]+")


def caption_votes(word, text):
    """Categories a caption word votes for. Latin keywords must start the word;
    keywords with a space or non-Latin letters are searched in the whole caption."""
    out = set()
    for name, words in CATEGORIES:
        for w in words:
            if w.endswith("="):
                if word == w[:-1]:
                    out.add(name)
                    break
            elif w.isascii() and " " not in w and "_" not in w:
                if word.startswith(w):
                    out.add(name)
                    break
            elif not w.isascii() or " " in w:
                if w in text:
                    out.add(name)
                    break
    return out


def categorize_caption(caption):
    """Pick one category from caption words. Returns (category, deciding words)."""
    text = caption.lower()
    votes = Counter()
    by_cat = defaultdict(list)
    seen_words = set()
    for word in WORD_RE.findall(text):
        if word in seen_words:
            continue
        seen_words.add(word)
        for cat in caption_votes(word, text):
            votes[cat] += 1
            by_cat[cat].append(word)
    if not votes:
        return UNSORTED, []
    best = max(votes.values())
    for name, _ in CATEGORIES:
        if votes.get(name) == best:
            return name, by_cat[name]
    return UNSORTED, []


def main():
    ap = argparse.ArgumentParser(description="Sort Instagram saved posts into categories by hashtag")
    ap.add_argument("inputs", nargs="+", help="saved-posts CSV file(s) from saved_to_table.py")
    ap.add_argument("--outdir", default="by-category", help="folder for the per-category CSVs")
    ap.add_argument("--prefix", default="instagram-saved", help="file name prefix")
    ap.add_argument("--max-rows", type=int, default=6000,
                    help="split a category into parts above this many rows (default 6000)")
    ap.add_argument("--caption-fallback", action="store_true",
                    help="sort posts the hashtags could not place by their caption words")
    args = ap.parse_args()

    started = datetime.now()
    outdir = Path(args.outdir)
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    errors, warnings, skipped_dupes, written_files = [], [], [], []

    rows, fieldnames, seen = [], None, set()
    for p in args.inputs:
        try:
            with open(p, encoding="utf-8-sig", newline="") as f:
                rd = csv.DictReader(f)
                fieldnames = fieldnames or rd.fieldnames
                for r in rd:
                    key = r.get("shortcode") or r.get("post_url")
                    if key in seen:
                        skipped_dupes.append((r.get("post_url", "?"), f"duplicate of an earlier row (from {p})"))
                        continue
                    seen.add(key)
                    rows.append(r)
        except Exception as e:
            errors.append((p, f"could not read: {e}"))

    per_cat = defaultdict(list)
    for r in rows:
        try:
            tags = r.get("hashtags", "").split()
            cat, why = categorize(tags)
            by = "hashtags" if cat != UNSORTED else ""
            if cat == UNSORTED and args.caption_fallback:
                cat, why = categorize_caption(r.get("caption", ""))
                by = "caption" if cat != UNSORTED else ""
            r["category"] = cat
            r["matched_tags"] = " ".join(why)
            r["sorted_by"] = by
            per_cat[cat].append(r)
        except Exception as e:
            errors.append((r.get("post_url", "?"), f"could not categorize: {e}"))

    out_cols = (fieldnames or []) + ["category", "matched_tags", "sorted_by"]
    order = [n for n, _ in CATEGORIES] + [UNSORTED]
    total_written = 0
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append((str(outdir), f"could not create folder: {e}"))
    for i, cat in enumerate(order, 1):
        rs = sorted(per_cat.get(cat, []), key=lambda r: r.get("saved_at", ""), reverse=True)
        if not rs:
            warnings.append((cat, "no posts matched this category; no file written"))
            continue
        n = -(-len(rs) // args.max_rows)
        size = -(-len(rs) // n)
        slug = SLUG_RE.sub("-", cat.lower()).strip("-")
        for k in range(n):
            part = rs[k * size:(k + 1) * size]
            name = f"{args.prefix}-{i:02d}-{slug}" + (f"-part{k + 1}" if n > 1 else "") + ".csv"
            path = outdir / name
            try:
                with path.open("w", encoding="utf-8-sig", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
                    w.writeheader()
                    w.writerows(part)
                written_files.append((str(path), f"{cat}: {len(part)} posts"))
                total_written += len(part)
            except Exception as e:
                errors.append((str(path), f"could not write: {e}"))

    finished = datetime.now()
    lines = [
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S} (duration {(finished - started).total_seconds():.1f}s)",
        f"Input       : {', '.join(args.inputs)}",
        f"Output      : {outdir}/",
        "",
        "SUMMARY",
        f"  Total posts read                : {len(rows) + len(skipped_dupes)}",
        f"  Done this run (written)         : {total_written}",
        "  Already done (skipped)          : 0",
        f"  Skipped on purpose              : {len(skipped_dupes)}",
        f"  Errors                          : {len(errors)}",
        f"  Warnings                        : {len(warnings)}",
        "",
        "POSTS PER CATEGORY",
    ]
    for cat in order:
        lines.append(f"  {len(per_cat.get(cat, [])):6d}  {cat}")
    lines.append("")

    def section(title, items):
        lines.append(f"{title} ({len(items)})")
        if not items:
            lines.append("  (none)")
        for a, b in items:
            lines.append(f"  {a}")
            lines.append(f"      {b}")
        lines.append("")

    section("SUCCESSFUL: WRITTEN", written_files)
    section("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", [])
    section("SKIPPED ON PURPOSE: DUPLICATE POST", skipped_dupes)
    section("ERRORS", errors)
    section("WARNINGS", warnings)
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {total_written} posts to {len(written_files)} file(s) in {outdir}/")
    for cat in order:
        print(f"  {len(per_cat.get(cat, [])):6d}  {cat}")
    print(f"Results log: {log_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
