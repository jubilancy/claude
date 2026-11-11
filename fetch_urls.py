#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["html2text"]
# ///
"""
fetch_urls.py

Reads URLs (one per line) from urls.txt, fetches each page politely
(rate-limited, with exponential backoff on 429 / errors), converts the
HTML to Markdown, and saves each page to its own .md file with the
source URL stored in YAML front matter.

Pagination: after each page, the script looks for a "next page" and follows
it, saving every page as its own file. Detection order (first hit wins):

  1. HTTP `Link: <...>; rel="next"` response header
  2. <link rel="next" href="..."> in the HTML
  3. <a rel="next" href="..."> in the HTML
  4. Heuristic anchors: text/aria-label/title such as "Next", "Next page",
     "Older posts", "Load more", ">", "›", "»", "→", or a class/id
     containing "next" (skipping disabled / prev / back / first / last)
  5. Page-number increment, if the URL already carries one:
     ?page=N, ?p=N, ?paged=N, ?pg=N, ... or a /page/N/ path segment

Safeguards: same-host only, never revisits a URL, stops when a page's
content duplicates an earlier one, on 404/error past page 1, or at
--max-pages.

Not supported: pagination driven purely by JavaScript (infinite scroll,
"Load more" buttons with no href, XHR/JSON cursors).

Usage:
    uv run fetch_urls.py [urls.txt] [output_dir] [--max-pages N] [--no-paginate]

Defaults:
    urls_file = urls.txt
    output_dir = ./output
    max_pages = 25
"""

import argparse
import hashlib
import html2text
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

# ---------- Config ----------
MIN_DELAY = 3          # seconds, minimum delay between requests
MAX_DELAY = 6          # seconds, maximum delay between requests (randomized)
MAX_RETRIES = 5        # retries per URL on failure/429
BACKOFF_BASE = 5        # base seconds for exponential backoff
TIMEOUT = 20            # request timeout in seconds
DEFAULT_MAX_PAGES = 25  # per starting URL
USER_AGENT = (
    "Mozilla/5.0 (compatible; PersonalArchiveBot/1.0; "
    "+https://eliana.lol) fetch_urls.py"
)

PAGE_PARAMS = {"page", "p", "paged", "pg", "pagenum", "page_num", "pagenumber", "pn"}


def slugify_from_url(url: str) -> str:
    """Build a filesystem-safe filename from a URL (query string included,
    so ?page=2 and ?page=3 get different names)."""
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/")

    base = f"{host}-{path}" if path else host
    if parsed.query:
        base = f"{base}-{parsed.query}"

    # replace path separators and unsafe chars
    base = re.sub(r"[\/]+", "-", base)
    base = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")

    if not base:
        base = "page"

    # keep filenames reasonable
    return base[:150]


def unique_path(base_path: str) -> str:
    """Avoid overwriting files that hash to the same name."""
    if not os.path.exists(base_path):
        return base_path
    root, ext = os.path.splitext(base_path)
    i = 2
    while os.path.exists(f"{root}-{i}{ext}"):
        i += 1
    return f"{root}-{i}{ext}"


def fetch_html(url: str):
    """Fetch a URL, retrying with exponential backoff on failure/429.
    Returns (html, response_headers, final_url_after_redirects)."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset, errors="replace")
                return body, resp.headers, resp.geturl()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                # Respect Retry-After if present, else exponential backoff
                retry_after = e.headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else BACKOFF_BASE * (2 ** (attempt - 1))
                except ValueError:  # Retry-After may be an HTTP date
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                print(f"  429 rate-limited. Waiting {wait:.0f}s (attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            elif 500 <= e.code < 600:
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                print(f"  Server error {e.code}. Waiting {wait:.0f}s (attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            else:
                # Non-retryable HTTP error (404, 403, etc.)
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            print(f"  Network error: {e}. Waiting {wait:.0f}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {last_err}")


# ---------- Link resolution (HTML -> absolute URLs) ----------

RESOLVABLE_ATTRS = {"href", "src", "srcset"}


class LinkResolver(HTMLParser):
    """Rewrites relative href/src/srcset attributes to absolute URLs
    using urllib.parse.urljoin, so every link/image survives the
    HTML -> Markdown conversion as a full, clickable URL."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=False)
        self.base_url = base_url
        self.out = []

    def _resolve_srcset(self, value: str) -> str:
        # srcset is a comma-separated list of "url descriptor" pairs
        parts = []
        for candidate in value.split(","):
            candidate = candidate.strip()
            if not candidate:
                continue
            bits = candidate.split()
            if bits:
                bits[0] = urljoin(self.base_url, bits[0])
            parts.append(" ".join(bits))
        return ", ".join(parts)

    def _emit_tag(self, tag, attrs, self_closing):
        pieces = [f"<{tag}"]
        for name, value in attrs:
            if value is None:
                pieces.append(f" {name}")
                continue
            if name in RESOLVABLE_ATTRS and value.strip():
                if name == "srcset":
                    value = self._resolve_srcset(value)
                else:
                    value = urljoin(self.base_url, value)
            escaped = value.replace('"', "&quot;")
            pieces.append(f' {name}="{escaped}"')
        pieces.append(" />" if self_closing else ">")
        self.out.append("".join(pieces))

    def handle_starttag(self, tag, attrs):
        self._emit_tag(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_tag(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def get_html(self) -> str:
        return "".join(self.out)


def resolve_relative_links(html: str, base_url: str) -> str:
    """Rewrite every relative href/src/srcset in the HTML to an absolute URL."""
    resolver = LinkResolver(base_url)
    resolver.feed(html)
    resolver.close()
    return resolver.get_html()


def html_to_markdown(html: str, base_url: str) -> str:
    html = resolve_relative_links(html, base_url)
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.body_width = 0  # don't hard-wrap lines
    return converter.handle(html)


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        return title
    return ""


def make_front_matter(url: str, title: str, page: int) -> str:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # escape double quotes in title for YAML safety
    safe_title = title.replace('"', "'")
    return (
        "---\n"
        f'source_url: "{url}"\n'
        f'title: "{safe_title}"\n'
        f"page: {page}\n"
        f"fetched_at: {fetched_at}\n"
        "---\n\n"
    )


# ---------- Pagination ----------

NEXT_WORD_RE = re.compile(r"^\W*(next|older|more|load more|show more|view more)\b.{0,20}$", re.I)
ARROW_ONLY_RE = re.compile(r"^[\s>›»→⟩❯▶▸…]*[>›»→⟩❯▶▸][\s>›»→⟩❯▶▸…]*$")
NEXT_CLASS_RE = re.compile(r"(^|[\s_-])next($|[\s_-])", re.I)
NEGATIVE_RE = re.compile(r"prev|back|first|last|newer|[«‹←<]", re.I)


class NextLinkFinder(HTMLParser):
    """Collects 'next page' candidates from <link> and <a> tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link_rel_next = None   # <link rel="next">
        self.a_rel_next = None      # <a rel="next">
        self.heuristic = None       # text/class based anchor
        self._a = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        href = a.get("href", "").strip()
        if tag == "link":
            if "next" in a.get("rel", "").lower().split() and href and not self.link_rel_next:
                self.link_rel_next = href
        elif tag == "a":
            if "next" in a.get("rel", "").lower().split() and href and not self.a_rel_next:
                self.a_rel_next = href
            self._a = {"attrs": a, "href": href, "text": []}

    def handle_data(self, data):
        if self._a is not None:
            self._a["text"].append(data)

    def handle_endtag(self, tag):
        if tag != "a" or self._a is None:
            return
        cur, self._a = self._a, None
        if self.heuristic or not cur["href"]:
            return
        if cur["href"].startswith(("#", "javascript:", "mailto:", "tel:")):
            return
        a = cur["attrs"]
        marker = f'{a.get("class", "")} {a.get("id", "")}'
        if "disabled" in marker.lower() or a.get("aria-disabled", "").lower() == "true":
            return
        label = " ".join(
            " ".join(cur["text"]).split() + a.get("aria-label", "").split() + a.get("title", "").split()
        ).strip()
        text_only = " ".join(" ".join(cur["text"]).split())
        if NEGATIVE_RE.search(label) or NEGATIVE_RE.search(marker):
            return
        if (
            NEXT_WORD_RE.match(text_only)
            or NEXT_WORD_RE.match(a.get("aria-label", "").strip())
            or NEXT_WORD_RE.match(a.get("title", "").strip())
            or ARROW_ONLY_RE.match(text_only)
            or NEXT_CLASS_RE.search(marker)
        ):
            self.heuristic = cur["href"]


def parse_link_header_next(header_value):
    """Extract rel="next" target from an HTTP Link header, or None."""
    if not header_value:
        return None
    for part in re.split(r",\s*(?=<)", header_value):
        m = re.match(r"\s*<([^>]*)>(.*)", part)
        if m and re.search(r'rel\s*=\s*"?[^";]*\bnext\b', m.group(2), re.I):
            return m.group(1)
    return None


def increment_page_url(url: str):
    """Bump ?page=N (and friends) or a /page/N/ path segment. None if absent."""
    parsed = urlparse(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    for i, (k, v) in enumerate(pairs):
        if k.lower() in PAGE_PARAMS and v.isdigit():
            pairs[i] = (k, str(int(v) + 1))
            return urlunparse(parsed._replace(query=urlencode(pairs)))
    m = re.search(r"(/(?:page|p)/)(\d+)(/?)$", parsed.path, re.I)
    if m:
        new_path = parsed.path[: m.start()] + m.group(1) + str(int(m.group(2)) + 1) + m.group(3)
        return urlunparse(parsed._replace(path=new_path))
    return None


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def find_next_url(html: str, headers, current_url: str, seen_urls: set):
    """Return (next_url, method) or (None, None)."""
    finder = NextLinkFinder()
    try:
        finder.feed(html)
        finder.close()
    except Exception:
        pass

    candidates = [
        (parse_link_header_next(headers.get("Link") if headers else None), "Link header"),
        (finder.link_rel_next, '<link rel="next">'),
        (finder.a_rel_next, '<a rel="next">'),
        (finder.heuristic, "next-link heuristic"),
    ]
    for href, method in candidates:
        if not href:
            continue
        absolute = urljoin(current_url, href).split("#")[0]
        if absolute in seen_urls or _host(absolute) != _host(current_url):
            continue
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        return absolute, method

    bumped = increment_page_url(current_url)
    if bumped and bumped not in seen_urls:
        return bumped, "page-number increment"
    return None, None


def polite_sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def crawl(seed_url: str, output_dir: str, max_pages: int, paginate: bool):
    """Fetch seed_url and (optionally) follow its pagination.
    Returns (pages_saved, error_or_None)."""
    seen_urls = set()
    seen_hashes = set()
    url = seed_url
    page = 1
    saved = 0

    while url and page <= max_pages:
        seen_urls.add(url)
        try:
            html, headers, final_url = fetch_html(url)
        except Exception as e:
            if page == 1:
                return saved, str(e)
            print(f"  Page {page} failed ({e}); assuming end of pagination.")
            break
        seen_urls.add(final_url)

        markdown_body = html_to_markdown(html, base_url=final_url)
        digest = hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            print(f"  Page {page} duplicates earlier content; stopping.")
            break
        seen_hashes.add(digest)

        front_matter = make_front_matter(final_url, extract_title(html), page)
        filename = slugify_from_url(final_url) + ".md"
        filepath = unique_path(os.path.join(output_dir, filename))
        with open(filepath, "w", encoding="utf-8") as out:
            out.write(front_matter + markdown_body)
        saved += 1
        print(f"  Saved page {page} -> {filepath}")

        if not paginate:
            break
        next_url, method = find_next_url(html, headers, final_url, seen_urls)
        if not next_url:
            print("  No next page found.")
            break
        print(f"  Next page via {method}: {next_url}")
        url = next_url
        page += 1
        polite_sleep()
    else:
        if paginate and url:
            print(f"  Reached --max-pages ({max_pages}); stopping.")

    return saved, None


def main():
    ap = argparse.ArgumentParser(description="Fetch URLs to Markdown, following pagination.")
    ap.add_argument("urls_file", nargs="?", default="urls.txt")
    ap.add_argument("output_dir", nargs="?", default="output")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    help=f"max pages followed per starting URL (default {DEFAULT_MAX_PAGES})")
    ap.add_argument("--no-paginate", action="store_true", help="fetch only the listed URLs")
    args = ap.parse_args()

    if not os.path.exists(args.urls_file):
        print(f"Error: {args.urls_file} not found.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    total = len(urls)
    print(f"Found {total} URL(s) in {args.urls_file}. Saving to '{args.output_dir}/'.\n")

    failures = []
    total_pages = 0

    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{total}] Fetching: {url}")
        saved, err = crawl(url, args.output_dir, max(1, args.max_pages), not args.no_paginate)
        total_pages += saved
        if err:
            print(f"  FAILED: {err}")
            failures.append((url, err))
        print()
        # polite randomized delay before next starting URL (skip after last one)
        if i < total:
            polite_sleep()

    print(f"Done. {total - len(failures)}/{total} URLs succeeded, {total_pages} page(s) saved.")
    if failures:
        print("\nFailed URLs:")
        for url, err in failures:
            print(f"  - {url}: {err}")


if __name__ == "__main__":
    main()
