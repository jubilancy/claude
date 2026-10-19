#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///

"""
Goodreads list / shelf fetcher
------------------------------
Reads a text file with one Goodreads URL per line (blank lines and lines
starting with # are ignored; anything after the URL on a line is ignored)
and writes one CSV (and optionally one Markdown) file per URL.

    uv run goodreads_fetch.py                       # urls.txt -> goodreads-out/
    uv run goodreads_fetch.py --format csv          # CSV only
    uv run goodreads_fetch.py --urls my.txt --out books --delay 5

Supported URLs:
  https://www.goodreads.com/list/show/925.Some_List
        Listopia list. Scraped from the HTML, page by page.
  https://www.goodreads.com/review/list/<user>?tag=<name>[&view=reviews]
  https://www.goodreads.com/review/list/<user>?shelf=<name>
  https://www.goodreads.com/review/list_rss/<user>?shelf=<name>
        A user's shelf or tag (Goodreads treats them the same). The HTML
        version of these pages now redirects to sign-in, so they are read
        from the public RSS feed instead. A profile set to private has no
        feed and is reported as an error.

Rate limiting: one request at a time, at least --delay seconds apart (plus
up to 50% random jitter). 429 / 5xx / network errors are retried with
exponential backoff and Retry-After is honoured. Existing output files are
skipped, so an interrupted run can simply be re-run; use --force to refetch.
"""

import argparse
import csv
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.goodreads.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
RSS_PER_PAGE = 200  # the feed honours this; 100 is the default


# --------------------------------------------------------------------------
# HTTP with rate limiting
# --------------------------------------------------------------------------

class Fetcher:
    def __init__(self, delay: float, retries: int, timeout: float, user_agent: str = USER_AGENT):
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en"})
        self._last = 0.0

    def _wait(self):
        gap = self.delay * (1 + random.random() * 0.5)
        sleep = self._last + gap - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)

    def get(self, url: str) -> requests.Response:
        backoff = max(self.delay, 2.0)
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                self._last = time.monotonic()
                err = f"{type(e).__name__}: {e}"
                retry_after = None
            else:
                self._last = time.monotonic()
                if resp.status_code < 400:
                    return resp
                if resp.status_code not in (429, 500, 502, 503, 504):
                    resp.raise_for_status()
                err = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
            if attempt == self.retries:
                raise RuntimeError(f"giving up on {url}: {err}")
            try:
                pause = float(retry_after) if retry_after else backoff
            except ValueError:
                pause = backoff
            print(f"    {err}; retry {attempt + 1}/{self.retries} in {pause:.0f}s", file=sys.stderr)
            time.sleep(pause)
            backoff *= 2
        raise AssertionError("unreachable")


# --------------------------------------------------------------------------
# URL handling
# --------------------------------------------------------------------------

def read_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # tolerate markdown links pasted straight in: [text](url "title")
        m = re.search(r"\]\((https?://[^\s)]+)", line)
        urls.append(m.group(1) if m else line.split()[0])
    return urls


def classify(url: str) -> tuple[str, dict]:
    """Return (kind, info) with kind in {'list', 'shelf'}."""
    p = urlparse(url)
    if not p.netloc.endswith("goodreads.com"):
        raise ValueError("not a goodreads.com URL")
    q = parse_qs(p.query)
    m = re.fullmatch(r"/list/show/(\d+)(?:\.([^/]+))?/?", p.path)
    if m:
        return "list", {"id": m.group(1), "slug": m.group(2) or "", "url": f"{BASE}{p.path}"}
    m = re.fullmatch(r"/review/list(?:_rss)?/(\d+)(?:-([^/?]+))?/?", p.path)
    if m:
        shelf = (q.get("shelf") or q.get("tag") or ["#ALL#"])[0]
        return "shelf", {"user_id": m.group(1), "user": m.group(2) or "", "shelf": shelf}
    raise ValueError("unsupported URL (expected /list/show/... or /review/list/...)")


def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:80] or "x"


def out_stem(kind: str, info: dict) -> str:
    if kind == "list":
        return f"list-{info['id']}-{slugify(info['slug'])}".rstrip("-")
    shelf = "all" if info["shelf"] == "#ALL#" else info["shelf"]
    return f"shelf-{info['user_id']}-{slugify(info['user'])}-{slugify(shelf)}".replace("--", "-")


# --------------------------------------------------------------------------
# Listopia lists (HTML)
# --------------------------------------------------------------------------

def to_int(s: str | None) -> int | None:
    if not s:
        return None
    s = s.replace(",", "")
    return int(s) if s.isdigit() else None


def parse_list_page(html: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table.tableList tr[itemtype$='schema.org/Book']"):
        title_a = tr.select_one("a.bookTitle")
        if not title_a:
            continue
        href = title_a.get("href", "")
        m = re.search(r"/book/show/(\d+)", href)
        authors = [a.get_text(strip=True) for a in tr.select("a.authorName")]
        author_urls = [a.get("href", "") for a in tr.select("a.authorName")]
        mini = tr.select_one(".minirating")
        mini_t = mini.get_text(" ", strip=True) if mini else ""
        avg = re.search(r"([\d.]+)\s+avg rating", mini_t)
        cnt = re.search(r"([\d,]+)\s+ratings?", mini_t)
        score = re.search(r"score:\s*([\d,]+)", tr.get_text(" ", strip=True))
        votes = re.search(r"([\d,]+)\s+people? voted", tr.get_text(" ", strip=True))
        img = tr.select_one("img.bookCover")
        rank = tr.select_one("td.number")
        rows.append({
            "rank": to_int(rank.get_text(strip=True)) if rank else None,
            "book_id": m.group(1) if m else "",
            "title": title_a.get_text(" ", strip=True),
            "author": "; ".join(authors),
            "avg_rating": avg.group(1) if avg else "",
            "ratings_count": to_int(cnt.group(1)) if cnt else None,
            "score": to_int(score.group(1)) if score else None,
            "votes": to_int(votes.group(1)) if votes else None,
            "book_url": urljoin(BASE, href.split("?")[0]),
            "author_url": "; ".join(author_urls),
            "cover_url": img.get("src", "") if img else "",
        })
    nxt = soup.select_one("div.pagination a[rel=next]")
    return rows, urljoin(BASE, nxt["href"]) if nxt else None


def list_meta(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1.gr-h1, h1")
    title = soup.title.get_text(strip=True) if soup.title else ""
    m = re.match(r"(.*?)\s*\(([\d,]+) books\)\s*$", title)
    desc = soup.select_one("meta[name=description]")
    return {
        "title": m.group(1) if m else (h1.get_text(strip=True) if h1 else title),
        "total": to_int(m.group(2)) if m else None,
        "description": desc.get("content", "") if desc else "",
    }


def fetch_list(f: Fetcher, info: dict, max_pages: int | None) -> tuple[dict, list[dict]]:
    url, books, seen, page, meta = info["url"], [], set(), 1, {}
    while url:
        print(f"  page {page}: {url}", file=sys.stderr)
        html = f.get(url).text
        if page == 1:
            meta = list_meta(html)
        rows, url = parse_list_page(html)
        new = [r for r in rows if (r["rank"], r["book_id"]) not in seen]
        if not new:
            break
        seen.update((r["rank"], r["book_id"]) for r in new)
        books += new
        if max_pages and page >= max_pages:
            break
        page += 1
    meta["source"] = info["url"]
    return meta, books


# --------------------------------------------------------------------------
# Open Library ISBN lookup / check
# --------------------------------------------------------------------------

OL_SEARCH = "https://openlibrary.org/search.json"


def ol_lookup(f: Fetcher, book_id: str) -> dict:
    """Open Library works indexed under this Goodreads book id: their ISBNs."""
    q = urlencode({"q": f"id_goodreads:{book_id}", "fields": "key,isbn", "limit": 1})
    data = f.get(f"{OL_SEARCH}?{q}").json()
    docs = data.get("docs") or []
    if not docs:
        return {"found": False}
    isbns = docs[0].get("isbn") or []
    return {"found": True, "work": docs[0].get("key", ""), "isbns": isbns}


def add_openlibrary(f: Fetcher, books: list[dict], cache_path: Path):
    """Add ol_status / ol_isbn13 / ol_isbn10 / ol_url to every book.

    Lookup is by Goodreads book id (Open Library records it as id_goodreads).
    A book that already has an ISBN (shelf rows) is checked against Open
    Library's ISBN list for that work: ol_status is 'verified' or
    'isbn_not_in_openlibrary'. A book without one gets Open Library's first
    ISBN-13/ISBN-10 for the work (ol_status 'found'); that is a work-level
    ISBN, not necessarily the exact Goodreads edition. Results are cached so
    an interrupted run resumes.
    """
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    todo = [b for b in books if b["book_id"] and b["book_id"] not in cache]
    print(f"  Open Library: {len(books) - len(todo)} cached, {len(todo)} to look up "
          f"(~{len(todo) * f.delay * 1.25 / 60:.0f} min)", file=sys.stderr)
    try:
        for i, b in enumerate(todo, 1):
            try:
                cache[b["book_id"]] = ol_lookup(f, b["book_id"])
            except Exception as e:  # leave uncached so the next run retries it
                print(f"    {b['book_id']}: {e}", file=sys.stderr)
            if i % 25 == 0:
                print(f"    {i}/{len(todo)}", file=sys.stderr)
                cache_path.write_text(json.dumps(cache))
    finally:
        cache_path.write_text(json.dumps(cache))
    for b in books:
        c = cache.get(b["book_id"])
        isbns = (c or {}).get("isbns", [])
        i13 = [x for x in isbns if len(x) == 13]
        i10 = [x for x in isbns if len(x) == 10]
        have = (b.get("isbn") or "").replace("-", "")
        if c is None:
            status = "lookup_failed"
        elif not c["found"]:
            status = "book_not_in_openlibrary"
        elif have:
            status = "verified" if have in isbns else "isbn_not_in_openlibrary"
        else:
            status = "found" if isbns else "no_isbn_in_openlibrary"
        b["ol_status"] = status
        b["ol_isbn13"] = i13[0] if i13 else ""
        b["ol_isbn10"] = i10[0] if i10 else ""
        b["ol_url"] = f"https://openlibrary.org{c['work']}" if c and c.get("work") else ""


# --------------------------------------------------------------------------
# User shelves / tags (RSS)
# --------------------------------------------------------------------------

def html_to_text(s: str | None) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s.replace("<br/>", "\n").replace("<br>", "\n"), "html.parser")
    return re.sub(r"\n{3,}", "\n\n", soup.get_text()).strip()


def iso_date(s: str) -> str:
    """RFC 2822 feed dates -> YYYY-MM-DD ('' if missing/unparseable)."""
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        return ""


def parse_rss(xml_text: str) -> tuple[str, list[dict]]:
    root = ET.fromstring(xml_text)
    chan = root.find("channel")
    title = (chan.findtext("title") or "").strip()
    books = []
    for it in chan.findall("item"):
        t = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
        book_id = t("book_id")
        review_url = t("link").split("?")[0]
        books.append({
            "book_id": book_id,
            "title": t("title"),
            "author": t("author_name"),
            "isbn": t("isbn"),
            "avg_rating": t("average_rating"),
            "my_rating": t("user_rating"),
            "num_pages": (it.find("book/num_pages").text or "").strip()
                         if it.find("book/num_pages") is not None else "",
            "year_published": t("book_published"),
            "date_read": iso_date(t("user_read_at")),
            "date_added": iso_date(t("user_date_added")),
            "shelves": t("user_shelves"),
            "book_url": f"{BASE}/book/show/{book_id}" if book_id else "",
            "review_url": review_url,
            "cover_url": t("book_large_image_url"),
            "description": html_to_text(t("book_description")),
            "review": html_to_text(t("user_review")),
        })
    return title, books


def fetch_shelf(f: Fetcher, info: dict, max_pages: int | None) -> tuple[dict, list[dict]]:
    books, seen, page, title = [], set(), 1, ""
    while True:
        params = {"shelf": info["shelf"], "per_page": RSS_PER_PAGE, "page": page}
        url = f"{BASE}/review/list_rss/{info['user_id']}?{urlencode(params)}"
        print(f"  page {page}: {url}", file=sys.stderr)
        resp = f.get(url)
        if "xml" not in resp.headers.get("Content-Type", "") or "<rss" not in resp.text[:500]:
            raise RuntimeError("no RSS feed returned (profile private or shelf unavailable)")
        title, rows = parse_rss(resp.text)
        new = [r for r in rows if r["review_url"] not in seen]
        if not new:
            break
        seen.update(r["review_url"] for r in new)
        books += new
        if len(rows) < RSS_PER_PAGE or (max_pages and page >= max_pages):
            break
        page += 1
    for i, b in enumerate(books, 1):
        b["rank"] = i
    meta = {
        "title": title,
        "total": len(books),
        "description": "",
        "source": f"{BASE}/review/list/{info['user_id']}?shelf={info['shelf']}",
    }
    return meta, books


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def write_csv(path: Path, books: list[dict]):
    cols = list(books[0]) if books else []
    # rank first, everything else in record order
    cols = (["rank"] if "rank" in cols else []) + [c for c in cols if c != "rank"]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(books)


MD_COLS = {
    "list": ["rank", "title", "author", "avg_rating", "ratings_count", "score", "votes",
             "ol_isbn13", "ol_isbn10", "ol_status"],
    "shelf": ["title", "author", "my_rating", "avg_rating", "year_published",
              "num_pages", "date_read", "isbn", "ol_status", "shelves"],
}
MD_HEAD = {
    "rank": "#", "avg_rating": "Avg", "ratings_count": "Ratings", "my_rating": "My rating",
    "year_published": "Year", "num_pages": "Pages", "date_read": "Read", "isbn": "ISBN",
    "ol_isbn13": "ISBN-13 (OL)", "ol_isbn10": "ISBN-10 (OL)", "ol_status": "Open Library",
}


def md_cell(v) -> str:
    return str("" if v is None else v).replace("|", "\\|").replace("\n", " ").strip()


def write_md(path: Path, kind: str, meta: dict, books: list[dict]):
    cols = [c for c in MD_COLS[kind] if books and c in books[0]]
    lines = [f"# {meta['title']}", "", f"Source: <{meta['source']}>  ",
             f"Books fetched: {len(books)}"
             + (f" (Goodreads reports {meta['total']})" if kind == "list" and meta.get("total") else ""),
             f"Fetched: {time.strftime('%Y-%m-%d')}", ""]
    if kind == "list" and meta.get("description"):
        lines += [f"> {meta['description']}", ""]
    lines.append("| " + " | ".join(MD_HEAD.get(c, c.replace("_", " ").title()) for c in cols) + " |")
    lines.append("|" + "|".join("---" for _ in cols) + "|")
    for b in books:
        cells = []
        for c in cols:
            v = md_cell(b.get(c))
            if c == "title" and b.get("book_url"):
                v = f"[{v}]({b['book_url']})"
            cells.append(v)
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Goodreads lists and shelves to CSV/Markdown.")
    ap.add_argument("--urls", default="urls.txt", type=Path, help="file with one URL per line (default urls.txt)")
    ap.add_argument("--out", default="goodreads-out", type=Path, help="output directory")
    ap.add_argument("--format", default="csv,md",
                    help="comma-separated output formats: csv, md (default csv,md)")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="minimum seconds between requests, plus up to 50%% jitter (default 3)")
    ap.add_argument("--retries", type=int, default=4, help="retries per request (default 4)")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--openlibrary", action="store_true",
                    help="look every book up on Open Library by Goodreads id: fill in ISBNs "
                         "for list books, verify the ISBN on shelf books "
                         "(cached in OUT/.openlibrary-cache.json)")
    ap.add_argument("--ol-delay", type=float, default=1.0,
                    help="minimum seconds between Open Library requests (default 1)")
    ap.add_argument("--max-pages", type=int, help="stop after N pages per URL (for testing)")
    ap.add_argument("--force", action="store_true", help="refetch even if output files exist")
    args = ap.parse_args()

    formats = {x.strip().lower() for x in args.format.split(",") if x.strip()}
    if not formats or formats - {"csv", "md"}:
        ap.error("--format must be csv, md, or csv,md")
    if not args.urls.exists():
        ap.error(f"{args.urls} not found")

    urls = read_urls(args.urls)
    args.out.mkdir(parents=True, exist_ok=True)
    f = Fetcher(args.delay, args.retries, args.timeout)
    ol = Fetcher(args.ol_delay, args.retries, args.timeout, user_agent="goodreads-fetch/1.0 (personal script)")
    failures = 0

    for n, url in enumerate(urls, 1):
        print(f"[{n}/{len(urls)}] {url}", file=sys.stderr)
        try:
            kind, info = classify(url)
            stem = out_stem(kind, info)
            targets = {fmt: args.out / f"{stem}.{fmt}" for fmt in formats}
            if not args.force and all(p.exists() for p in targets.values()):
                print("  already done, skipping (use --force to refetch)", file=sys.stderr)
                continue
            meta, books = (fetch_list if kind == "list" else fetch_shelf)(f, info, args.max_pages)
            if not books:
                raise RuntimeError("no books found")
            if args.openlibrary:
                add_openlibrary(ol, books, args.out / ".openlibrary-cache.json")
            if "csv" in formats:
                write_csv(targets["csv"], books)
            if "md" in formats:
                write_md(targets["md"], kind, meta, books)
            print(f"  {len(books)} books -> {', '.join(str(p) for p in targets.values())}", file=sys.stderr)
        except Exception as e:  # keep going; report at the end
            failures += 1
            print(f"  ERROR: {e}", file=sys.stderr)

    if failures:
        print(f"{failures} of {len(urls)} URLs failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
