#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["markdown-it-py"]
# ///
"""
sort_notes.py - redistribute messy source notes into themed markdown files, losslessly.

What it does:
- build: reads every file in the input folder (skips __MACOSX), splits each into
  units (frontmatter, fenced code, heading, block), gives each a unit ID such as
  S07-L120-134, routes each unit to a theme file/section (ROUTES below), cleans only
  the presentation (markdown, escapes, HTML, bare URLs, glued bold, stray symbols),
  merges exact duplicates, and writes the theme files, 00-index.md, 97-appendix,
  _exclusions.md, _provenance.csv and _ledger.csv (original text kept untouched).
- verify: re-reads sources and outputs from disk and checks coverage, URLs, 4-word
  sequences (both directions), structure (TOC/index/cross-file links) and rendering
  (CommonMark parse). Writes _verification-report.md with one verdict per source.

Every run writes results-log-{YYYY-MM-DD_HHMMSS}.txt in the current folder (header,
SUMMARY, one list per outcome) and prints its path at the end.

Usage:
    uv run scripts/archive/sort_notes.py build  --input to-sort/ --output sorted-notes/
    uv run scripts/archive/sort_notes.py verify --input to-sort/ --output sorted-notes/
"""

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

csv.field_size_limit(10**9)

# ----------------------------------------------------------------------------
# Taxonomy: output files, their sections, and per-source routing
# ----------------------------------------------------------------------------

THEMES = {
    "01-indieweb-and-personal-websites.md": {
        "title": "Indieweb and Personal Websites",
        "description": "Personal-website pages, colophons, webrings, friends lists, profile handles and links saved from indieweb-style sites.",
        "concepts": ["personal websites", "webrings", "colophons", "social handles", "web ethics", "digital sovereignty"],
        "tags": ["indieweb", "personal-websites", "profiles", "clippings"],
        "sections": [
            "Handles and profile URLs",
            "Profiles and project links",
            "Friends, interests and online presence",
            "Website colophons and sitemaps",
        ],
    },
    "02-software-and-web-tools.md": {
        "title": "Software and Web Tools",
        "description": "Tool notes: chat clients, newsletter services, bookmarking alternatives, headless browsers, Puter.js, user agent strings, OpenDesktop and software licenses.",
        "concepts": ["software tools", "browser automation", "user agents", "bookmarking", "open source licenses", "hosting"],
        "tags": ["tools", "software", "web", "reference"],
        "sections": [
            "Pidgin and Adium on macOS",
            "Email newsletter services",
            "Pinboard alternatives and Pastebot",
            "Headless browsers, test automation and Puter.js",
            "User agent strings and random notes",
            "OpenDesktop and Opencode",
            "Spotify third-party licenses",
        ],
    },
    "03-ai-prompts-and-chat-exports.md": {
        "title": "AI Prompts and Chat Exports",
        "description": "Prompts written for LLMs, saved search prompts, chat export instructions and follow-up fragments from LLM conversations.",
        "concepts": ["LLM prompts", "prompt engineering", "chat export", "research questions", "Obsidian vault export"],
        "tags": ["ai", "prompts", "llm", "chat-exports"],
        "sections": [
            "Research index prompts",
            "Saved search prompts and topic lists",
            "Chat export prompts and follow-ups",
            "Title options and export notes",
        ],
    },
    "04-books-and-reading.md": {
        "title": "Books and Reading",
        "description": "Book recommendations, series searches, book price and tracking tools, literature collection indexes and an esoteric library thread.",
        "concepts": ["book recommendations", "Harvard Classics", "book price comparison", "book tracking apps", "esoteric libraries"],
        "tags": ["books", "reading", "literature", "clippings"],
        "sections": [
            "r/Fantasy book recommendations",
            "Harvard Classics search clipping",
            "Book price comparison, verification and tracking apps",
            "Literature collection index",
            "Esoteric library thread",
            "Federated bookshelves",
        ],
    },
    "05-history-art-and-folklore.md": {
        "title": "History, Art and Folklore",
        "description": "Historical maps, queens, cathedrals, religious origins, art history and museum image metadata.",
        "concepts": ["Fool's Cap map", "Boudicca", "Old St. Paul's Cathedral", "sex magic", "Georgia O'Keeffe", "Oppenheimer", "Familists"],
        "tags": ["history", "art", "folklore", "clippings"],
        "sections": [
            "Fool's Cap Map of the World",
            "Boudicca comments",
            "Old St. Paul's Cathedral",
            "The origin of going to church",
            "Georgia O'Keeffe and Oppenheimer",
            "Faust image metadata",
        ],
    },
    "06-imageboards-and-image-resources.md": {
        "title": "Imageboards and Image Resources",
        "description": "Booru and imageboard site lists, tag pages, emoji collections and image-search URLs.",
        "concepts": ["imageboards", "booru sites", "tag lists", "emoji", "reverse image search"],
        "tags": ["images", "imageboards", "emoji", "links"],
        "sections": [
            "lefty.pictures pages and tags",
            "Booru project sites",
            "Squirrel emojis",
            "Google Lens URL",
        ],
    },
    "07-social-media-captures.md": {
        "title": "Social Media Captures",
        "description": "A saved X (Twitter) thread with replies, relevant people and trending items.",
        "concepts": ["X thread", "replies", "trending"],
        "tags": ["social-media", "x", "twitter", "clippings"],
        "sections": ["X thread on alcohol and civilization"],
    },
    "08-search-clippings-and-reference-resources.md": {
        "title": "Search Clippings and Reference Resources",
        "description": "Saved search-engine result pages and AI overviews about language resources and a Flickr frontend search.",
        "concepts": ["language resources", "AI overview", "search results", "SerpApi", "Flickr frontend"],
        "tags": ["search", "reference", "clippings"],
        "sections": ["Global language resources search", "Flickr frontend search results"],
    },
    "09-link-collections-and-bookmarks.md": {
        "title": "Link Collections and Bookmarks",
        "description": "General links, a prompt library and loose notes saved as a link list.",
        "concepts": ["bookmarks", "prompt library", "link list"],
        "tags": ["links", "bookmarks"],
        "sections": ["General links, prompt library and notes"],
    },
    "99-miscellaneous.md": {
        "title": "Miscellaneous",
        "description": "Single stray items that fit no theme: an autogenerated Obsidian file index and an Obsidian Bases definition.",
        "concepts": ["Obsidian index", "Obsidian Bases"],
        "tags": ["miscellaneous", "obsidian"],
        "sections": ["Autogenerated index of the to-sort folder", "Research base definition"],
    },
}

F01, F02, F03, F04, F05, F06, F07, F08, F09, F99 = (
    "01-indieweb-and-personal-websites.md",
    "02-software-and-web-tools.md",
    "03-ai-prompts-and-chat-exports.md",
    "04-books-and-reading.md",
    "05-history-art-and-folklore.md",
    "06-imageboards-and-image-resources.md",
    "07-social-media-captures.md",
    "08-search-clippings-and-reference-resources.md",
    "09-link-collections-and-bookmarks.md",
    "99-miscellaneous.md",
)


def sec(fname, idx):
    return (fname, THEMES[fname]["sections"][idx])


# ROUTES: source file name -> list of (first_line, last_line or None, (dest file, section))
ROUTES = {
    "3 TweetDetail 11 items received.md": [(1, None, sec(F07, 0))],
    "completed searches.md": [(1, None, sec(F03, 1))],
    "Dec.6.25.md": [
        (1, 16, sec(F01, 0)),
        (17, 24, sec(F02, 0)),
        (25, 49, sec(F01, 1)),
        (50, 59, sec(F02, 1)),
        (60, 64, sec(F01, 1)),
        (65, 195, sec(F01, 2)),
        (196, 325, sec(F01, 3)),
        (326, 333, sec(F04, 5)),
        (334, None, sec(F02, 2)),
    ],
    "doc holliday llm prompt.md": [(1, None, sec(F03, 0))],
    "Fool's Cap World Map.md": [(1, None, sec(F05, 0))],
    "Fringechan Archive.md": [(1, None, sec(F04, 4))],
    "Georgia O'Keeffe and Oppenheimer.md": [(1, None, sec(F05, 4))],
    "Global Language Resources.md": [(1, None, sec(F08, 0))],
    "index \u2192 to-sort.md": [(1, None, sec(F99, 0))],
    "info.md": [(1, None, sec(F06, 0))],
    "lens by google.md": [(1, None, sec(F06, 3))],
    "Libre Cloud Services - OpenDesktop.org.md": [(1, None, sec(F02, 5))],
    "links.md": [(1, None, sec(F09, 0))],
    "Metadata.md": [(1, None, sec(F05, 5))],
    "new!!.md": [(1, 78, sec(F03, 2)), (79, None, sec(F02, 4))],
    "notes.md": [(1, None, sec(F04, 3))],
    "old-st-pauls.md": [(1, None, sec(F05, 2))],
    "Page Token.md": [(1, None, sec(F08, 1))],
    "Queen Bouddica.md": [(1, None, sec(F05, 1))],
    "r-Fantasy books.md": [(1, None, sec(F04, 0))],
    "research base.base": [(1, None, sec(F99, 1))],
    "Returns images from given page of booruproject.md": [(1, None, sec(F06, 1))],
    "Series Harvard Classics.md": [(1, None, sec(F04, 1))],
    "Squirrel Emojis.md": [(1, None, sec(F06, 2))],
    "summarizer.md": [
        (1, 62, sec(F02, 3)),
        (63, 83, sec(F03, 3)),
        (84, 174, sec(F04, 2)),
        (175, None, sec(F03, 3)),
    ],
    "the origin of going to church.md": [(1, None, sec(F05, 3))],
    "Third-party Licenses.md": [(1, None, sec(F02, 6))],
}

INDEX_BLURB = {
    "01-indieweb-and-personal-websites.md": "Personal-website colophons, webrings, friends lists, handles and profile links.",
    "02-software-and-web-tools.md": "Chat clients, newsletter services, bookmarking alternatives, headless browsers, Puter.js, user agent strings, OpenDesktop and licenses.",
    "03-ai-prompts-and-chat-exports.md": "LLM prompts, saved search prompts, chat export instructions and follow-up fragments.",
    "04-books-and-reading.md": "Book recommendations, Harvard Classics, price and tracking tools, literature indexes, esoteric library thread.",
    "05-history-art-and-folklore.md": "Fool's Cap map, Boudicca comments, Old St. Paul's, church origins, O'Keeffe and Oppenheimer, Faust image metadata.",
    "06-imageboards-and-image-resources.md": "Imageboard and booru site lists, lefty.pictures tag pages, squirrel emojis, Google Lens URL.",
    "07-social-media-captures.md": "A saved X thread with replies, relevant people and trending items.",
    "08-search-clippings-and-reference-resources.md": "Saved search results and AI overviews on language resources and a Flickr frontend.",
    "09-link-collections-and-bookmarks.md": "General links, prompt library and loose notes.",
    "97-appendix-other-urls.md": "URLs that appear only inside fenced code blocks, as clickable links, grouped by source.",
    "99-miscellaneous.md": "Stray items: an autogenerated Obsidian index and an Obsidian Bases definition.",
}

# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

ZERO_WIDTH = {"\u200b": "ZERO WIDTH SPACE", "\ufeff": "BOM / ZERO WIDTH NO-BREAK SPACE", "\ufffd": "REPLACEMENT CHARACTER",
              "\u00ad": "SOFT HYPHEN", "\u200e": "LEFT-TO-RIGHT MARK", "\u200f": "RIGHT-TO-LEFT MARK", "\u2060": "WORD JOINER"}
SPACE_LIKE = {"\u00a0": "NO-BREAK SPACE", "\u2009": "THIN SPACE", "\u202f": "NARROW NO-BREAK SPACE", "\u2002": "EN SPACE",
              "\u2003": "EM SPACE", "\u2007": "FIGURE SPACE", "\u200a": "HAIR SPACE", "\u3000": "IDEOGRAPHIC SPACE"}

URL_RE = re.compile(r"https?://[^\s<>\"\u201c\u201d\[\]]+")
TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?/?>")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})(?:\s+(.*?))?\s*#*\s*$")
HR_RE = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(?:\s+(.*))?$")
SCHEME_RE = r"[A-Za-z][A-Za-z0-9+.-]{1,31}:"
AUTOLINK_RE = re.compile(r"<" + SCHEME_RE + r"[^<>\s]*>")
LABEL_RE = re.compile(r"\*\((?:merged: \d+ copies|image-only, not captured)\)\*")


def trim_url(u):
    """Strip trailing punctuation from a bare URL (keeps balanced parentheses)."""
    while u:
        c = u[-1]
        if c in ".,;:!?'\u2019\u201d*_" or (c == ")" and u.count(")") > u.count("(")) or c == "}":
            u = u[:-1]
        else:
            break
    return u


def norm_url(u):
    u = html.unescape(u.strip())
    u = u.strip("<>")
    u = trim_url(u)
    u = re.sub(r"\\([_*\[\]()<>#!.\-~`>])", r"\1", u)
    return u


def find_close_bracket(s, i):
    depth = 0
    j = i
    n = len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            m = re.match(r"`+", s[j:])
            run = m.group()
            k = s.find(run, j + len(run))
            if k != -1:
                j = k + len(run)
                continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def contains_link(inner):
    """True if inner text holds a non-image link [..](..) (links cannot nest)."""
    for m in re.finditer(r"\[", inner):
        if m.start() and inner[m.start() - 1] == "!":
            continue
        j = find_close_bracket(inner, m.start())
        if j != -1 and j + 1 < len(inner) and inner[j + 1] == "(" and parse_dest(inner, j + 1):
            return True
    return False


def parse_dest(s, j):
    """s[j] == '('. Returns (end_after_close_paren, dest, title) or None."""
    n = len(s)
    k = j + 1
    while k < n and s[k] in " \t\n":
        k += 1
    if k < n and s[k] == "<":
        e = s.find(">", k)
        if e == -1:
            return None
        dest = s[k + 1:e]
        k = e + 1
    else:
        depth = 0
        st = k
        while k < n:
            c = s[k]
            if c == "\\":
                k += 2
                continue
            if c in " \t\n":
                break
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    break
                depth -= 1
            k += 1
        dest = s[st:k]
    while k < n and s[k] in " \t\n":
        k += 1
    title = ""
    if k < n and s[k] in "\"'(":
        q = s[k]
        close = ")" if q == "(" else q
        e = k + 1
        while e < n and s[e] != close:
            if s[e] == "\\":
                e += 1
            e += 1
        if e >= n:
            return None
        title = s[k:e + 1]
        k = e + 1
        while k < n and s[k] in " \t\n":
            k += 1
    if k < n and s[k] == ")":
        return k + 1, dest, title
    return None


def strip_link_dests(text):
    """Remove (destination "title") after ] for tokenisation; keeps link text."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "]" and i + 1 < n and text[i + 1] == "(":
            r = parse_dest(text, i + 1)
            if r:
                out.append("]")
                i = r[0]
                continue
        out.append(c)
        i += 1
    return "".join(out)


def tokens(text):
    """Tokenise for the 4-gram checks: strip HTML, link destinations, URLs, markdown, escapes."""
    text = html.unescape(text)
    text = COMMENT_RE.sub(" ", text)
    text = AUTOLINK_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"\[([^\[\]\n]+)\]\(\1\)", " ", text)
    text = strip_link_dests(text)
    text = URL_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = LABEL_RE.sub(" ", text)
    return re.findall(r"[^\W_]+", text.casefold())


def ngrams(toks, n=4):
    return [tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)]


def slugify(text):
    """GitHub-style heading slug (without duplicate suffix)."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    t = t.lower()
    t = re.sub(r"[^\w\- ]", "", t, flags=re.UNICODE)
    return t.replace(" ", "-")


def heading_slugs(lines):
    """Return list of (level, text, slug) for ATX headings outside fences, with dedupe suffixes."""
    seen = Counter()
    out = []
    in_fence = None
    for ln in lines:
        m = FENCE_OPEN.match(ln)
        if in_fence:
            if m and m.group(2)[0] == in_fence[0] and len(m.group(2)) >= len(in_fence) and not m.group(3).strip():
                in_fence = None
            continue
        if m:
            in_fence = m.group(2)
            continue
        h = HEADING_RE.match(ln)
        if h and h.group(2) is not None and h.group(2).strip():
            text = h.group(2).strip()
            base = slugify(text)
            k = seen[base]
            seen[base] += 1
            out.append((len(h.group(1)), text, base if k == 0 else f"{base}-{k}"))
    return out


# ----------------------------------------------------------------------------
# Segmentation
# ----------------------------------------------------------------------------

def bracket_depth_after(lines):
    s = "\n".join(lines)
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            m = re.match(r"`+", s[i:])
            run = m.group()
            k = s.find(run, i + len(run))
            if k != -1:
                i = k + len(run)
                continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth = max(0, depth - 1) if depth > 0 else 0
        i += 1
    return depth


def segment(lines):
    """Split a file's lines into units: dicts with start, end (1-based, inclusive), type, lines."""
    units = []
    n = len(lines)
    i = 0
    cur = []
    cur_start = None

    def flush():
        nonlocal cur, cur_start
        if cur:
            units.append({"start": cur_start, "end": cur_start + len(cur) - 1, "type": "block", "lines": cur})
        cur, cur_start = [], None

    # frontmatter
    if n and lines[0].strip() == "---":
        for j in range(1, min(n, 400)):
            if lines[j].strip() == "---":
                units.append({"start": 1, "end": j + 1, "type": "frontmatter", "lines": lines[:j + 1]})
                i = j + 1
                break
    while i < n:
        ln = lines[i]
        fm = FENCE_OPEN.match(ln)
        if fm and not (fm.group(2)[0] == "`" and "`" in fm.group(3)):
            flush()
            ch, ln_len = fm.group(2)[0], len(fm.group(2))
            j = i + 1
            closed = False
            while j < n:
                cm = FENCE_OPEN.match(lines[j])
                if cm and cm.group(2)[0] == ch and len(cm.group(2)) >= ln_len and not cm.group(3).strip():
                    closed = True
                    break
                j += 1
            end = j if closed else n - 1
            units.append({"start": i + 1, "end": end + 1, "type": "fence", "lines": lines[i:end + 1], "closed": closed})
            i = end + 1
            continue
        if not ln.strip():
            # blank line: absorb it if we are inside an unclosed [ ... ]( ) link that closes soon
            if cur and bracket_depth_after(cur) > 0:
                k = i
                probe = list(cur)
                ok = False
                while k < n and k < i + 14:
                    if FENCE_OPEN.match(lines[k]) or HEADING_RE.match(lines[k]) and lines[k].lstrip().startswith("#"):
                        break
                    probe.append(lines[k])
                    if bracket_depth_after(probe) == 0:
                        ok = True
                        break
                    k += 1
                if ok:
                    cur.extend(lines[i:k + 1])
                    i = k + 1
                    continue
            flush()
            i += 1
            continue
        if HEADING_RE.match(ln) and ln.lstrip().startswith("#"):
            flush()
            units.append({"start": i + 1, "end": i + 1, "type": "heading", "lines": [ln]})
            i += 1
            continue
        if HR_RE.match(ln):
            flush()
            units.append({"start": i + 1, "end": i + 1, "type": "hr", "lines": [ln]})
            i += 1
            continue
        if not cur:
            cur_start = i + 1
        cur.append(ln)
        i += 1
    flush()
    return units


# ----------------------------------------------------------------------------
# Cleaning
# ----------------------------------------------------------------------------

class Stats:
    """Counts of removed/changed syntax with a few examples each, for _exclusions.md."""

    def __init__(self):
        self.c = Counter()
        self.ex = defaultdict(list)

    def add(self, key, example=None, n=1):
        self.c[key] += n
        if example is not None and len(self.ex[key]) < 3 and example not in self.ex[key]:
            self.ex[key].append(example if len(example) < 140 else example[:137] + "...")


class UnitCtx:
    def __init__(self, stats):
        self.stats = stats
        self.image_only = 0
        self.thumbs = []


class HtmlToMd(HTMLParser):
    """Converts an HTML fragment to markdown-ish text; counts removed tags."""

    BLOCK = {"p", "div", "li", "ul", "ol", "tr", "table", "tbody", "thead", "main", "section", "article", "h1", "h2",
             "h3", "h4", "h5", "h6", "blockquote", "pre", "header", "footer", "nav", "dl", "dt", "dd"}

    def __init__(self, stats):
        super().__init__(convert_charrefs=True)
        self.stats = stats
        self.parts = []
        self.href = None
        self.link_buf = None
        self.table = None  # list of rows
        self.row = None
        self.cell = None

    def _emit(self, s):
        if self.cell is not None:
            self.cell.append(s)
        elif self.link_buf is not None:
            self.link_buf.append(s)
        else:
            self.parts.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stats.add(f"HTML tag removed: {tag}", f"<{tag}>")
        if tag == "a" and a.get("href"):
            self.href = a["href"]
            self.link_buf = []
        elif tag == "iframe" and a.get("src"):
            self._emit(f"\n\n<{html.unescape(a['src'])}>\n\n")
        elif tag == "img" and a.get("src"):
            alt = a.get("alt", "")
            self._emit(f"![{alt}]({a['src']})")
        elif tag == "br":
            self._emit("\n")
        elif tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag in self.BLOCK:
            self._emit("\n\n")

    def handle_endtag(self, tag):
        if tag == "a" and self.link_buf is not None:
            text = " ".join("".join(self.link_buf).split())
            buf = self.link_buf
            href = self.href
            self.link_buf = None
            self.href = None
            self._emit(f"[{text}]({href})" if text else f"<{href}>")
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if r]
            if rows:
                w = max(len(r) for r in rows)
                lines = ["| " + " | ".join([""] * w) + " |", "|" + "---|" * w]
                for r in rows:
                    r = [c.replace("|", "\\|") for c in r] + [""] * (w - len(r))
                    lines.append("| " + " | ".join(r) + " |")
                self.parts.append("\n\n" + "\n".join(lines) + "\n\n")
            self.table = None
        elif tag in self.BLOCK:
            self._emit("\n\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self._emit(data)

    def result(self):
        return "".join(self.parts)


def html_to_md(text, stats):
    p = HtmlToMd(stats)
    p.feed(text)
    p.close()
    return p.result()


def clean_chars(text, stats):
    out = []
    for ch in text:
        if ch in ZERO_WIDTH:
            stats.add(f"Invisible character removed: {ZERO_WIDTH[ch]}", repr(ch))
            continue
        if ch in SPACE_LIKE:
            stats.add(f"Space-like character replaced by a space: {SPACE_LIKE[ch]}", repr(ch))
            out.append(" ")
            continue
        out.append(ch)
    text = "".join(out)

    def strike(m):
        stats.add("Combining strikethrough U+0336 converted to markdown strikethrough", m.group(0).replace("\u0336", ""))
        return "~~" + m.group(0).replace("\u0336", "").strip() + "~~"

    text = re.sub(r"(?:[^\n\u0336]\u0336)+", strike, text)
    if re.search(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);", text):
        stats.add("HTML entity decoded", re.search(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);", text).group(0),
                  len(re.findall(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);", text)))
        text = html.unescape(text)
    def wl(m):
        stats.add("Wikilink double brackets removed (text kept)", m.group(0))
        return m.group(1)
    text = re.sub(r"\[\[([^\[\]\n]*)\]\]", wl, text)
    def obs(m):
        stats.add("Obsidian percent-percent comment markers removed (text kept)", m.group(0))
        return m.group(1)
    text = re.sub(r"%%\s?(.*?)\s?%%", obs, text)
    return text


def collapse_multiline_links(text):
    """Join link text that spans several lines onto one line."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == "`":
            m = re.match(r"`+", text[i:])
            run = m.group()
            k = text.find(run, i + len(run))
            if k != -1:
                out.append(text[i:k + len(run)])
                i = k + len(run)
                continue
        if c == "[":
            j = find_close_bracket(text, i)
            if j != -1 and j + 1 < n and text[j + 1] == "(" and "\n" in text[i:j]:
                inner = collapse_multiline_links(text[i + 1:j])
                inner = " ".join(inner.split())
                out.append("[" + inner + "]")
                i = j + 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def emit_dest(dest):
    d = dest
    if d == "":
        return d
    if re.search(r"[\s<>]", d) or d.count("(") != d.count(")"):
        d = "<" + d.replace("<", "%3C").replace(">", "%3E") + ">"
    return d


def inline_clean(s, ctx, in_link=False):
    """Clean one chunk of inline markdown: autolink bare URLs, convert images, escape lone brackets."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            out.append(s[i:i + 2])
            i += 2
            continue
        if c == "`":
            m = re.match(r"`+", s[i:])
            run = m.group()
            k = s.find(run, i + len(run))
            if k != -1:
                out.append(s[i:k + len(run)])
                i = k + len(run)
                continue
            out.append(s[i:i + len(run)])
            i += len(run)
            continue
        is_img = c == "!" and i + 1 < n and s[i + 1] == "["
        if c == "[" or is_img:
            b = i + 1 if is_img else i
            j = find_close_bracket(s, b)
            if j != -1 and j + 1 < n and s[j + 1] == "(" and (is_img or not contains_link(s[b + 1:j])):
                r = parse_dest(s, j + 1)
                if r:
                    end, dest, title = r
                    inner_raw = s[b + 1:j]
                    dest_n = dest
                    if is_img:
                        alt = " ".join(inline_clean(inner_raw, ctx, True).split())
                        if in_link:
                            ctx.thumbs.append(dest_n)
                            if not alt.strip():
                                ctx.image_only += 1
                            out.append(alt)
                        else:
                            if alt.strip():
                                out.append(f"[{alt}]({emit_dest(dest_n)}{(' ' + title) if title else ''})")
                            else:
                                out.append(f"<{dest_n}> *(image-only, not captured)*")
                                ctx.image_only += 1
                        ctx.stats.add("Image syntax converted to a link", f"![{inner_raw}]({dest_n[:60]})")
                    else:
                        saved = ctx.thumbs
                        ctx.thumbs = []
                        text = " ".join(inline_clean(inner_raw, ctx, True).split())
                        thumbs = ctx.thumbs
                        ctx.thumbs = saved
                        absolute = re.match(SCHEME_RE, dest_n)
                        if text.strip():
                            piece = f"[{text}]({emit_dest(dest_n)}{(' ' + title) if title else ''})"
                        elif absolute:
                            ctx.stats.add("Empty-text link converted to an autolink", f"[]({dest_n[:60]})")
                            piece = f"<{dest_n}>"
                        else:
                            ctx.stats.add("Empty-text link converted to a titled link", f"[]({dest_n[:60]})")
                            piece = f"[{dest_n}]({emit_dest(dest_n)})"
                        for t in thumbs:
                            piece += f" <{t}>" if re.match(SCHEME_RE, t) else f" [{t}]({emit_dest(t)})"
                        if thumbs and not text.strip():
                            piece += " *(image-only, not captured)*"
                        out.append(piece)
                    i = end
                    continue
            if is_img:
                out.append("!")
                i += 1
                continue
            out.append("\\[")
            ctx.stats.add("Lone opening square bracket escaped", s[max(0, i - 15):i + 25])
            i += 1
            continue
        if c == "]":
            if i + 1 < n and s[i + 1] == "(":
                r = parse_dest(s, i + 1)
                if r:
                    d = r[1]
                    ctx.stats.add("Orphan link syntax converted to an autolink", s[max(0, i - 15):i + 40])
                    out.append(f"<{d}>" if re.match(SCHEME_RE, d) else f"[{d}]({emit_dest(d)})")
                    i = r[0]
                    continue
            out.append("\\]")
            ctx.stats.add("Lone closing square bracket escaped", s[max(0, i - 25):i + 15])
            i += 1
            continue
        if c == "<":
            m = AUTOLINK_RE.match(s, i)
            if m:
                out.append(m.group(0))
                i += len(m.group(0))
                continue
        if c == "h" and not in_link and (s.startswith("http://", i) or s.startswith("https://", i)):
            prev = s[i - 1] if i else " "
            if not prev.isalnum():
                m = URL_RE.match(s, i)
                if m:
                    url = trim_url(m.group(0))
                    out.append(f"<{url}>")
                    ctx.stats.add("Bare URL converted to an angle-bracket autolink", url)
                    i += len(url)
                    continue
        out.append(c)
        i += 1
    return "".join(out)


def is_pure_link(line):
    """Return (text, dest) if the whole line is one link or one autolink, else None."""
    line = line.strip()
    m = re.fullmatch(r"<(" + SCHEME_RE + r"[^<>\s]*)>", line)
    if m:
        return "", m.group(1)
    if line.startswith("["):
        j = find_close_bracket(line, 0)
        if j != -1 and j + 1 < len(line) and line[j + 1] == "(":
            r = parse_dest(line, j + 1)
            if r and r[0] == len(line):
                return line[1:j], r[1]
    return None


def links_to_table(items):
    rows = []
    for it in items:
        text, dest = is_pure_link(it)
        text = text.replace("|", "\\|")
        if text and re.match(r"https?://", text) and text.rstrip("/") == dest.rstrip("/"):
            text = ""
        elif text and re.match(r"https?://", text):
            text = f"[{text}]({emit_dest(dest)})"
        rows.append(f"| {text} | <{dest}> |" if re.match(SCHEME_RE, dest) else f"| {text} | [{dest}]({emit_dest(dest)}) |")
    return ["| Title | URL |", "|---|---|"] + rows


def classify(line, prev):
    if not line.strip():
        return "blank"
    if re.match(r"^\s*\|", line):
        return "table"
    if re.match(r"^\s{0,3}>", line):
        return "quote"
    if LIST_RE.match(line) and (LIST_RE.match(line).group(3) is not None or line.strip() in ("-", "*", "+")):
        return "list"
    if prev == "list" and re.match(r"^\s{2,}\S", line):
        return "list"
    return "plain"


def clean_text_block(raw, ctx):
    """Clean a non-fence, non-frontmatter, non-heading block; return list of output lines (blank-separated pieces)."""
    stats = ctx.stats
    text = clean_chars(raw, stats)
    if re.search(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?/?>", COMMENT_RE.sub("", text)) and not re.search(r"^\s*`{3}", text, re.M):
        if COMMENT_RE.search(text):
            stats.add("HTML comment removed", COMMENT_RE.search(text).group(0)[:80])
            text = COMMENT_RE.sub("", text)
        text = html_to_md(text, stats)
    elif COMMENT_RE.search(text):
        stats.add("HTML comment removed", COMMENT_RE.search(text).group(0)[:80])
        text = COMMENT_RE.sub("", text)
    text = collapse_multiline_links(text)
    lines = text.split("\n")
    # group into segments
    segs = []
    prev = "blank"
    for ln in lines:
        k = classify(ln, prev)
        if k == "blank":
            prev = "blank"
            continue
        if segs and segs[-1][0] == k and prev != "blank":
            segs[-1][1].append(ln)
        elif segs and segs[-1][0] == k and prev == "blank" and k in ("plain",):
            segs.append([k, [ln]])
        elif segs and segs[-1][0] == k and prev == "blank":
            segs[-1][1].append(ln)
        else:
            segs.append([k, [ln]])
        prev = k
    # sub-split html-converted output: blank-separated plain paragraphs become separate segs automatically
    pieces = []
    for kind, ls in segs:
        if kind == "table":
            outl = []
            for ln in ls:
                ln = ln.rstrip()
                if ln != ln.rstrip(" "):
                    pass
                outl.append(inline_clean(ln.strip(), ctx))
            pieces.append(outl)
        elif kind == "quote":
            outl = []
            for ln in ls:
                body = re.sub(r"^\s{0,3}>\s?", "", ln).rstrip()
                outl.append("> " + inline_clean(body, ctx) if body.strip() else ">")
            pieces.append(outl)
        elif kind == "list":
            outl = []
            items = []
            for ln in ls:
                if ln.rstrip() != ln:
                    stats.add("Trailing whitespace / double-space line break removed", repr(ln[-6:]))
                ln = ln.expandtabs(4).rstrip()
                m = LIST_RE.match(ln)
                if m and (m.group(3) is not None):
                    indent, marker, body = m.group(1), m.group(2), m.group(3)
                    if marker in ("*", "+"):
                        stats.add("List marker normalised to a hyphen", marker)
                        marker = "-"
                    body = inline_clean(" ".join(body.split()), ctx)
                    if not body.strip():
                        stats.add("Empty list item removed", ln)
                        continue
                    outl.append(f"{indent}{marker} {body}")
                    items.append((indent, body))
                elif m:
                    stats.add("Empty list item removed", ln)
                else:
                    body = inline_clean(" ".join(ln.split()), ctx)
                    if body.strip():
                        outl.append(("  " + body) if outl else body)
            if outl and len(outl) == len(items) and len(items) >= 3 and all(i == "" for i, _ in items) and all(
                    is_pure_link(b) for _, b in items):
                outl = links_to_table([b for _, b in items])
                stats.add("Link list converted to a Title | URL table", None)
            if outl:
                pieces.append(outl)
        else:
            cleaned = []
            for ln in ls:
                if ln.rstrip() != ln:
                    stats.add("Trailing whitespace / double-space line break removed", repr(ln[-6:]))
                ln = " ".join(ln.split())
                ln = inline_clean(ln, ctx)
                ln2 = re.sub(r"^\*{3,}\s*(.*?)\s*\*{3,}$", r"\1", ln.strip()) if re.match(r"^\*{3,}\s+\S", ln.strip()) else ln
                if ln2 != ln:
                    stats.add("Stray * decoration removed", ln)
                    ln = ln2

                def _bold(m):
                    inner = m.group(1).strip()
                    if not inner:
                        return m.group(0)
                    return "**" + inner + "**" + (" " + m.group(2) if m.group(2) else "")

                if re.search(r"\*\*[^\w\s*]+\*\*", ln):
                    stats.add("Bold marks around punctuation only removed", re.search(r"\*\*[^\w\s*]+\*\*", ln).group(0))
                    ln = re.sub(r"\*\*([^\w\s*]+)\*\*", r"\1", ln)
                ln = re.sub(r"\*\*([^*\n]+?)\*\*([A-Za-z0-9]?)", _bold, ln)
                if re.fullmatch(r"\**", ln.strip()):
                    if ln.strip():
                        stats.add("Stray * removed", ln)
                    continue
                if ln.strip():
                    cleaned.append(ln)
            if not cleaned:
                continue
            if len(cleaned) == 1:
                pieces.append(cleaned)
            elif any("-->" in c for c in cleaned):
                pieces.append([" ".join(cleaned)])
            elif all(is_pure_link(c) for c in cleaned) and len(cleaned) >= 3:
                pieces.append(links_to_table(cleaned))
                stats.add("Link lines converted to a Title | URL table", None)
            else:
                stats.add("Plain multi-line block converted to a bullet list", None)
                pieces.append(["- " + c for c in cleaned])
    return pieces


def clean_unit(unit, ctx):
    """Return (cleaned_text or '', exclusion_reason or None)."""
    stats = ctx.stats
    t = unit["type"]
    lines = unit["lines"]
    if t == "hr":
        stats.add("Thematic break line removed (no text)", lines[0].strip())
        return "", "markdown separator line (no text content)"
    if t == "frontmatter":
        stats.add("YAML frontmatter delimiters removed; fields shown as a bullet list", None)
        out = []
        for ln in lines[1:-1]:
            if not ln.strip():
                continue
            ln = clean_chars(ln, stats).rstrip()
            indent = len(ln) - len(ln.lstrip())
            body = ln.strip()
            if body.startswith("- "):
                body = body[2:]
            out.append(" " * indent + "- " + inline_clean(body, ctx))
        return "\n".join(out), None
    if t == "fence":
        ind = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
        body = [l[ind:] if l.strip() else "" for l in lines]
        for ln in lines:
            if ln != ln.rstrip() and False:
                pass
        if not unit.get("closed", True):
            stats.add("Unclosed code fence closed at end of file", lines[0].strip())
            fm = FENCE_OPEN.match(body[0])
            body.append(fm.group(2))
        if len(body) == 2:
            return "", "empty code fence"
        return "\n".join(body), None
    if t == "heading":
        raw = clean_chars(lines[0], stats)
        m = HEADING_RE.match(raw)
        txt = (m.group(2) or "").strip()
        if not txt:
            stats.add("Empty heading marker removed", lines[0].strip())
            return "", "empty heading (marker only, no text)"
        lvl = min(6, len(m.group(1)) + 3)
        txt = " ".join(collapse_multiline_links(txt).split())
        return "#" * lvl + " " + inline_clean(txt, ctx), None
    # block
    pieces = clean_text_block("\n".join(lines), ctx)
    text = "\n\n".join("\n".join(p) for p in pieces if p)
    return text, None


def meaningful(text):
    for ch in text:
        if ch.isalnum():
            return True
        if ord(ch) > 127 and unicodedata.category(ch) in ("So", "Sk"):
            return True
    return False


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

def route_for(source, line):
    for lo, hi, dest in ROUTES[source]:
        if line >= lo and (hi is None or line <= hi):
            return dest
    raise KeyError((source, line))


def collect_urls(text):
    urls = set()
    t = html.unescape(text)
    i = 0
    while True:
        i = t.find("](", i)
        if i == -1:
            break
        r = parse_dest(t, i + 1)
        if r and r[1].strip():
            urls.add(norm_url(r[1]))
        i += 2
    for m in AUTOLINK_RE.finditer(t):
        urls.add(norm_url(m.group(0)))
    for m in re.finditer(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", t):
        urls.add(norm_url(m.group(1)))
    for m in URL_RE.finditer(strip_link_dests(t)):
        urls.add(norm_url(m.group(0)))
    urls.discard("")
    return urls


def image_urls(text):
    t = html.unescape(text)
    urls = set()
    for m in re.finditer(r"!\[", t):
        j = find_close_bracket(t, m.start() + 1)
        if j != -1 and j + 1 < len(t) and t[j + 1] == "(":
            r = parse_dest(t, j + 1)
            if r:
                urls.add(norm_url(r[1]))
    for m in re.finditer(r"""<img[^>]*\bsrc\s*=\s*["']([^"']+)["']""", t):
        urls.add(norm_url(m.group(1)))
    return urls


def source_files(inp):
    files = [p for p in Path(inp).iterdir() if p.is_file() and not p.name.startswith("._")]
    return sorted(files, key=lambda p: p.name.casefold())


def read_source(p):
    raw = p.read_bytes()
    text = raw.decode("utf-8")  # strict: fails loudly if unreadable
    text = text.replace("\r\n", "\n")
    return raw, text


def md_escape_cell(s):
    return s.replace("|", "\\|")


def write_log(path, kind, started, inp, outp, summary, lists):
    finished = datetime.now()
    dur = finished - started
    L = []
    L.append(f"sort_notes.py {kind} - results log")
    L.append(f"Run started : {started:%Y-%m-%d %H:%M:%S}")
    L.append(f"Run finished: {finished:%Y-%m-%d %H:%M:%S} (duration {dur.total_seconds():.1f}s)")
    L.append(f"Input       : {inp}")
    L.append(f"Output      : {outp}")
    L.append("")
    L.append("SUMMARY")
    for k, v in summary:
        L.append(f"  {k:<34}{v}")
    L.append("")
    for title, items in lists:
        L.append(f"{title} ({len(items)})")
        if not items:
            L.append("  (none)")
        for item, detail in items:
            L.append(f"  {item}")
            if detail:
                L.append(f"      {detail}")
        L.append("")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


def build(inp, outp):
    started = datetime.now()
    inp, outp = Path(inp), Path(outp)
    outp.mkdir(parents=True, exist_ok=True)
    files = source_files(inp)
    errors, warnings = [], []
    stats_by_source = {}
    ledger = []
    manifest = []
    seen_orig = {}  # (dest file, original text) -> ledger index of first occurrence
    for sn, p in enumerate(files, 1):
        try:
            raw, text = read_source(p)
        except Exception as e:  # noqa: BLE001
            errors.append((p.name, f"unreadable: {e}"))
            continue
        if p.name not in ROUTES:
            errors.append((p.name, "no route defined"))
            continue
        lines = text.split("\n")
        if lines and lines[-1] == "" and text.endswith("\n"):
            lines_for_seg = lines[:-1]
        else:
            lines_for_seg = lines
        stats = Stats()
        stats_by_source[p.name] = stats
        units = segment(lines_for_seg)
        covered = sum(u["end"] - u["start"] + 1 for u in units)
        blank = sum(1 for l in lines_for_seg if not l.strip())
        manifest.append({
            "source": p.name, "sn": sn, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()[:16],
            "lines": len(lines_for_seg), "words": len(text.split()), "urls": len(collect_urls(text)),
            "image_urls": len(image_urls(text)), "units": len(units), "blank_lines": blank,
            "covered_nonblank_lines": covered,
        })
        for u in units:
            uid = f"S{sn:02d}-L{u['start']}-{u['end']}"
            original = "\n".join(u["lines"])
            dest = route_for(p.name, u["start"])
            if route_for(p.name, u["end"]) != dest:
                warnings.append((uid, f"unit spans a route boundary; assigned to {dest[1]} by its first line"))
            ctx = UnitCtx(stats)
            cleaned, excl = clean_unit(u, ctx)
            if excl is None and not cleaned.strip():
                excl = "no content after cleaning"
            if excl is None and u["type"] not in ("fence", "frontmatter") and not meaningful(cleaned) and not re.search(r"(?:https?://|mailto:)", cleaned):
                excl = "stray symbols only (no words, URLs or emoji)"
                stats.add("Stray-symbol-only unit removed", original.strip()[:40])
            urls = sorted(collect_urls(original))
            rec = {
                "id": uid, "source": p.name, "start": u["start"], "end": u["end"], "type": u["type"],
                "original_text": original, "urls": json.dumps(urls, ensure_ascii=False),
                "dest_file": dest[0], "dest_section": dest[1], "cleaned_text": cleaned,
                "status": "kept", "note": "", "image_only": ctx.image_only, "merged_copies": 1,
            }
            if excl:
                rec.update(status="excluded", note=excl, dest_file="", dest_section="", cleaned_text="")
            else:
                mergeable = u["type"] in ("block", "fence") and (len(tokens(original)) >= 3 or urls)
                key = (dest[0], original.strip())
                if mergeable and key in seen_orig:
                    first = ledger[seen_orig[key]]
                    first["merged_copies"] += 1
                    rec.update(status="merged", note=f"exact duplicate of {first['id']}")
                else:
                    if mergeable:
                        seen_orig[key] = len(ledger)
            ledger.append(rec)

    # ----- assemble theme files
    by_file = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in ledger:
        if r["status"] == "kept":
            by_file[r["dest_file"]][r["dest_section"]][r["source"]].append(r)

    src_order = [p.name for p in files]
    file_sources = {}
    written = {}
    sections_of = {}
    for fname, meta in THEMES.items():
        body = []
        used = set()
        sec_list = []
        for si, sname in enumerate(meta["sections"], 1):
            srcs = by_file[fname][sname]
            if not srcs:
                warnings.append((fname, f"section '{sname}' has no units"))
                continue
            body.append(f"## {si}. {sname}")
            body.append("")
            sec_list.append((si, sname, []))
            for ki, sname_src in enumerate([s for s in src_order if s in srcs], 1):
                used.add(sname_src)
                body.append(f"### {si}.{ki} From: {sname_src}")
                body.append("")
                sec_list[-1][2].append((f"{si}.{ki}", f"From: {sname_src}"))
                for r in srcs[sname_src]:
                    txt = r["cleaned_text"]
                    body.append(txt)
                    if r["merged_copies"] > 1:
                        body.append("")
                        body.append(f"*(merged: {r['merged_copies']} copies)*")
                    body.append("")
        file_sources[fname] = [s for s in src_order if s in used]
        written[fname] = (body, sec_list)
        sections_of[fname] = sec_list

    # 97 appendix: URLs found only inside fenced code blocks
    app_rows = defaultdict(list)
    for r in ledger:
        if r["status"] == "kept" and r["type"] == "fence":
            for m in URL_RE.finditer(html.unescape(r["original_text"])):
                u = trim_url(m.group(0))
                app_rows[r["source"]].append((u, r["id"]))
    for r in ledger:
        if r["status"] == "kept" and r["type"] == "fence":
            pass
    appendix_body = []
    if app_rows:
        for src in src_order:
            if src in app_rows:
                appendix_body.append(f"## {src}")
                appendix_body.append("")
                appendix_body.append("URLs that appear inside fenced code blocks, where they are kept verbatim and not clickable. Listed again here as links.")
                appendix_body.append("")
                appendix_body.append("| URL | Unit |")
                appendix_body.append("|---|---|")
                seen_rows = set()
                for u, uid in app_rows[src]:
                    if (u, uid) in seen_rows:
                        continue
                    seen_rows.add((u, uid))
                    appendix_body.append(f"| <{u}> | {uid} |")
                appendix_body.append("")
    else:
        appendix_body = ["No URLs found outside units. Every URL travels with its unit.", ""]

    # slugs and TOC
    final_text = {}
    slug_maps = {}

    def assemble(fname, body, sec_list, meta, sources, extra_sections=None):
        # compute heading slugs from the headings in order: H1 title, '## Contents', body headings
        head = [f"# {meta['title']}", "", "## Contents", ""]
        probe_lines = head + body
        slugs = heading_slugs(probe_lines)
        by_text = {(lvl, text): slug for lvl, text, slug in slugs}
        toc = []
        for si, sname, subs in sec_list:
            toc.append(f"{si}. [{si}. {sname}](#{by_text[(2, f'{si}. {sname}')]})")
            for num, label in subs:
                toc.append(f"    {num.split('.')[1]}. [{num} {label}](#{by_text[(3, f'{num} {label}')]})")
        return head, toc, slugs

    outputs = {}
    slug_lookup = {}
    for fname, meta in THEMES.items():
        body, sec_list = written[fname]
        head, toc, slugs = assemble(fname, body, sec_list, meta, file_sources[fname])
        slug_lookup[fname] = {text: slug for lvl, text, slug in slugs if lvl == 2}
        outputs[fname] = (head, toc, body, sec_list, meta)

    # See-also cross references (files that share at least one source)
    def see_also(fname):
        mine = set(file_sources[fname])
        links = []
        for other, meta in THEMES.items():
            if other == fname:
                continue
            shared = sorted(mine & set(file_sources[other]), key=src_order.index)
            if not shared:
                continue
            sn = sections_of[other][0]
            anchor = slug_lookup[other][f"{sn[0]}. {sn[1]}"]
            links.append(f"- [{meta['title']}]({other}#{anchor}): shares source {', '.join(shared)}")
        return links

    for fname, (head, toc, body, sec_list, meta) in outputs.items():
        sa = see_also(fname)
        extra = []
        if sa:
            nsec = len(sec_list) + 1
            extra = [f"## {nsec}. See also", ""] + sa + [""]
        # recompute slugs including the See also heading (no effect on earlier slugs)
        body_full = body + extra
        sl = heading_slugs(head + body_full)
        by_text = {(lvl, text): slug for lvl, text, slug in sl}
        toc_full = list(toc)
        if extra:
            nsec = len(sec_list) + 1
            toc_full.append(f"{nsec}. [{nsec}. See also](#{by_text[(2, f'{nsec}. See also')]})")
        slug_lookup[fname] = {text: slug for lvl, text, slug in sl if lvl == 2}
        fm = ["---", f'title: "{meta["title"]}"', f'description: "{meta["description"]}"', "concepts:"]
        fm += [f'  - "{c}"' for c in meta["concepts"]]
        fm += ["tags:"] + [f"  - {t}" for t in meta["tags"]]
        fm += ["sources:"] + [f'  - "{s}"' for s in file_sources[fname]] + ["---", ""]
        text = "\n".join(fm + head + toc_full + [""] + body_full)
        text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
        (outp / fname).write_text(text, encoding="utf-8")
        final_text[fname] = text

    # 97 appendix file
    ameta = {"title": "Appendix: Other URLs", "description": "URLs from fenced code blocks listed as clickable links, grouped by source file.",
             "concepts": ["URLs", "code blocks"], "tags": ["appendix", "urls"]}
    a_srcs = [s for s in src_order if s in app_rows]
    a_sec = [(i, s, []) for i, s in enumerate(a_srcs, 1)]
    a_body = []
    if app_rows:
        for i, s in enumerate(a_srcs, 1):
            seg = []
            on = False
            for ln in appendix_body:
                if ln == f"## {s}":
                    on = True
                    seg.append(f"## {i}. {s}")
                    continue
                if on and ln.startswith("## "):
                    break
                if on:
                    seg.append(ln)
            a_body += seg
    else:
        a_body = ["## 1. None", ""] + appendix_body
        a_sec = [(1, "None", [])]
    head = [f"# {ameta['title']}", "", "## Contents", ""]
    sl = heading_slugs(head + a_body)
    by_text = {(lvl, text): slug for lvl, text, slug in sl}
    toc = [f"{si}. [{si}. {sname}](#{by_text[(2, f'{si}. {sname}')]})" for si, sname, _ in a_sec]
    fm = ["---", f'title: "{ameta["title"]}"', f'description: "{ameta["description"]}"', "concepts:"] + [f'  - "{c}"' for c in ameta["concepts"]]
    fm += ["tags:"] + [f"  - {t}" for t in ameta["tags"]] + ["sources:"] + [f'  - "{s}"' for s in a_srcs or src_order[:0]]
    if not a_srcs:
        fm[-1:] = ["sources: []"] if fm[-1] == "sources:" else fm[-1:]
    fm += ["---", ""]
    text = "\n".join(fm + head + toc + [""] + a_body)
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
    (outp / "97-appendix-other-urls.md").write_text(text, encoding="utf-8")
    final_text["97-appendix-other-urls.md"] = text
    slug_lookup["97-appendix-other-urls.md"] = {t: s for l, t, s in sl if l == 2}
    sections_of["97-appendix-other-urls.md"] = a_sec
    file_sources["97-appendix-other-urls.md"] = a_srcs

    # 00 index
    ifm = ["---", 'title: "Index"', 'description: "Table of contents of all sorted notes files with their sections."', "concepts:",
           '  - "table of contents"', "tags:", "  - index", "sources:"] + [f'  - "{s}"' for s in src_order] + ["---", ""]
    idx = ["# Index", "", "## Contents", ""]
    all_files = sorted(list(THEMES) + ["97-appendix-other-urls.md"])
    n = 0
    for fname in all_files:
        n += 1
        title = THEMES[fname]["title"] if fname in THEMES else ameta["title"]
        idx.append(f"{n}. [{title}]({fname})")
        idx.append(f"    - {INDEX_BLURB[fname]}")
        for si, sname, _ in sections_of[fname]:
            anchor = slug_lookup[fname].get(f"{si}. {sname}")
            idx.append(f"    - [{si}. {sname}]({fname}#{anchor})")
    idx += ["", "## Support files", "",
            "- [Exclusions](_exclusions.md): everything not carried over verbatim.",
            "- [Verification report](_verification-report.md): per-source verdicts.",
            "- [Provenance](_provenance.csv): unit ID, source, lines, destination.",
            "- [Ledger](_ledger.csv): every unit with original and cleaned text."]
    # the support-file links must resolve: they are files, checked by verify
    (outp / "00-index.md").write_text("\n".join(ifm + idx) + "\n", encoding="utf-8")

    # ----- exclusions
    ex = ["---", 'title: "Exclusions"', 'description: "Everything not carried over verbatim, grouped by source file."', "concepts:",
          '  - "exclusions"', '  - "merged duplicates"', '  - "removed syntax"', "tags:", "  - exclusions", "  - audit", "sources:"]
    ex += [f'  - "{s}"' for s in src_order] + ["---", "", "# Exclusions", "",
          "Presentation fixes are applied only to the cleaned text. The original text is untouched in `_ledger.csv`.", ""]
    ex.append("## Whole-batch notes")
    ex.append("")
    ex.append("- Ignored macOS AppleDouble metadata files in `__MACOSX/` (names starting with `._`): resource-fork data, not notes.")
    ex.append("- URLs inside fenced code blocks are kept verbatim there and also listed as clickable links in [the appendix](97-appendix-other-urls.md).")
    ex.append("- HTML tags are removed; of their attributes only href, src and alt are kept (as links). Other attributes (width, height, style, frameborder, colspan, SVG path data and similar) are dropped. Tag names and counts are listed per source below.")
    ex.append("- Exact duplicates are merged only within the same output file, and never for headings, separators or units under 3 words.")
    ex.append("- No image files were attached, so no OCR was done. Images are kept as links; an image with no alt text is marked *(image-only, not captured)*.")
    ex.append("")
    for p in files:
        if p.name not in stats_by_source:
            continue
        st = stats_by_source[p.name]
        sid = next(m["sn"] for m in manifest if m["source"] == p.name)
        ex.append(f"## S{sid:02d} {p.name}")
        ex.append("")
        recs = [r for r in ledger if r["source"] == p.name]
        merged = [r for r in recs if r["status"] == "merged"]
        excl = [r for r in recs if r["status"] == "excluded"]
        imgonly = sum(r["image_only"] for r in recs if r["status"] == "kept")
        ex.append(f"### S{sid:02d} Merged duplicates")
        ex.append("")
        if merged:
            for r in merged:
                ex.append(f"- {r['id']}: {r['note']}")
        else:
            ex.append("None")
        ex.append("")
        ex.append(f"### S{sid:02d} Units not carried over (no text content)")
        ex.append("")
        if excl:
            cnt = Counter(r["note"] for r in excl)
            for reason, c in cnt.most_common():
                ids = ", ".join(r["id"] for r in excl if r["note"] == reason)
                ex.append(f"- {reason}: {c} (units {ids if len(ids) < 400 else ids[:400] + ', ...'})")
                shown = [r["original_text"].strip().replace("\n", " / ")[:60] for r in excl if r["note"] == reason][:3]
                ex.append(f"  - examples: {'; '.join('`' + s.replace('`', chr(39)) + '`' for s in shown)}")
        else:
            ex.append("None")
        ex.append("")
        ex.append(f"### S{sid:02d} Removed or changed syntax (counts and examples)")
        ex.append("")
        if st.c:
            for key, c in sorted(st.c.items(), key=lambda kv: (-kv[1], kv[0])):
                exs = st.ex.get(key, [])
                line = f"- {key}: {c}"
                if exs:
                    line += " (examples: " + "; ".join("`" + e.replace("`", "'").replace("\n", " ") + "`" for e in exs) + ")"
                ex.append(line)
        else:
            ex.append("None")
        ex.append("")
        ex.append(f"### S{sid:02d} Image-only items")
        ex.append("")
        ex.append(f"{imgonly} image(s) with no alt text kept as links and marked image-only, not captured." if imgonly else "None")
        ex.append("")
    # excluded unit full text (needed for the 4-gram union with the exclusions file)
    ex.append("## Full text of excluded units")
    ex.append("")
    anyx = False
    for r in ledger:
        if r["status"] == "excluded":
            anyx = True
            ex.append(f"- {r['id']}: `{r['original_text'].strip()[:200].replace('`', chr(39)).replace(chr(10), ' / ')}`")
    if not anyx:
        ex.append("None")
    (outp / "_exclusions.md").write_text("\n".join(ex) + "\n", encoding="utf-8")

    # ----- provenance + ledger
    with open(outp / "_provenance.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["unit_id", "source_file", "lines", "destination_file", "destination_section", "status", "note"])
        for r in ledger:
            if r["status"] == "excluded":
                dest_file, dest_sec = "_exclusions.md", "Units not carried over"
            elif r["status"] == "merged":
                first = next(x for x in ledger if x["id"] == r["note"].split()[-1])
                dest_file, dest_sec = first["dest_file"], first["dest_section"]
            else:
                dest_file, dest_sec = r["dest_file"], r["dest_section"]
            w.writerow([r["id"], r["source"], f"{r['start']}-{r['end']}", dest_file, dest_sec, r["status"], r["note"]])
    with open(outp / "_ledger.csv", "w", newline="", encoding="utf-8") as f:
        cols = ["id", "source", "start", "end", "type", "original_text", "urls", "dest_file", "dest_section", "cleaned_text",
                "status", "note", "image_only", "merged_copies"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in ledger:
            w.writerow({k: r[k] for k in cols})
    (outp / "_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    cnt = Counter(r["status"] for r in ledger)
    summary = [("Source files", len(files)), ("Units total", len(ledger)), ("Written this run", cnt["kept"]),
               ("Already done (skipped)", 0), ("Merged exact duplicates", cnt["merged"]), ("Skipped on purpose (excluded)", cnt["excluded"]),
               ("Errors", len(errors)), ("Warnings", len(warnings)), ("Output files", len(final_text) + 1)]
    lists = [("SUCCESSFUL: WRITTEN", [(f"{r['id']} ({r['type']})", f"-> {r['dest_file']} / {r['dest_section']}") for r in ledger if r["status"] == "kept"]),
             ("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", []),
             ("SKIPPED ON PURPOSE: exact duplicate merged", [(r["id"], r["note"]) for r in ledger if r["status"] == "merged"]),
             ("SKIPPED ON PURPOSE: no text content", [(r["id"], r["note"]) for r in ledger if r["status"] == "excluded"]),
             ("ERRORS", errors), ("WARNINGS", warnings)]
    logp = Path.cwd() / f"results-log-{started:%Y-%m-%d_%H%M%S}.txt"
    write_log(logp, "build", started, inp, outp, summary, lists)
    print(f"units: {len(ledger)} kept {cnt['kept']} merged {cnt['merged']} excluded {cnt['excluded']}; errors {len(errors)} warnings {len(warnings)}")
    print(f"results log: {logp}")
    return 0 if not errors else 1


# ----------------------------------------------------------------------------
# Verify
# ----------------------------------------------------------------------------

def parse_nav_links(text):
    """Markdown links with relative targets (files or #anchors) in nav areas."""
    out = []
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        out.append(m.group(1))
    return out


def verify(inp, outp):
    from markdown_it import MarkdownIt

    started = datetime.now()
    inp, outp = Path(inp), Path(outp)
    files = source_files(inp)
    ledger = list(csv.DictReader(open(outp / "_ledger.csv", newline="", encoding="utf-8")))
    manifest = json.loads((outp / "_manifest.json").read_text(encoding="utf-8"))
    out_files = sorted(p for p in outp.iterdir() if p.suffix == ".md")
    out_texts = {p.name: p.read_text(encoding="utf-8") for p in out_files}
    excl_text = out_texts.get("_exclusions.md", "")
    theme_names = [n for n in out_texts if re.match(r"\d\d-", n)]
    failures = defaultdict(list)  # source -> reasons
    global_fail = []

    # ---- 1 coverage
    by_src = defaultdict(list)
    for r in ledger:
        by_src[r["source"]].append(r)
    cover = {}
    for p in files:
        raw, text = read_source(p)
        lines = text.split("\n")
        if lines and lines[-1] == "" and text.endswith("\n"):
            lines = lines[:-1]
        recs = by_src.get(p.name, [])
        nonblank = {i + 1 for i, l in enumerate(lines) if l.strip()}
        got = set()
        for r in recs:
            for ln in range(int(r["start"]), int(r["end"]) + 1):
                got.add(ln)
        missing_lines = sorted(nonblank - got)
        orphan = [r["id"] for r in recs if r["status"] == "kept" and not r["dest_file"]]
        orig_ok = all(True for _ in recs)
        # original text equals source lines
        bad_orig = []
        for r in recs:
            seg = "\n".join(lines[int(r["start"]) - 1:int(r["end"])])
            if seg != r["original_text"]:
                bad_orig.append(r["id"])
        cover[p.name] = {"units": len(recs), "missing_lines": len(missing_lines), "orphans": len(orphan), "bad_original": len(bad_orig)}
        if missing_lines:
            failures[p.name].append(f"{len(missing_lines)} non-blank lines not in any unit")
        if orphan:
            failures[p.name].append(f"{len(orphan)} orphan units")
        if bad_orig:
            failures[p.name].append(f"{len(bad_orig)} units whose original text differs from the source")
        if len(raw) != next(m["bytes"] for m in manifest if m["source"] == p.name):
            failures[p.name].append("file size differs from manifest (truncated or changed)")

    # ---- 2 URLs
    out_all = "\n".join(out_texts.values())
    out_urls = collect_urls(out_all)
    out_url_blob = html.unescape(out_all)
    url_res = {}
    for p in files:
        raw, text = read_source(p)
        su = collect_urls(text)
        miss = sorted(u for u in su if u not in out_urls and u not in out_url_blob)
        url_res[p.name] = (len(su), len(su) - len(miss), miss)
        if miss:
            failures[p.name].append(f"{len(miss)} URLs missing")

    # ---- 3 text 4-grams per source (per unit)
    out_tok_streams = {}
    all_out_grams = set()
    short_sets = {1: set(), 2: set(), 3: set()}
    stream_blob = []
    for name, t in out_texts.items():
        tk = tokens(t)
        out_tok_streams[name] = tk
        all_out_grams.update(ngrams(tk, 4))
        for n_ in (1, 2, 3):
            short_sets[n_].update(ngrams(tk, n_))
        stream_blob.append("".join(tk))
    blob = "\x00".join(stream_blob)
    text_res = {}
    for p in files:
        miss_real, miss_fmt = [], []
        for r in by_src.get(p.name, []):
            tk = tokens(r["original_text"])
            if len(tk) >= 4:
                for g in ngrams(tk, 4):
                    if g not in all_out_grams:
                        (miss_fmt if "".join(g) in blob else miss_real).append((r["id"], " ".join(g)))
            elif tk:
                if tuple(tk) not in short_sets[len(tk)]:
                    (miss_fmt if "".join(tk) in blob else miss_real).append((r["id"], " ".join(tk)))
        text_res[p.name] = (miss_real, miss_fmt)
        if miss_real:
            failures[p.name].append(f"{len(miss_real)} MISSING 4-grams")

    # ---- 4 reverse check
    src_grams = set()
    src_short = {1: set(), 2: set(), 3: set()}
    for r in ledger:
        tk = tokens(r["original_text"])
        src_grams.update(ngrams(tk, 4))
    for r in ledger:
        pass
    unsourced = defaultdict(list)
    unsourced_total = 0
    for name, t in out_texts.items():
        if not re.match(r"\d\d-", name) or name.startswith(("00-", "97-")):
            continue
        body_lines = t.split("\n")
        # drop frontmatter
        if body_lines and body_lines[0] == "---":
            k = body_lines.index("---", 1)
            body_lines = body_lines[k + 1:]
        in_fence = None
        in_toc = False
        chunks, cur = [], []
        for ln in body_lines:
            fm = FENCE_OPEN.match(ln)
            if in_fence:
                cur.append(ln)
                if fm and fm.group(2)[0] == in_fence[0] and len(fm.group(2)) >= len(in_fence) and not fm.group(3).strip():
                    in_fence = None
                continue
            if fm:
                in_fence = fm.group(2)
                cur.append(ln)
                continue
            if re.match(r"^#{1,3} ", ln):
                in_toc = ln.startswith("## Contents")
                chunks.append(cur)
                cur = []
                continue
            if in_toc:
                continue
            if re.match(r"^\| Title \| URL \|$", ln) or re.match(r"^\|(?:---\|)+$", ln) or re.match(r"^\| (?:\| )*\|$", ln):
                continue
            if ln.startswith("- [") and "shares source" in ln:
                continue
            if ln.strip() in ("*(see also)*",):
                continue
            if not ln.strip():
                if cur:
                    chunks.append(cur)
                    cur = []
                continue
            cur.append(ln)
        chunks.append(cur)
        for ch in chunks:
            tk = tokens("\n".join(ch))
            for g in ngrams(tk, 4):
                if g not in src_grams:
                    # table header cell / glue differences: retest ignoring whitespace against source tokens
                    unsourced[name].append(" ".join(g))
    # whitespace-insensitive retest against source blob
    src_blob = "\x00".join("".join(tokens(r["original_text"])) for r in ledger)
    unsourced_real = {}
    unsourced_fmt = {}
    for name, gl in unsourced.items():
        real, fmt = [], []
        for g in gl:
            (fmt if "".join(g.split()) in src_blob else real).append(g)
        unsourced_real[name] = real
        unsourced_fmt[name] = fmt
    unsourced_total = sum(len(v) for v in unsourced_real.values())

    # ---- 5 structure
    struct_fail = []
    slugs_by_file = {}
    for name, t in out_texts.items():
        hs = heading_slugs(t.split("\n"))
        slugs_by_file[name] = {s for _, _, s in hs}
        if not t.strip():
            struct_fail.append(f"{name}: empty file")
    nav_checked = 0
    for name, t in out_texts.items():
        if name.startswith("_"):
            nav_scope = t
        # only links I generate: TOC block, index, see-also, support-file links
        gen = []
        lines = t.split("\n")
        in_toc = False
        for ln in lines:
            if ln.startswith("## Contents"):
                in_toc = True
                continue
            if ln.startswith("## ") and not ln.startswith("## Contents"):
                in_toc = name == "00-index.md" and ln.startswith("## Support files")
            if in_toc or ln.startswith("- [") and "shares source" in ln:
                gen += parse_nav_links(ln)
        for target in gen:
            nav_checked += 1
            if target.startswith("#"):
                if target[1:] not in slugs_by_file[name]:
                    struct_fail.append(f"{name}: anchor {target} does not resolve")
            else:
                fpart, _, anc = target.partition("#")
                if fpart in out_texts:
                    if anc and anc not in slugs_by_file[fpart]:
                        struct_fail.append(f"{name}: {target} anchor not found in {fpart}")
                elif fpart != "_verification-report.md" and not (outp / fpart).exists():
                    struct_fail.append(f"{name}: link target {fpart} does not exist")
    for name, t in out_texts.items():
        texts = [x for _, x, _ in heading_slugs(t.split("\n")) if True]
    # duplicate H1/H2/H3 headings (my anchors) within a file
    for name, t in out_texts.items():
        hs = [(l, x) for l, x, _ in heading_slugs(t.split("\n")) if l <= 3]
        dup = [h for h, c in Counter(hs).items() if c > 1]
        if dup:
            struct_fail.append(f"{name}: duplicate headings at levels 1-3: {dup[:3]}")

    # ---- 6 render
    render_fail = []
    escaped_brackets = 0
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    for name, t in out_texts.items():
        if name == "_verification-report.md":
            continue
        body = t
        if body.startswith("---\n"):
            body = body[body.index("\n---\n", 4) + 5:]
        toks = md.parse(body)
        fenced = 0
        for tk in toks:
            if tk.type in ("html_block",):
                render_fail.append(f"{name}: raw HTML block: {tk.content[:60]!r}")
            if tk.type == "inline":
                for ch in tk.children or []:
                    if ch.type == "html_inline":
                        render_fail.append(f"{name}: raw inline HTML: {ch.content[:60]!r}")
                    if ch.type == "text":
                        for bad in ("**", "](", "[[", "~~"):
                            if bad in ch.content:
                                render_fail.append(f"{name}: literal {bad!r} in text: {ch.content[:80]!r}")
                        if ch.content.count("\\["):
                            escaped_brackets += 1
        # blank-line checks outside fences
        in_fence = None
        prev = ""
        prev_kind = "blank"
        for i, ln in enumerate(body.split("\n")):
            fm = FENCE_OPEN.match(ln)
            if in_fence:
                if fm and fm.group(2)[0] == in_fence[0] and len(fm.group(2)) >= len(in_fence) and not fm.group(3).strip():
                    in_fence = None
                prev_kind = "fence"
                continue
            if fm:
                if prev_kind not in ("blank",):
                    render_fail.append(f"{name}: fence without blank line before (body line {i + 1})")
                in_fence = fm.group(2)
                prev_kind = "fence"
                continue
            k = classify(ln, prev_kind if prev_kind in ("list",) else "other")
            if re.match(r"^#{1,6} ", ln):
                k = "heading"
            if prev_kind == "fence" and k != "blank":
                render_fail.append(f"{name}: text right after a fence (body line {i + 1})")
            if prev_kind not in ("blank", k) and k != "blank" and not (prev_kind == "list" and k == "list"):
                if not (prev_kind == "quote" and k == "quote") and not (prev_kind == "table" and k == "table"):
                    render_fail.append(f"{name}: missing blank line between {prev_kind} and {k} (body line {i + 1})")
            prev_kind = k
    # ---- verdicts
    verdict = {}
    for p in files:
        reasons = list(failures.get(p.name, []))
        if render_fail:
            reasons.append("render check failures exist")
        if struct_fail:
            reasons.append("structure check failures exist")
        if unsourced_total:
            reasons.append("unsourced text exists in outputs")
        img = sum(int(r["image_only"]) for r in by_src.get(p.name, []) if r["status"] == "kept")
        if reasons:
            verdict[p.name] = "Not safe: " + "; ".join(reasons)
        elif img:
            verdict[p.name] = f"Safe, but {img} image-only items not captured"
        else:
            verdict[p.name] = "Safe to delete"

    # ---- report
    rep = ["---", 'title: "Verification report"', 'description: "Per-source verification results for the sorted notes."', "concepts:",
           '  - "verification"', "tags:", "  - verification", "  - audit", "sources:"] + [f'  - "{p.name}"' for p in files] + ["---", "",
           "# Verification report", "", "## Per-source results", "",
           "| Source | URLs (source/found) | MISSING 4-grams | formatting-only | unsourced | image-only items | Verdict |",
           "|---|---|---|---|---|---|---|"]
    for p in files:
        su, found, _ = url_res[p.name]
        mr, mf = text_res[p.name]
        img = sum(int(r["image_only"]) for r in by_src.get(p.name, []) if r["status"] == "kept")
        rep.append(f"| {md_escape_cell(p.name)} | {su}/{found} | {len(mr)} | {len(mf)} | {unsourced_total} | {img} | {md_escape_cell(verdict[p.name])} |")
    rep += ["", "## Manifest", "", "| Source | Bytes | Lines | Words | URLs | Image URLs | Units | Read in full |", "|---|---|---|---|---|---|---|---|"]
    for m in manifest:
        c = cover[m["source"]]
        full = "yes" if c["missing_lines"] == 0 and c["bad_original"] == 0 else "NO"
        rep.append(f"| {md_escape_cell(m['source'])} | {m['bytes']} | {m['lines']} | {m['words']} | {m['urls']} | {m['image_urls']} | {m['units']} | {full} |")
    rep += ["", "## Check summary", "",
            f"- Coverage: every non-blank source line sits in a unit; units with orphan or altered original text: {sum(c['orphans'] + c['bad_original'] for c in cover.values())}.",
            f"- URLs: {sum(v[0] for v in url_res.values())} source URLs, {sum(v[1] for v in url_res.values())} found in outputs.",
            f"- Text: MISSING 4-grams {sum(len(v[0]) for v in text_res.values())}; formatting-only {sum(len(v[1]) for v in text_res.values())}.",
            f"- Reverse check: unsourced 4-grams {unsourced_total}; formatting-only (glue/split) {sum(len(v) for v in unsourced_fmt.values())}.",
            f"- Structure: {nav_checked} generated links checked; failures {len(struct_fail)}.",
            f"- Render: CommonMark parse of {len(out_texts)} files; failures {len(render_fail)}; escaped bracket pairs in text nodes {escaped_brackets} (expected where a source had lone brackets).",
            ""]
    for title, items in (("Structure failures", struct_fail), ("Render failures", render_fail)):
        rep.append(f"## {title}")
        rep.append("")
        rep += [f"- {x}" for x in items[:50]] or ["None"]
        rep.append("")
    rep.append("## Formatting-only differences (glued-word splits and similar)")
    rep.append("")
    any_f = False
    for p in files:
        mf = text_res[p.name][1]
        if mf:
            any_f = True
            rep.append(f"- {p.name}: {len(mf)} (e.g. `{mf[0][1]}` in {mf[0][0]})")
    if not any_f:
        rep.append("None")
    rep.append("")
    rep.append("## Missing URLs and 4-grams (detail)")
    rep.append("")
    any_m = False
    for p in files:
        su, found, miss = url_res[p.name]
        mr = text_res[p.name][0]
        for u in miss[:20]:
            any_m = True
            rep.append(f"- {p.name}: URL missing `{u[:120]}`")
        for uid, g in mr[:20]:
            any_m = True
            rep.append(f"- {p.name}: MISSING `{g}` ({uid})")
    if not any_m:
        rep.append("None")
    rep.append("")
    rep.append("## Unsourced output text (detail)")
    rep.append("")
    any_u = False
    for name, v in unsourced_real.items():
        for g in v[:20]:
            any_u = True
            rep.append(f"- {name}: `{g}`")
    if not any_u:
        rep.append("None")
    (outp / "_verification-report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    safe = [p.name for p in files if verdict[p.name].startswith("Safe")]
    summary = [("Source files", len(files)), ("Safe (incl. image-only notes)", len(safe)), ("Not safe", len(files) - len(safe)),
               ("MISSING 4-grams", sum(len(v[0]) for v in text_res.values())), ("Missing URLs", sum(len(v[2]) for v in url_res.values())),
               ("Unsourced 4-grams", unsourced_total), ("Structure failures", len(struct_fail)), ("Render failures", len(render_fail))]
    lists = [("SUCCESSFUL: VERIFIED SAFE", [(n, verdict[n]) for n in safe]),
             ("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", []),
             ("SKIPPED ON PURPOSE", []),
             ("ERRORS", [(n, verdict[n]) for n in verdict if verdict[n].startswith("Not safe")]),
             ("WARNINGS", [(f"{n}", f"{len(text_res[n][1])} formatting-only 4-grams") for n in text_res if text_res[n][1]])]
    logp = Path.cwd() / f"results-log-{started:%Y-%m-%d_%H%M%S}.txt"
    write_log(logp, "verify", started, inp, outp, summary, lists)
    for p in files:
        print(f"{verdict[p.name]:<45} {p.name}")
    print(f"MISSING={sum(len(v[0]) for v in text_res.values())} URLmissing={sum(len(v[2]) for v in url_res.values())} unsourced={unsourced_total} struct={len(struct_fail)} render={len(render_fail)}")
    print(f"results log: {logp}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "verify"])
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    return build(a.input, a.output) if a.command == "build" else verify(a.input, a.output)


if __name__ == "__main__":
    sys.exit(main())
