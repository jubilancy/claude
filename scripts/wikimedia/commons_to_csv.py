#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "pyyaml",
# ]
# ///
"""
commons_to_csv.py - Wikimedia Commons File:/Category: URLs -> timestamped CSV (sizes, title, description, categories, taxonomy, tags) + matching log, --info counts, --md gallery.

What it does:
- Reads Commons URLs from urls.txt (one per line, # comments ok): commons.wikimedia.org/wiki/File:...
  and commons.wikimedia.org/wiki/Category:... (also /w/index.php?title=... and mobile hosts).
  Special: pages, other namespaces and non-Commons URLs are skipped on purpose and listed in the log.
- One CSV row per image, written as it goes so an interrupted run keeps its rows. Columns:
  id, title, file_name, description, author, credit, date, license, license_url, attribution,
  mime, width, height, bytes, url_original, url_<width> for each --sizes, page_url,
  collection, theme, categories, tags, depicts, depicts_qids,
  taxon, taxon_rank, taxon_qid, taxa_all, taxonomy, kingdom..species, uploaded, uploader, retrieved.
  Several values in one cell are separated by |
- Where the data comes from:
    title, description, author, credit, date, license, attribution  Commons image metadata (extmetadata)
    categories   the file's visible categories (hidden maintenance categories are left out)
    depicts      the file's structured data "depicts" (P180) statements, labelled from Wikidata
    taxon...     Wikidata taxon items found among the depicts items and the main topic (P301) of the
                 file's categories; name (P225), rank (P105) and the parent chain (P171)
    tags         slugs of the visible categories + depicts labels + taxon names
    theme        the category you gave (or, for a File: URL, the file's first visible category)
    collection   the category the file was found in (differs from theme with --subcats)
- Every run writes a NEW commons_<timestamp>.csv and a matching log_<timestamp>.txt (same timestamp)
  in the output folder. Nothing is ever overwritten or appended to.
- --info: writes info.txt (no CSV): what is in urls.txt, the file count of every category (and of
  sub-categories with --subcats), the number of rows a run would write and a rough run time.
- --md: turns an existing CSV into a markdown gallery (whole file, or only some rows/categories/tags)
  and writes a matching log.
- Retries on 429/503, honoring Retry-After. One request at a time, with gzip and maxlag, and a
  User-Agent with contact information (set your own with --user-agent or WIKI_USER_AGENT).
- Audio, video and PDF files are skipped and counted in the log; only image files become rows.

Usage:
    uv run scripts/wikimedia/commons_to_csv.py                          # reads ./urls.txt, writes commons-out/commons_<timestamp>.csv + log
    uv run scripts/wikimedia/commons_to_csv.py --info                   # writes commons-out/info.txt, fetches no rows
    uv run scripts/wikimedia/commons_to_csv.py --info --subcats 2       # ...counting sub-categories two levels down
    uv run scripts/wikimedia/commons_to_csv.py --input other.txt --output out_dir --subcats 1
    uv run scripts/wikimedia/commons_to_csv.py --sizes 250,500,1920 --limit 100 --no-taxonomy
    uv run scripts/wikimedia/commons_to_csv.py --md                     # newest CSV in commons-out -> gallery_<timestamp>.md
    uv run scripts/wikimedia/commons_to_csv.py --md commons-out/commons_2026-11-14_120000.csv --rows 1-20,35
    uv run scripts/wikimedia/commons_to_csv.py --md --category "Bellis" --tag daisy --size 500
"""

import argparse
import csv
import html
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

DEFAULT_UA = "commons-to-csv/1.0 (personal archive tool; +https://github.com/jubilancy/claude)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
BATCH = 50  # most titles/ids one request may carry
DEFAULT_SIZES = "250,500,960,1920"
# The only thumbnail widths Commons serves (checked live: any other width, e.g. 640, 800, 1024 or 2560, is refused).
STANDARD_WIDTHS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)
MAX_RETRIES = 6
RETRY_MAX_WAIT_SECONDS = 120.0
RANK_COLUMNS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
RANK_SPECIFICITY = ["species", "subspecies", "genus", "tribe", "subfamily", "family", "order", "class", "phylum", "division", "kingdom", "domain"]

FIELDS = [
    "id", "title", "file_name", "description", "author", "credit", "date", "license", "license_url", "attribution",
    "mime", "width", "height", "bytes", "url_original",
    "{sizes}",
    "page_url", "collection", "theme", "categories", "tags", "depicts", "depicts_qids",
    "taxon", "taxon_rank", "taxon_qid", "taxa_all", "taxonomy", *RANK_COLUMNS,
    "uploaded", "uploader", "retrieved",
]


class SkipUrl(Exception):
    """Raised for URLs that should be skipped on purpose (not errors)."""


# --------------------------------------------------------------------------
# HTTP with retry
# --------------------------------------------------------------------------

class Client:
    """One request at a time, with a pause, gzip, maxlag, and a wait on 429/503."""

    def __init__(self, user_agent: str, delay: float):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip"})
        self.delay = delay
        self.last = 0.0
        self.requests_made = 0

    def _pause(self):
        wait = self.last + self.delay - time.time()
        if wait > 0:
            time.sleep(wait)

    def get(self, base: str, **params) -> dict:
        params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        wait_default = 5.0
        for attempt in range(MAX_RETRIES + 1):
            self._pause()
            try:
                resp = self.session.get(base, params=params, timeout=60)
            except requests.RequestException as e:
                self.last = time.time()
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"network error: {e}") from None
                wait = min(wait_default * 2 ** attempt, RETRY_MAX_WAIT_SECONDS)
                print(f"  network problem ({type(e).__name__}), waiting {wait:.0f}s (retry {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            self.last = time.time()
            self.requests_made += 1
            retry_after = resp.headers.get("Retry-After", "")
            body = None
            if resp.status_code == 200:
                body = resp.json()
                if body.get("error", {}).get("code") != "maxlag":
                    if "error" in body:
                        raise RuntimeError(f"API error: {body['error'].get('code')}: {body['error'].get('info')}")
                    return body
            elif resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
            if attempt == MAX_RETRIES:
                raise RuntimeError("gave up after repeated rate limiting; try again later or raise --delay")
            wait = float(retry_after) if retry_after.isdigit() else wait_default * 2 ** attempt
            wait = min(max(wait, 1.0), RETRY_MAX_WAIT_SECONDS)
            print(f"  HTTP {resp.status_code if body is None else 'maxlag'}, waiting {wait:.0f}s (retry {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)
        raise RuntimeError("unreachable")

    def pages(self, base: str, drop_continue=("iistart", "iicontinue"), **params):
        """Every page of a query, following `continue`. Older file versions (iistart) are not followed."""
        cont = {}
        while True:
            body = self.get(base, **params, **cont)
            for w in body.get("warnings", {}).values():
                print(f"  API warning: {w}")
            yield from body.get("query", {}).get("pages", [])
            cont = {k: v for k, v in body.get("continue", {}).items() if k not in drop_continue}
            if not any(k != "continue" for k in cont):
                return


# --------------------------------------------------------------------------
# URLs
# --------------------------------------------------------------------------

def parse_commons_url(url: str):
    """Return ("file" | "category", title) or raise SkipUrl for anything else."""
    parsed = urllib.parse.urlsplit(url.strip())
    host = parsed.netloc.lower().replace("commons.m.", "commons.")
    if host != "commons.wikimedia.org":
        raise SkipUrl("not a commons.wikimedia.org URL")
    if parsed.path.startswith("/wiki/"):
        title = parsed.path[len("/wiki/"):]
    else:
        title = (urllib.parse.parse_qs(parsed.query).get("title") or [""])[0]
    title = urllib.parse.unquote(title).replace("_", " ").strip()
    if not title:
        raise SkipUrl("no page title in the URL")
    ns, _, name = title.partition(":")
    ns_l = ns.lower()
    if ns_l == "special":
        raise SkipUrl("Special: page (generated by MediaWiki, not a real page)")
    if ns_l in ("file", "image") and name:
        return "file", f"File:{name}"
    if ns_l == "category" and name:
        return "category", f"Category:{name}"
    raise SkipUrl(f"only File: and Category: pages are supported (got “{title}”)")


def read_urls(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# --------------------------------------------------------------------------
# Text cleanup
# --------------------------------------------------------------------------

ANCHOR = re.compile(r'<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def md_url(url: str) -> str:
    """Parentheses in an address would end a markdown link early."""
    return url.replace("(", "%28").replace(")", "%29")


def plain(text: str, host: str = "commons.wikimedia.org") -> str:
    """Wiki metadata is HTML: keep links as markdown, drop the rest."""
    def absolute(href):
        href = html.unescape(href)
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return f"https://{host}{href}"
        return href

    text = ANCHOR.sub(lambda m: f"[{re.sub(r'<[^>]+>', '', m[2]).strip() or m[1]}]({md_url(absolute(m[1]))})", text or "")
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r" *\n *", "\n", text)).strip()


def shorten(text: str, limit: int) -> str:
    if not limit or len(text) <= limit:
        return text
    return text[:limit].rsplit(None, 1)[0].rstrip(".,;:([ ") + " …"


def slugify_tag(text: str) -> str:
    tag = unicodedata.normalize("NFC", text).lower()
    tag = re.sub(r"[^\w\s-]", "", tag)
    return re.sub(r"[\s_-]+", "-", tag).strip("-")


def clean_url(url: str) -> str:
    """The API appends tracking parameters to wikimedia.org addresses; the file does not need them."""
    p = urllib.parse.urlsplit(url or "")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", "")) if p.netloc.endswith("wikimedia.org") else (url or "")


# --------------------------------------------------------------------------
# Image sizes
# --------------------------------------------------------------------------

THUMB_WIDTH = re.compile(r"^(.*/)((?:[a-z0-9]+-)*?)(\d+)px-([^/]*)$")


def thumb_at(thumb_url: str, width: int) -> str:
    """Commons names a thumbnail <prefix><width>px-<file>; swap the width for another one."""
    m = THUMB_WIDTH.match(clean_url(thumb_url))
    return f"{m[1]}{m[2]}{width}px-{m[4]}" if m else ""


def size_urls(info: dict, sizes: list[int]) -> dict:
    """{width: address}. Raster images never get a copy larger than the original; SVG scales freely."""
    original = clean_url(info.get("url", ""))
    thumb = info.get("thumburl", "")
    vector = info.get("mime") == "image/svg+xml"
    out = {}
    for w in sizes:
        if not vector and info.get("width") and info["width"] <= w:
            out[w] = original
        else:
            out[w] = thumb_at(thumb, w) if thumb else (original if not vector else "")
    return out


# --------------------------------------------------------------------------
# Enrichment: categories, structured data, Wikidata taxonomy
# --------------------------------------------------------------------------

def chunks(items, n=BATCH):
    items = list(items)
    for i in range(0, len(items), n):
        yield items[i:i + n]


def visible_categories(client: Client, pageids: list[int]) -> dict[int, list[str]]:
    """File pages -> visible (non-hidden) category names. Hidden ones are maintenance categories."""
    out = {pid: [] for pid in pageids}
    for group in chunks(pageids):
        for p in client.pages(COMMONS_API, drop_continue=(), action="query", pageids="|".join(map(str, group)),
                              prop="categories", clshow="!hidden", cllimit="max"):
            out.setdefault(p["pageid"], []).extend(c["title"].split(":", 1)[1] for c in p.get("categories", []))
    return out


def depicts_of(client: Client, pageids: list[int]) -> dict[int, list[str]]:
    """File pages -> Wikidata Q-ids from the structured data 'depicts' (P180) statements."""
    out = {pid: [] for pid in pageids}
    for group in chunks(pageids):
        body = client.get(COMMONS_API, action="wbgetentities", ids="|".join(f"M{pid}" for pid in group), props="claims")
        for mid, ent in (body.get("entities") or {}).items():
            statements = ent.get("statements") or ent.get("claims") or {}
            if not isinstance(statements, dict):
                continue
            ids = []
            for st in statements.get("P180", []):
                val = (st.get("mainsnak") or {}).get("datavalue", {}).get("value")
                if isinstance(val, dict) and val.get("id"):
                    ids.append(val["id"])
            try:
                out[int(mid.lstrip("M"))] = ids
            except ValueError:
                pass
    return out


def category_items(client: Client, categories: list[str]) -> dict[str, str]:
    """Category name -> Wikidata item of that category (when it has one)."""
    out = {}
    for group in chunks(categories):
        for p in client.pages(COMMONS_API, drop_continue=(), action="query", titles="|".join(f"Category:{c}" for c in group),
                              prop="pageprops", ppprop="wikibase_item"):
            q = (p.get("pageprops") or {}).get("wikibase_item")
            if q:
                out[p["title"].split(":", 1)[1]] = q
    return out


class Wikidata:
    """Cached Wikidata lookups for labels, taxon names, ranks and parent taxa."""

    def __init__(self, client: Client):
        self.client = client
        self.items: dict[str, dict] = {}
        self.category_item: dict[str, str] = {}  # category name -> its Wikidata item
        self.checked_categories: set[str] = set()

    @staticmethod
    def _first(claims, prop):
        """The value of the preferred statement for a property, else the first normal one (never a deprecated one)."""
        try:
            statements = [c for c in claims[prop] if c.get("rank") != "deprecated"]
            statements.sort(key=lambda c: c.get("rank") != "preferred")  # stable: preferred first
            return statements[0]["mainsnak"]["datavalue"]["value"]
        except (KeyError, IndexError, TypeError):
            return None

    def _store(self, qid, entity):
        claims = entity.get("claims") or {}
        if not isinstance(claims, dict):
            claims = {}
        ref = lambda prop: (lambda v: v.get("id") if isinstance(v, dict) else None)(self._first(claims, prop))
        labels = entity.get("labels") or {}
        taxon_name = self._first(claims, "P225")
        self.items[qid] = {
            "label": labels.get("en", {}).get("value") or labels.get("mul", {}).get("value") or taxon_name or qid,
            "taxon_name": taxon_name,
            "rank": ref("P105"),
            "parent": ref("P171"),
            "main_topic": ref("P301"),
        }

    def ensure(self, qids):
        """Fetch labels and taxon data for these items, then for their parents and ranks, until nothing is missing."""
        pending = {q for q in qids if q and q not in self.items}
        for _ in range(60):
            if not pending:
                return
            for group in chunks(sorted(pending)):
                body = self.client.get(WIKIDATA_API, action="wbgetentities", ids="|".join(group), props="labels|claims", languages="en|mul")
                for qid, ent in (body.get("entities") or {}).items():
                    if "missing" in ent:
                        self.items[qid] = {"label": qid, "taxon_name": None, "rank": None, "parent": None, "main_topic": None}
                    else:
                        self._store(qid, ent)
                for qid in group:
                    self.items.setdefault(qid, {"label": qid, "taxon_name": None, "rank": None, "parent": None, "main_topic": None})
            pending = set()
            for item in list(self.items.values()):
                if item["taxon_name"]:  # a taxon: its parent and rank are needed too
                    pending.update(q for q in (item["parent"], item["rank"]) if q and q not in self.items)
            pending -= set(self.items)

    def add_categories(self, categories):
        """Look up the Wikidata item of every category not seen yet, and the main topic (P301) of each."""
        new = sorted(set(categories) - self.checked_categories)
        if not new:
            return
        self.category_item.update(category_items(self.client, new))
        self.checked_categories.update(new)
        self.ensure(self.category_item.values())
        self.ensure(self.items[q]["main_topic"] for q in self.category_item.values() if self.items[q]["main_topic"])

    def category_topics(self, categories):
        """Wikidata items the given categories are about (P301)."""
        out = []
        for c in categories:
            item = self.items.get(self.category_item.get(c, ""), {})
            if item.get("main_topic"):
                out.append(item["main_topic"])
        return out

    def label(self, qid):
        return self.items.get(qid, {}).get("label", qid)

    def is_taxon(self, qid):
        return bool(self.items.get(qid, {}).get("taxon_name"))

    def lineage(self, qid):
        """[(name, rank)] from the top down to this taxon."""
        chain, seen = [], set()
        while qid and qid in self.items and qid not in seen:
            seen.add(qid)
            it = self.items[qid]
            if not it["taxon_name"]:
                break
            chain.append((it["taxon_name"], (self.items.get(it["rank"], {}).get("label") or "").lower(), qid))
            qid = it["parent"]
        return list(reversed(chain))


def empty_taxonomy() -> dict:
    return {"taxon": "", "taxon_rank": "", "taxon_qid": "", "taxa_all": "", "taxonomy": "", **{r: "" for r in RANK_COLUMNS}}


def taxonomy_for(wd: Wikidata, candidates: list[str]) -> dict:
    """Pick the most specific taxon among the candidates and describe its lineage."""
    taxa = [q for q in dict.fromkeys(candidates) if wd.is_taxon(q)]
    empty = empty_taxonomy()
    if not taxa:
        return empty

    def specificity(q):
        rank = (wd.items.get(wd.items[q]["rank"], {}).get("label") or "").lower() if wd.items[q]["rank"] else ""
        return RANK_SPECIFICITY.index(rank) if rank in RANK_SPECIFICITY else len(RANK_SPECIFICITY)

    primary = min(taxa, key=specificity)  # min() keeps the first of equals
    lineage = wd.lineage(primary)
    out = dict(empty)
    out["taxon"] = wd.items[primary]["taxon_name"]
    out["taxon_rank"] = lineage[-1][1] if lineage else ""
    out["taxon_qid"] = primary
    out["taxa_all"] = "|".join(wd.items[q]["taxon_name"] for q in taxa)
    out["taxonomy"] = " > ".join(name for name, _, _ in lineage)
    for name, rank, _ in lineage:
        col = "phylum" if rank == "division" and not out["phylum"] else rank
        if col in RANK_COLUMNS and not out[col]:
            out[col] = name
    return out


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

def meta(info: dict, key: str) -> str:
    return plain((info.get("extmetadata", {}).get(key) or {}).get("value", ""))


def attribution_line(title, page_url, author, license_name, license_url):
    line = f'"[{title}]({md_url(page_url)})"'
    if author:
        line += f" by {author}"
    if license_name:
        line += f", [{license_name}]({md_url(license_url)})" if license_url else f", {license_name}"
    return line


def build_row(page, sizes, collection, theme, cats, depicts_q, wd, taxonomy_on, max_desc, retrieved):
    info = (page.get("imageinfo") or [{}])[0]
    page_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page['title'].replace(' ', '_'), safe=':')}"
    file_name = page["title"].split(":", 1)[1]
    title = meta(info, "ObjectName") or re.sub(r"\.[A-Za-z0-9]+$", "", file_name)
    author = meta(info, "Artist")
    license_name = meta(info, "LicenseShortName") or meta(info, "UsageTerms")
    license_url = meta(info, "LicenseUrl")
    depicts_labels = [wd.label(q) for q in depicts_q]
    tax = taxonomy_for(wd, depicts_q + wd.category_topics(cats)) if taxonomy_on else empty_taxonomy()
    tags = []
    for t in [*cats, *depicts_labels, *([tax["taxon"]] if tax["taxon"] else []), *([tax["genus"]] if tax["genus"] else [])]:
        s = slugify_tag(t)
        if s and s not in tags:
            tags.append(s)
    row = {
        "id": page["pageid"],
        "title": title,
        "file_name": file_name,
        "description": shorten(meta(info, "ImageDescription"), max_desc),
        "author": author,
        "credit": meta(info, "Credit"),
        "date": meta(info, "DateTimeOriginal") or meta(info, "DateTime"),
        "license": license_name,
        "license_url": license_url,
        "attribution": attribution_line(title, page_url, author, license_name, license_url),
        "mime": info.get("mime", ""),
        "width": info.get("width", ""),
        "height": info.get("height", ""),
        "bytes": info.get("size", ""),
        "url_original": clean_url(info.get("url", "")),
        "page_url": page_url,
        "collection": collection,
        "theme": theme,
        "categories": "|".join(cats),
        "tags": "|".join(tags[:20]),
        "depicts": "|".join(depicts_labels),
        "depicts_qids": "|".join(depicts_q),
        **tax,
        "uploaded": info.get("timestamp", ""),
        "uploader": info.get("user", ""),
        "retrieved": retrieved,
    }
    for w, url in size_urls(info, sizes).items():
        row[f"url_{w}"] = url
    return row


def csv_columns(sizes):
    cols = []
    for f in FIELDS:
        cols.extend(f"url_{w}" for w in sizes) if f == "{sizes}" else cols.append(f)
    return cols


# --------------------------------------------------------------------------
# Collecting files from a URL
# --------------------------------------------------------------------------

IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|size|mime|timestamp|user|extmetadata"}


def category_batches(client, category, thumb_width, seen, limit):
    """Yield lists of up to 50 file pages (with image info) directly in one category."""
    batch, count = [], 0
    for p in client.pages(COMMONS_API, action="query", generator="categorymembers", gcmtitle=category, gcmtype="file",
                          gcmlimit=BATCH, iiurlwidth=thumb_width, **IMAGEINFO):
        if p.get("pageid") in seen or "imageinfo" not in p:
            continue
        seen.add(p["pageid"])
        batch.append(p)
        count += 1
        if len(batch) == BATCH:
            yield batch
            batch = []
        if limit and count >= limit:
            break
    if batch:
        yield batch


def subcategories(client, category):
    return [p["title"] for p in client.pages(COMMONS_API, action="query", generator="categorymembers", gcmtitle=category,
                                              gcmtype="subcat", gcmlimit=BATCH, prop="info")]


def walk_categories(client, root, depth):
    """Yield (category title, level) for the root and its sub-categories, breadth first."""
    queue, visited = [(root, 0)], {root}
    while queue:
        cat, level = queue.pop(0)
        yield cat, level
        if level < depth:
            for sub in subcategories(client, cat):
                if sub not in visited:
                    visited.add(sub)
                    queue.append((sub, level + 1))


# --------------------------------------------------------------------------
# Results log (same layout as wiki_to_markdown.py)
# --------------------------------------------------------------------------

def write_results_log(log_path: Path, meta_info: dict, written, skipped_dupes, skipped_special, errors, warnings) -> None:
    lines = [
        f"{meta_info['tool']} results log",
        f"Run started : {meta_info['started']}",
        f"Input file  : {meta_info['input']}",
        f"Output file : {meta_info['output']}",
        f"Options     : {meta_info['options']}",
        f"URLs in file: {meta_info['total']}",
        f"Processed   : {meta_info['processed']}" + ("  (run was interrupted)" if meta_info["interrupted"] else ""),
        "",
        "SUMMARY",
        f"  Written (URLs with new rows)   : {len(written)}",
        f"  Rows written                   : {meta_info['rows']}",
        f"  Skipped (already seen)         : {len(skipped_dupes)}",
        f"  Skipped (special/unsupported)  : {len(skipped_special)}",
        f"  Errors                         : {len(errors)}",
        f"  Warnings                       : {len(warnings)}",
        "",
        f"SUCCESSFUL: WRITTEN ({len(written)})",
    ]
    lines += [f"  {url}\n    -> {fname}  ({detail})" for url, fname, detail in written] or ["  (none)"]

    lines += ["", f"SUCCESSFUL: SKIPPED, ALREADY SEEN IN THIS RUN ({len(skipped_dupes)})"]
    lines += [f"  {url}\n    {why}" for url, why in skipped_dupes] or ["  (none)"]

    lines += ["", f"SKIPPED ON PURPOSE: SPECIAL OR UNSUPPORTED PAGES ({len(skipped_special)})"]
    lines += [f"  {url}\n    {why}" for url, why in skipped_special] or ["  (none)"]

    lines += ["", f"ERRORS ({len(errors)})"]
    lines += [f"  {url}\n    {err}" for url, err in errors] or ["  (none)"]

    lines += ["", f"WARNINGS ({len(warnings)})"]
    lines += [f"  {url}\n    {msg}" for url, msg in warnings] or ["  (none)"]

    lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")


def new_stamp(output_dir: Path, names) -> str:
    """A timestamp no existing output file uses, so nothing is ever overwritten."""
    while True:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if not any((output_dir / n.format(stamp=stamp)).exists() for n in names):
            return stamp
        time.sleep(1)


# --------------------------------------------------------------------------
# Main run: URLs -> CSV
# --------------------------------------------------------------------------

def parse_sizes(text: str) -> list[int]:
    try:
        sizes = sorted({int(s) for s in text.split(",") if s.strip()})
    except ValueError:
        raise SystemExit(f"--sizes must be whole numbers like 250,500,960,1920 (got {text!r})")
    bad = [w for w in sizes if w not in STANDARD_WIDTHS]
    if not sizes or bad:
        raise SystemExit(f"--sizes: Commons only serves these widths: {', '.join(map(str, STANDARD_WIDTHS))} (not {', '.join(map(str, bad)) or 'an empty list'})")
    return sizes


def run(args) -> int:
    input_path, output_dir = Path(args.input), Path(args.output)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    urls = read_urls(input_path)
    if not urls:
        print("No URLs found in input file.", file=sys.stderr)
        return 1
    sizes = parse_sizes(args.sizes)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    stamp = new_stamp(output_dir, ["commons_{stamp}.csv", "log_{stamp}.txt"])
    csv_path, log_path = output_dir / f"commons_{stamp}.csv", output_dir / f"log_{stamp}.txt"
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    client = Client(args.user_agent, args.delay)
    wd = Wikidata(client)
    columns = csv_columns(sizes)

    written, skipped_dupes, skipped_special, errors, warnings = [], [], [], [], []
    seen_urls, seen_pages = set(), set()
    rows_total, processed, interrupted = 0, 0, False
    print(f"Processing {len(urls)} URL(s) -> {csv_path}\n")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        f.flush()
        try:
            for i, url in enumerate(urls, 1):
                print(f"[{i}/{len(urls)}] {url}")
                try:
                    kind, title = parse_commons_url(url)
                    if title in seen_urls:
                        print("  skip: already seen in this run")
                        skipped_dupes.append((url, f"same page as an earlier line: {title}"))
                        processed = i
                        continue
                    seen_urls.add(title)
                    rows_before = rows_total
                    non_image = 0
                    theme_root = title.split(":", 1)[1] if kind == "category" else ""

                    def batches():
                        if kind == "category":
                            for cat, level in walk_categories(client, title, args.subcats):
                                print(f"  {cat}" + (f"  (sub-category, level {level})" if level else ""))
                                for b in category_batches(client, cat, sizes[0], seen_pages, args.limit):
                                    yield cat.split(":", 1)[1], b
                        else:
                            for p in client.pages(COMMONS_API, action="query", titles=title, iiurlwidth=sizes[0], **IMAGEINFO):
                                if p.get("pageid") in seen_pages:
                                    continue
                                if "imageinfo" not in p:
                                    warnings.append((url, "file not found"))
                                    print("  file not found")
                                    continue
                                seen_pages.add(p["pageid"])
                                yield "", [p]

                    for collection, batch in batches():
                        images = [p for p in batch if (p["imageinfo"][0].get("mime") or "").startswith("image/")]
                        non_image += len(batch) - len(images)
                        if not images:
                            continue
                        ids = [p["pageid"] for p in images]
                        cats = visible_categories(client, ids)
                        depicts = depicts_of(client, ids)
                        wd.ensure(q for v in depicts.values() for q in v)  # labels of the depicts items (and their lineage)
                        if not args.no_taxonomy:
                            wd.add_categories(c for v in cats.values() for c in v)
                        for p in images:
                            pid = p["pageid"]
                            theme = theme_root or (cats[pid][0] if cats[pid] else "")
                            row = build_row(p, sizes, collection, theme, cats[pid], depicts[pid], wd, not args.no_taxonomy, args.max_desc, retrieved)
                            writer.writerow(row)
                            rows_total += 1
                        f.flush()
                        print(f"  {rows_total - rows_before} rows so far")
                    if non_image:
                        warnings.append((url, f"{non_image} non-image file(s) skipped (audio, video or PDF)"))
                    added = rows_total - rows_before
                    if added == 0 and not any(w[0] == url for w in warnings):
                        warnings.append((url, "0 rows: the page has no images, or all were seen under an earlier URL"))
                    written.append((url, csv_path.name, f"{added} rows"))
                except SkipUrl as e:
                    print(f"  skip: {e}")
                    skipped_special.append((url, str(e)))
                except Exception as e:
                    print(f"  ERROR: {e}", file=sys.stderr)
                    errors.append((url, str(e)))
                processed = i
        except KeyboardInterrupt:
            interrupted = True
            print("\nInterrupted. Closing the CSV and writing the log for what was processed so far.")
        finally:
            write_results_log(
                log_path,
                {
                    "tool": "commons_to_csv", "started": started.strftime("%Y-%m-%d %H:%M:%S"), "input": str(input_path),
                    "output": str(csv_path),
                    "options": f"sizes={','.join(map(str, sizes))} subcats={args.subcats} limit={args.limit or 'none'} taxonomy={'off' if args.no_taxonomy else 'on'}",
                    "total": len(urls), "processed": processed, "interrupted": interrupted, "rows": rows_total,
                },
                written, skipped_dupes, skipped_special, errors, warnings,
            )

    print(f"\nDone: {rows_total} rows from {len(written)} URL(s), {len(skipped_dupes)} duplicate, "
          f"{len(skipped_special)} special/unsupported skipped, {len(errors)} failed. ({client.requests_made} requests)")
    print(f"CSV: {csv_path}\nLog: {log_path}")
    return 1 if errors else 0


# --------------------------------------------------------------------------
# --info
# --------------------------------------------------------------------------

def category_counts(client, titles):
    """{category title: {"files": n, "subcats": n, "missing": bool}}"""
    out = {}
    for group in chunks(titles):
        for p in client.pages(COMMONS_API, drop_continue=(), action="query", titles="|".join(group), prop="categoryinfo"):
            ci = p.get("categoryinfo") or {}
            out[p["title"]] = {"files": ci.get("files", 0), "subcats": ci.get("subcats", 0), "missing": bool(p.get("missing"))}
    return out


def info(args) -> int:
    input_path, output_dir = Path(args.input), Path(args.output)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    raw_lines = input_path.read_text(encoding="utf-8-sig").splitlines()
    urls = read_urls(input_path)
    client = Client(args.user_agent, args.delay)
    output_dir.mkdir(parents=True, exist_ok=True)

    seen, entries = set(), []
    for url in urls:
        try:
            kind, title = parse_commons_url(url)
        except SkipUrl as e:
            entries.append({"url": url, "status": f"skipped: {e}"})
            continue
        if title in seen:
            entries.append({"url": url, "status": "duplicate of an earlier line"})
            continue
        seen.add(title)
        entries.append({"url": url, "kind": kind, "title": title, "status": "ok"})

    print(f"Counting {len([e for e in entries if e['status'] == 'ok'])} page(s)...")
    cats = [e for e in entries if e.get("kind") == "category"]
    counts = category_counts(client, [e["title"] for e in cats]) if cats else {}
    files = [e for e in entries if e.get("kind") == "file"]
    file_state = {}
    for group in chunks([e["title"] for e in files]):
        for p in client.pages(COMMONS_API, action="query", titles="|".join(group), prop="imageinfo", iiprop="mime"):
            file_state[p["title"]] = (p.get("imageinfo") or [{}])[0].get("mime") if "imageinfo" in p else None

    total_rows, lines = 0, []
    for e in entries:
        if e["status"] != "ok":
            lines.append(f"  {e['url']}\n    {e['status']}")
        elif e["kind"] == "file":
            mime = file_state.get(e["title"])
            n = 1 if mime and mime.startswith("image/") else 0
            total_rows += n
            lines.append(f"  {e['url']}\n    file: {e['title']}  ->  {n} row" + ("" if mime else "  (not found)") + (f"  ({mime})" if mime and not n else ""))
        else:
            c = counts.get(e["title"], {"files": 0, "subcats": 0, "missing": True})
            if c["missing"]:
                lines.append(f"  {e['url']}\n    category: {e['title']}  ->  not found")
                continue
            sub_note, level_files = "", c["files"]
            if args.subcats:
                visited, queue, deep = {e["title"]}, [(e["title"], 0)], 0
                while queue:
                    cat, level = queue.pop(0)
                    if level >= args.subcats:
                        continue
                    for p in client.pages(COMMONS_API, action="query", generator="categorymembers", gcmtitle=cat, gcmtype="subcat",
                                          gcmlimit=BATCH, prop="categoryinfo"):
                        if p["title"] in visited:
                            continue
                        visited.add(p["title"])
                        deep += (p.get("categoryinfo") or {}).get("files", 0)
                        queue.append((p["title"], level + 1))
                sub_note = f"; {len(visited) - 1} sub-categories down to level {args.subcats} hold {deep} more"
                level_files += deep
            total_rows += level_files
            lines.append(f"  {e['url']}\n    category: {e['title']}  ->  {c['files']} files, {c['subcats']} sub-categories{sub_note}")

    ok = [e for e in entries if e["status"] == "ok"]
    requests_est = math.ceil(total_rows / BATCH) * 5 + len(ok)
    seconds_est = requests_est * (args.delay + 0.6)
    existing = sorted(output_dir.glob("commons_*.csv"))
    report = [
        "commons_to_csv info",
        f"Created      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Input file   : {input_path}",
        f"Sub-categories counted to level: {args.subcats}",
        "",
        "urls.txt",
        f"  Lines                       : {len(raw_lines)}",
        f"  URLs                        : {len(urls)}",
        f"  Comments / blank lines      : {len(raw_lines) - len(urls)}",
        f"  Category pages              : {len(cats)}",
        f"  File pages                  : {len(files)}",
        f"  Duplicates                  : {sum(1 for e in entries if e['status'].startswith('duplicate'))}",
        f"  Skipped (special/unsupported): {sum(1 for e in entries if e['status'].startswith('skipped'))}",
        "",
        "PER URL",
        *lines,
        "",
        "TOTALS",
        f"  Rows the CSV would have     : about {total_rows}  (an upper bound: a file in several of these categories is written once)",
        f"  Rough requests              : about {requests_est}  (roughly 5 per {BATCH} images, plus 1 per URL; taxonomy lookups add more)",
        f"  Rough run time              : about {seconds_est / 60:.0f} min at --delay {args.delay} (longer when Commons asks to slow down)",
        "",
        f"EXISTING CSVs in {output_dir} ({len(existing)})",
    ]
    for p in existing:
        with open(p, newline="", encoding="utf-8") as fh:
            report.append(f"  {p.name}: {max(sum(1 for _ in fh) - 1, 0)} rows")
    if not existing:
        report.append("  (none)")
    report.append("")
    info_path = output_dir / "info.txt"
    info_path.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Written: {info_path}  ({client.requests_made} requests)")
    return 0


# --------------------------------------------------------------------------
# --md: CSV -> markdown gallery
# --------------------------------------------------------------------------

def parse_row_ranges(text: str, total: int) -> set[int]:
    """'1-20,35' -> {1..20, 35} (1 = first data row of the CSV)."""
    wanted = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise SystemExit(f"--rows must look like 1-20,35 (got {part!r})")
        lo, hi = int(m[1]), int(m[2] or m[1])
        wanted.update(range(lo, min(hi, total) + 1))
    return wanted


def pick_size_column(row: dict, size: int) -> str:
    """The url_<width> column nearest to the requested size, else the original."""
    cols = sorted(int(k[4:]) for k in row if re.fullmatch(r"url_\d+", k) and row[k])
    if not cols:
        return row.get("url_original", "")
    best = min(cols, key=lambda w: (abs(w - size), w))
    return row[f"url_{best}"]


def make_gallery(args) -> int:
    output_dir = Path(args.output)
    if args.md == "latest":
        found = sorted(output_dir.glob("commons_*.csv"))
        if not found:
            print(f"No commons_*.csv in {output_dir}. Pass the CSV: --md path/to/file.csv", file=sys.stderr)
            return 1
        csv_path = found[-1]
    else:
        csv_path = Path(args.md)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    started = datetime.now()
    keep = parse_row_ranges(args.rows, len(rows)) if args.rows else set(range(1, len(rows) + 1))

    def has(row, field, needles):
        hay = [h.lower() for h in row.get(field, "").split("|")]
        return any(n.lower() in h for n in needles for h in hay)

    chosen = []
    for n, row in enumerate(rows, 1):
        if n not in keep:
            continue
        if args.category and not any(has(row, "categories", [c]) or has(row, "collection", [c]) or has(row, "theme", [c]) for c in args.category):
            continue
        if args.tag and not any(has(row, "tags", [t]) for t in args.tag):
            continue
        chosen.append((n, row))

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = new_stamp(output_dir, ["gallery_{stamp}.md", "log_{stamp}.txt"])
    md_path, log_path = output_dir / f"gallery_{stamp}.md", output_dir / f"log_{stamp}.txt"

    filters = {k: v for k, v in {"rows": args.rows, "category": args.category, "tag": args.tag}.items() if v}
    title = args.title or f"Commons gallery {stamp}"
    front = {
        "title": title, "source_csv": csv_path.name, "filters": filters or "none",
        "images": len(chosen), "image_size": args.size, "created": started.strftime("%Y-%m-%d"),
    }
    parts = [f"---\n{yaml.dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)}---\n", f"# {title}\n"]
    for n, row in chosen:
        img = pick_size_column(row, args.size)
        block = [f"## {row['title'] or row['file_name']}", ""]
        if img:
            block.append(f"![{(row['title'] or row['file_name']).replace(']', ')')}]({md_url(img)})\n")
        if row.get("description"):
            block.append(row["description"] + "\n")
        if row.get("taxonomy"):
            block.append(f"**Taxonomy:** {row['taxonomy']}\n")
        if row.get("categories"):
            block.append("**Categories:** " + ", ".join(row["categories"].split("|")) + "\n")
        if row.get("tags"):
            block.append(" ".join("#" + t for t in row["tags"].split("|")) + "\n")
        block.append(f"{row.get('attribution', '')}  \nrow {n} · [file page]({md_url(row['page_url'])})\n")
        parts.append("\n".join(block))
    md_path.write_text("\n".join(parts), encoding="utf-8")

    warnings = []
    if not chosen:
        warnings.append((str(csv_path), "no rows matched the filters; the gallery is empty"))
    write_results_log(
        log_path,
        {
            "tool": "commons_to_csv --md", "started": started.strftime("%Y-%m-%d %H:%M:%S"), "input": str(csv_path),
            "output": str(md_path), "options": f"filters={filters or 'none'} size={args.size}", "total": len(rows),
            "processed": len(rows), "interrupted": False, "rows": len(chosen),
        },
        [(str(csv_path), md_path.name, f"{len(chosen)} of {len(rows)} rows")], [], [], [], warnings,
    )
    print(f"Gallery: {md_path}  ({len(chosen)} of {len(rows)} rows)\nLog: {log_path}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Wikimedia Commons File:/Category: URLs -> timestamped CSV, with --info and --md.")
    ap.add_argument("--input", default="urls.txt", help="Path to file of Commons URLs (default: urls.txt)")
    ap.add_argument("--output", default="commons-out", help="Output folder for CSV, log, info.txt and galleries (default: commons-out)")
    ap.add_argument("--subcats", type=int, default=0, help="Also read sub-categories this many levels down (default 0)")
    ap.add_argument("--sizes", default=DEFAULT_SIZES, help=f"Image widths to give a url_<width> column for (default {DEFAULT_SIZES}); Commons only serves {','.join(map(str, STANDARD_WIDTHS))}")
    ap.add_argument("--limit", type=int, default=0, help="Stop after this many files per category (default: all)")
    ap.add_argument("--max-desc", type=int, default=2000, help="Cut descriptions at this many characters (default 2000, 0 = never)")
    ap.add_argument("--no-taxonomy", action="store_true", help="Skip the Wikidata taxonomy lookups (faster)")
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (default 1)")
    ap.add_argument("--user-agent", default=os.environ.get("WIKI_USER_AGENT", DEFAULT_UA), help="User-Agent with contact information (or set WIKI_USER_AGENT)")
    ap.add_argument("--info", action="store_true", help="Write info.txt about urls.txt and the file counts; no CSV")
    ap.add_argument("--md", nargs="?", const="latest", metavar="CSV", help="Turn a CSV into a markdown gallery (default: the newest commons_*.csv in the output folder)")
    ap.add_argument("--rows", help="With --md: CSV rows to include, e.g. 1-20,35 (1 = first data row)")
    ap.add_argument("--category", action="append", help="With --md: only rows whose categories/collection/theme contain this text (repeatable)")
    ap.add_argument("--tag", action="append", help="With --md: only rows with a tag containing this text (repeatable)")
    ap.add_argument("--size", type=int, default=500, help="With --md: image width to show (nearest available column, default 500)")
    ap.add_argument("--title", help="With --md: the gallery title")
    args = ap.parse_args()

    if args.md is not None:
        return make_gallery(args)
    if args.info:
        return info(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
