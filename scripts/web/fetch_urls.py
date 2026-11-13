#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["html2text", "playwright"]
# ///
"""
fetch_urls.py - all-in-one polite scraper

Reads URLs (one per line) from urls.txt, fetches each page politely
(rate-limited, exponential backoff on 429 / errors), and saves it:
  * HTML  -> Markdown (.md) with the source URL in YAML front matter
  * JSON  -> pretty-printed .json
Then it follows pagination and saves every page as its own file.

STATIC MODE (default; plain HTTP, fast) finds the next page via, in order:
  1. HTTP `Link: <...>; rel="next"` header
  2. <link rel="next"> / <a rel="next">
  3. Heuristic anchors: "Next", "Older posts", "Load more", ">", "›", "»", "→",
     or a class/id containing "next" (skips disabled / prev / back / first / last)
  4. Numbered pagers with no "next" link: finds the current page number
     (aria-current / active / current / selected) and follows N+1
  5. Page-number increment when the URL has ?page=N, ?p=N, ?paged=N, /page/N/
  JSON responses (REST / cursor APIs) are detected automatically and followed via:
  Link header, "next" URL fields (next, next_url, _links.next.href, @odata.nextLink...),
  cursors (next_cursor, endCursor, nextPageToken, next_token, continuation...),
  page numbers (page / total_pages / has_more), and offset/skip/start.

JS MODE (--js; headless Chromium) additionally handles pages that need JavaScript:
  * infinite scroll (scrolls the window and inner scroll containers until stable)
  * "Load more" / "Show more" buttons and links with no real href (clicked until gone)
  * "Next" buttons and numbered pagers with no href (clicked, state saved per page)
  * everything the static finder does, on the rendered DOM
  * --capture-api saves the JSON (XHR/fetch) responses the page makes, and prints
    the endpoints so you can paginate them directly in static mode

Safeguards: same host only, never revisits a URL, stops on duplicate content,
on 404/error past page 1, or at --max-pages.

Not supported: POST/GraphQL APIs, logins, CAPTCHAs.

Usage:
    uv run scripts/web/fetch_urls.py [urls.txt] [output_dir] [options]

Options:
    --max-pages N     pages followed per starting URL (default 25)
    --no-paginate     fetch only the listed URLs
    --js              render with headless Chromium (needs a browser, see below)
    --max-scrolls N   JS mode: max scroll/"load more" steps per page (default 30)
    --capture-api     JS mode: save JSON responses the page fetches
    --chromium-path P JS mode: Chromium executable (or set CHROMIUM_PATH)

JS mode needs a browser once:
    uv run --with playwright python -m playwright install chromium
"""

import argparse
import hashlib
import html2text
import json
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
DEFAULT_MAX_SCROLLS = 30
SETTLE_MS = 700         # JS mode: pause after each scroll/click
USER_AGENT = (
    "Mozilla/5.0 (compatible; PersonalArchiveBot/1.0; "
    "+https://eliana.lol) fetch_urls.py"
)

PAGE_PARAMS = {"page", "p", "paged", "pg", "pagenum", "page_num", "pagenumber", "pn"}


# ---------- Filenames ----------

def slugify_from_url(url: str) -> str:
    """Build a filesystem-safe filename from a URL (query string included,
    so ?page=2 and ?page=3 get different names)."""
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/")

    base = f"{host}-{path}" if path else host
    if parsed.query:
        base = f"{base}-{parsed.query}"

    base = re.sub(r"[\/]+", "-", base)
    base = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return (base or "page")[:150]


def unique_path(base_path: str) -> str:
    """Avoid overwriting files that hash to the same name."""
    if not os.path.exists(base_path):
        return base_path
    root, ext = os.path.splitext(base_path)
    i = 2
    while os.path.exists(f"{root}-{i}{ext}"):
        i += 1
    return f"{root}-{i}{ext}"


# ---------- HTTP ----------

def fetch_html(url: str):
    """Fetch a URL, retrying with exponential backoff on failure/429.
    Returns (body, response_headers, final_url_after_redirects)."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset, errors="replace")
                return body, resp.headers, resp.geturl()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
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
                raise  # non-retryable (404, 403, ...)
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
    """Rewrites relative href/src/srcset attributes to absolute URLs so every
    link/image survives the HTML -> Markdown conversion as a full URL."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=False)
        self.base_url = base_url
        self.out = []

    def _resolve_srcset(self, value: str) -> str:
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
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def make_front_matter(url: str, title: str, page: int) -> str:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_title = title.replace('"', "'")
    return (
        "---\n"
        f'source_url: "{url}"\n'
        f'title: "{safe_title}"\n'
        f"page: {page}\n"
        f"fetched_at: {fetched_at}\n"
        "---\n\n"
    )


# ---------- HTML pagination: next-link detection ----------

NEXT_WORD_RE = re.compile(r"^\W*(next|older|more|load more|show more|view more)\b.{0,20}$", re.I)
ARROW_ONLY_RE = re.compile(r"^[\s>›»→⟩❯▶▸…]*[>›»→⟩❯▶▸][\s>›»→⟩❯▶▸…]*$")
NEXT_CLASS_RE = re.compile(r"(^|[\s_-])next($|[\s_-])", re.I)
NEGATIVE_RE = re.compile(r"prev|back|first|last|newer|[«‹←<]", re.I)
ACTIVE_RE = re.compile(r"(^|[\s_-])(active|current|selected)($|[\s_-])", re.I)
PAGER_RE = re.compile(
    r"pagin|pager|paging|page[-_]?(?:num|link|item|list|nav|numbers)|(?:^|[\s_-])pages(?:$|[\s_-])", re.I)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
LOADMORE_HINT_RE = re.compile(r"load\s*more|show\s*more|view\s*more|infinite|IntersectionObserver", re.I)


def _is_active(attrs):
    aria = attrs.get("aria-current", "")
    return bool(ACTIVE_RE.search(attrs.get("class", ""))) or (aria not in ("", "false"))


class NextLinkFinder(HTMLParser):
    """Collects 'next page' candidates from <link> and <a> tags, plus a
    numbered-pager map (page number -> href) and the current page number."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link_rel_next = None   # <link rel="next">
        self.a_rel_next = None      # <a rel="next">
        self.heuristic = None       # text/class based anchor
        self.numbered = {}          # {page number: href} from pager links
        self.current_num = None     # page number marked active/current
        self._a = None
        self._stack = []

    def _in_pager(self):
        for _, at in self._stack:
            if PAGER_RE.search(f'{at.get("class", "")} {at.get("id", "")} {at.get("aria-label", "")}'):
                return True
        return False

    def _pop(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        href = a.get("href", "").strip()
        if tag not in VOID_TAGS:
            self._stack.append((tag, a))
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
        t = data.strip()
        if t.isdigit() and len(t) <= 4 and self._stack:
            if any(_is_active(at) for _, at in self._stack[-3:]) and self._in_pager():
                self.current_num = int(t)

    def handle_endtag(self, tag):
        if tag != "a":
            self._pop(tag)
            return
        in_pager = self._in_pager()
        self._pop(tag)
        if self._a is None:
            return
        cur, self._a = self._a, None
        href = cur["href"]
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return
        a = cur["attrs"]
        text_only = " ".join(" ".join(cur["text"]).split())

        # numbered pager link
        if text_only.isdigit() and len(text_only) <= 4:
            n = int(text_only)
            if in_pager or a.get("rel", "") or _is_active(a):
                self.numbered.setdefault(n, href)
            if _is_active(a) and in_pager:
                self.current_num = n

        if self.heuristic:
            return
        marker = f'{a.get("class", "")} {a.get("id", "")}'
        if "disabled" in marker.lower() or a.get("aria-disabled", "").lower() == "true":
            return
        label = " ".join(text_only.split() + a.get("aria-label", "").split() + a.get("title", "").split())
        if NEGATIVE_RE.search(label) or NEGATIVE_RE.search(marker):
            return
        if (
            NEXT_WORD_RE.match(text_only)
            or NEXT_WORD_RE.match(a.get("aria-label", "").strip())
            or NEXT_WORD_RE.match(a.get("title", "").strip())
            or ARROW_ONLY_RE.match(text_only)
            or NEXT_CLASS_RE.search(marker)
        ):
            self.heuristic = href


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


def _plausible_page_link(current_url: str, candidate: str, n: int) -> bool:
    """A numbered link is a real pager link if its URL contains the number,
    or it only differs from the current URL by query string."""
    c, u = urlparse(candidate), urlparse(current_url)
    if str(n) in re.findall(r"\d+", f"{c.path}?{c.query}"):
        return True
    return c.path == u.path


def _numbered_candidate(finder, current_url, seen_urls):
    nums = finder.numbered
    if not nums:
        return None
    if finder.current_num is not None:
        order = [finder.current_num + 1]
    else:
        order = sorted(n for n in nums if n >= 2)
    for n in order:
        href = nums.get(n)
        if not href:
            continue
        absolute = urljoin(current_url, href).split("#")[0]
        if absolute in seen_urls or absolute == current_url or _host(absolute) != _host(current_url):
            continue
        if urlparse(absolute).scheme in ("http", "https") and _plausible_page_link(current_url, absolute, n):
            return absolute
    return None


def find_next_url(html, headers, current_url, seen_urls, allow_increment=True):
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

    numbered = _numbered_candidate(finder, current_url, seen_urls)
    if numbered:
        return numbered, "numbered pager"

    if allow_increment:
        bumped = increment_page_url(current_url)
        if bumped and bumped not in seen_urls:
            return bumped, "page-number increment"
    return None, None


# ---------- JSON / API pagination ----------

URL_KEYS = ("next", "nexturl", "nextpageurl", "nextlink", "@odata.nextlink", "nextpage")
CURSOR_KEYS = {  # normalized response key -> default request param
    "nextcursor": "cursor", "cursor": "cursor", "endcursor": "after", "after": "after",
    "nextpagetoken": "pageToken", "nexttoken": "next_token",
    "continuation": "continuation", "continuationtoken": "continuation_token",
}
CURSOR_ALIASES = ("cursor", "after", "pagetoken", "nexttoken", "continuation", "continuationtoken", "startingafter")
MORE_FLAGS = ("hasnextpage", "hasmore", "hasnext", "more")
TOTAL_PAGES_KEYS = ("totalpages", "lastpage", "pagecount", "numpages", "pages")
CURRENT_PAGE_KEYS = ("currentpage", "pagenumber", "pageno", "page")
TOTAL_ITEMS_KEYS = ("total", "totalcount", "totalresults", "totalitems")
OFFSET_PARAMS = ("offset", "skip", "start", "from")
DATA_LIST_KEYS = ("items", "results", "data", "records", "entries", "nodes", "hits", "posts", "list")


def _norm(key: str) -> str:
    return re.sub(r"[_\-\s]", "", str(key).lower())


def _walk(obj, depth=0):
    """Yield (key, value) for dict entries up to 3 levels deep (dicts only)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            if depth < 3 and isinstance(v, dict):
                yield from _walk(v, depth + 1)


def set_query_param(url: str, key: str, value) -> str:
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != key]
    pairs.append((key, str(value)))
    return urlunparse(p._replace(query=urlencode(pairs)))


def _query_map(url: str):
    """normalized param name -> (original name, value)"""
    return {_norm(k): (k, v) for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True)}


def main_list(data):
    """The record list in a JSON response (largest list; [] if only empty data lists)."""
    if isinstance(data, list):
        return data
    best, empty_data = None, False
    for k, v in _walk(data):
        if isinstance(v, list):
            if v and (best is None or len(v) > len(best)):
                best = v
            elif not v and _norm(k) in DATA_LIST_KEYS:
                empty_data = True
    if best is not None:
        return best
    return [] if empty_data else None


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def find_next_json(data, headers, url):
    """Return (next_url, method) for a JSON API response, or (None, None)."""
    link = parse_link_header_next(headers.get("Link") if headers else None)
    if link:
        return urljoin(url, link), "Link header"

    items = main_list(data)
    if items is not None and len(items) == 0:
        return None, None
    if not isinstance(data, dict):
        return None, None

    flat = {}
    for k, v in _walk(data):
        flat.setdefault(_norm(k), v)

    # 1. A ready-made next URL
    for key in URL_KEYS:
        v = flat.get(key)
        if isinstance(v, dict):
            v = v.get("href") or v.get("url")
        if isinstance(v, str) and re.match(r"^(https?://|/|\?)", v):
            return urljoin(url, v), f"JSON '{key}' URL"

    # 2. Explicit "no more" flags
    for key in MORE_FLAGS:
        if flat.get(key) is False:
            return None, None

    q = _query_map(url)

    # 3. Cursor / token
    for key, default in CURSOR_KEYS.items():
        v = flat.get(key)
        if v is None or isinstance(v, (bool, dict, list)) or str(v) == "":
            continue
        alias = next((a for a in CURSOR_ALIASES if a in q), None)
        name = q[alias][0] if alias else default
        if alias and q[alias][1] == str(v):
            continue  # echo of the current cursor, not a next one
        return set_query_param(url, name, v), f"JSON cursor '{key}'"

    # 4. Offset / skip / start
    total = next((_int(flat[k]) for k in TOTAL_ITEMS_KEYS if _int(flat.get(k)) is not None), None)
    for a in OFFSET_PARAMS:
        if a in q and q[a][1].isdigit() and items:
            new = int(q[a][1]) + len(items)
            if total is not None and new >= total:
                return None, None
            return set_query_param(url, q[a][0], new), "JSON offset"

    # 5. Page number
    pname = next((a for a in (_norm(p) for p in PAGE_PARAMS) if a in q and q[a][1].isdigit()), None)
    cur = int(q[pname][1]) if pname else None
    if cur is None:
        cur = next((_int(flat[k]) for k in CURRENT_PAGE_KEYS if _int(flat.get(k)) is not None), None)
    nextp = _int(flat.get("nextpage"))
    if cur is not None or nextp is not None:
        target = nextp if nextp is not None else cur + 1
        last = next((_int(flat[k]) for k in TOTAL_PAGES_KEYS if _int(flat.get(k)) is not None), None)
        if last is not None and target > last:
            return None, None
        name = q[pname][0] if pname else "page"
        return set_query_param(url, name, target), "JSON page number"
    return None, None


def looks_like_json(headers, body: str) -> bool:
    ct = (headers.get("Content-Type") or "").lower() if headers else ""
    if "json" in ct:
        return True
    return "html" not in ct and body.lstrip()[:1] in ("{", "[")


# ---------- Static crawl ----------

def polite_sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def _write(output_dir, url, ext, content):
    filepath = unique_path(os.path.join(output_dir, slugify_from_url(url) + ext))
    with open(filepath, "w", encoding="utf-8") as out:
        out.write(content)
    return filepath


def crawl(seed_url: str, output_dir: str, max_pages: int, paginate: bool):
    """Static (plain HTTP) crawl of seed_url, following HTML and JSON pagination.
    Returns (pages_saved, error_or_None)."""
    seen_urls, seen_hashes = set(), set()
    url, page, saved = seed_url, 1, 0

    while url and page <= max_pages:
        seen_urls.add(url)
        try:
            body, headers, final_url = fetch_html(url)
        except Exception as e:
            if page == 1:
                return saved, str(e)
            print(f"  Page {page} failed ({e}); assuming end of pagination.")
            break
        seen_urls.add(final_url)

        data = None
        if looks_like_json(headers, body):
            try:
                data = json.loads(body)
            except ValueError:
                data = None

        if data is not None:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            ext = ".json"
        else:
            markdown_body = html_to_markdown(body, base_url=final_url)
            digest = hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()
            content = make_front_matter(final_url, extract_title(body), page) + markdown_body
            ext = ".md"

        if digest in seen_hashes:
            print(f"  Page {page} duplicates earlier content; stopping.")
            break
        seen_hashes.add(digest)

        print(f"  Saved page {page} -> {_write(output_dir, final_url, ext, content)}")
        saved += 1

        if not paginate:
            break
        if data is not None:
            next_url, method = find_next_json(data, headers, final_url)
        else:
            next_url, method = find_next_url(body, headers, final_url, seen_urls)
        if not next_url or next_url in seen_urls:
            print("  No next page found.")
            if data is None and LOADMORE_HINT_RE.search(body):
                print("  Hint: page looks JavaScript-driven (load more / infinite scroll). Try --js.")
            break
        print(f"  Next page via {method}: {next_url}")
        url, page = next_url, page + 1
        polite_sleep()
    else:
        if paginate and url:
            print(f"  Reached --max-pages ({max_pages}); stopping.")

    return saved, None


# ---------- JS mode (headless Chromium via Playwright) ----------

CLICKABLE = ("button, [role=button], input[type=button], input[type=submit], "
             "a:not([href]), a[href='#'], a[href^='javascript:']")
PAGER_ITEMS = (":is([class*=pagin i], [class*=pager i], [id*=pagin i], [id*=pager i], "
               "nav[aria-label*=pag i]) :is(a, button, li, span, [role=button])")
LOAD_MORE_RE = re.compile(
    r"^\W*(?:(?:load|show|view|see|get|fetch)\s+(?:more|older|next)\b.*|"
    r"more(?:\s+(?:results|posts|articles|items|stories|comments))?)\W*$", re.I)
NEXT_BTN_RE = re.compile(r"^\W*(next|older)\b.{0,20}$|^[\s>›»→⟩❯▶▸]+$", re.I)

INFOS_JS = """(sel) => Array.from(document.querySelectorAll(sel)).slice(0, 400).map((e, i) => {
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
  return {i, text: (e.innerText || e.value || '').trim().slice(0, 60),
    aria: e.getAttribute('aria-label') || '', title: e.getAttribute('title') || '',
    cls: String(e.className || '') + ' ' + (e.id || ''),
    active: e.getAttribute('aria-current') && e.getAttribute('aria-current') !== 'false',
    disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true',
    visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'};
})"""

SCROLL_JS = """() => {
  window.scrollTo(0, document.body.scrollHeight);
  for (const el of document.querySelectorAll('div,main,section,ul,ol')) {
    const s = getComputedStyle(el);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 50)
      el.scrollTop = el.scrollHeight;
  }
}"""

CURRENT_PAGER_JS = """() => {
  const sel = '[class*=pagin i],[class*=pager i],[id*=pagin i],[id*=pager i],nav[aria-label*=pag i]';
  for (const c of document.querySelectorAll(sel)) {
    const a = c.querySelector("[aria-current]:not([aria-current=false]), .active, .current, .selected, " +
      "[class*=active i], [class*=current i], [class*=selected i]");
    if (a) { const t = (a.innerText || '').trim(); if (/^\\d+$/.test(t)) return parseInt(t, 10); }
  }
  return null;
}"""


def _signature(page):
    """Hash of visible text + URL; changes when the DOM content changes."""
    for _ in range(2):
        try:
            text = page.evaluate("() => (document.body ? document.body.innerText : '') + '|' + location.href")
            return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
        except Exception:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
    return None


def _settle(page, ms=SETTLE_MS):
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def _clickable_infos(page, selector):
    for _ in range(2):
        try:
            return page.evaluate(INFOS_JS, selector)
        except Exception:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
    return []


def _label(info):
    return (info["text"] or info["aria"] or info["title"]).strip()


def _find_load_more(page):
    for info in _clickable_infos(page, CLICKABLE):
        if info["disabled"] or not info["visible"] or "disabled" in info["cls"].lower():
            continue
        if LOAD_MORE_RE.match(info["text"]) or LOAD_MORE_RE.match(info["aria"]):
            return page.locator(CLICKABLE).nth(info["i"])
    return None


def _find_js_next(page, current_num):
    """A clickable 'next page' control with no real href: numbered pager item
    for current+1 first, then a 'Next' / arrow button."""
    for info in _clickable_infos(page, PAGER_ITEMS):
        if info["visible"] and not info["disabled"] and info["text"] == str(current_num + 1):
            return page.locator(PAGER_ITEMS).nth(info["i"]), "JS numbered pager"
    for info in _clickable_infos(page, CLICKABLE):
        if info["disabled"] or not info["visible"] or "disabled" in info["cls"].lower():
            continue
        if NEGATIVE_RE.search(f'{_label(info)} {info["cls"]}'):
            continue
        if (NEXT_BTN_RE.match(info["text"]) or NEXT_BTN_RE.match(info["aria"])
                or NEXT_BTN_RE.match(info["title"]) or NEXT_CLASS_RE.search(info["cls"])):
            return page.locator(CLICKABLE).nth(info["i"]), "JS next button"
    return None, None


def _click_and_wait(page, locator, timeout_s=8.0):
    """Click, then wait until the page content changes. True if it did."""
    before = _signature(page)
    try:
        locator.scroll_into_view_if_needed(timeout=3000)
        locator.click(timeout=5000)
    except Exception as e:
        print(f"  Click failed: {str(e).splitlines()[0]}")
        return False
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _signature(page) != before:
            _settle(page, 300)
            return True
        page.wait_for_timeout(300)
    return False


def expand_page(page, max_steps):
    """Infinite scroll + 'Load more' buttons: keep going until the page stops growing."""
    prev, stagnant, steps = _signature(page), 0, 0
    for steps in range(1, max_steps + 1):
        btn = _find_load_more(page)
        if btn is not None:
            try:
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=5000)
            except Exception:
                page.evaluate(SCROLL_JS)
        else:
            try:
                page.evaluate(SCROLL_JS)
            except Exception:
                pass
        _settle(page)
        sig = _signature(page)
        stagnant = stagnant + 1 if sig == prev else 0
        prev = sig
        if stagnant >= 2:
            break
    if steps:
        print(f"  Expanded page ({steps} scroll/load-more step(s)).")
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
    except Exception:
        pass


def crawl_js(page, seed_url, output_dir, max_pages, paginate, max_scrolls, api_store):
    """Browser crawl: render, expand infinite scroll / load more, then follow
    href pagination or click next/numbered controls. Returns (pages_saved, error)."""
    try:
        resp = page.goto(seed_url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000 + 10000)
    except Exception as e:
        return 0, str(e)
    if resp is not None and resp.status >= 400:
        return 0, f"HTTP {resp.status}"
    if resp is not None and "json" in (resp.headers.get("content-type") or "").lower():
        print("  Response is JSON; using static API pagination.")
        return crawl(seed_url, output_dir, max_pages, paginate)
    _settle(page)

    seen_urls, seen_hashes = {seed_url}, set()
    n, saved = 1, 0
    while n <= max_pages:
        expand_page(page, max_scrolls)
        html, url = page.content(), page.url
        seen_urls.add(url)

        markdown_body = html_to_markdown(html, base_url=url)
        digest = hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            print(f"  Page {n} duplicates earlier content; stopping.")
            break
        seen_hashes.add(digest)
        content = make_front_matter(url, extract_title(html), n) + markdown_body
        print(f"  Saved page {n} -> {_write(output_dir, url, '.md', content)}")
        saved += 1
        if not paginate or n >= max_pages:
            break

        nxt, method = find_next_url(html, None, url, seen_urls, allow_increment=False)
        if nxt:
            print(f"  Next page via {method}: {nxt}")
            try:
                r = page.goto(nxt, wait_until="domcontentloaded", timeout=TIMEOUT * 1000 + 10000)
            except Exception as e:
                print(f"  Page {n + 1} failed ({e}); assuming end of pagination.")
                break
            if r is not None and r.status >= 400:
                print(f"  Page {n + 1} returned HTTP {r.status}; stopping.")
                break
            _settle(page)
        else:
            try:
                cur = page.evaluate(CURRENT_PAGER_JS) or n
            except Exception:
                cur = n
            ctrl, method = _find_js_next(page, cur)
            if ctrl is not None:
                print(f"  Next page via {method} (clicking)")
                if not _click_and_wait(page, ctrl):
                    print("  Click changed nothing; stopping.")
                    break
            else:
                bumped = increment_page_url(url)
                if not bumped or bumped in seen_urls:
                    print("  No next page found.")
                    break
                print(f"  Next page via page-number increment: {bumped}")
                try:
                    r = page.goto(bumped, wait_until="domcontentloaded", timeout=TIMEOUT * 1000 + 10000)
                except Exception as e:
                    print(f"  Page {n + 1} failed ({e}); assuming end of pagination.")
                    break
                if r is not None and r.status >= 400:
                    break
                _settle(page)
        n += 1
        polite_sleep()
    else:
        if paginate:
            print(f"  Reached --max-pages ({max_pages}); stopping.")
    return saved, None


class BrowserSession:
    """Headless Chromium via Playwright (imported lazily)."""

    def __init__(self, chromium_path=None, capture_api=False):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            sys.exit("Playwright is required for --js (it is in this script's dependencies; "
                     "run via `uv run scripts/web/fetch_urls.py ...`).")
        self._pw = sync_playwright().start()
        launch = {"headless": True}
        path = chromium_path or os.environ.get("CHROMIUM_PATH")
        if path:
            launch["executable_path"] = path
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            launch["args"] = ["--no-sandbox"]  # Chromium refuses to run sandboxed as root
        try:
            self.browser = self._pw.chromium.launch(**launch)
        except Exception as e:
            self._pw.stop()
            sys.exit(f"Could not start Chromium: {str(e).splitlines()[0]}\n"
                     "Install one with: uv run --with playwright python -m playwright install chromium\n"
                     "or pass --chromium-path / set CHROMIUM_PATH.")
        self.context = self.browser.new_context(user_agent=USER_AGENT)
        self.page = self.context.new_page()
        self.api_store = []
        if capture_api:
            self.page.on("response", self._on_response)

    def _on_response(self, resp):
        try:
            if (resp.request.resource_type in ("xhr", "fetch") and resp.status == 200
                    and "json" in (resp.headers.get("content-type") or "").lower()):
                self.api_store.append((resp.url, resp.text()))
        except Exception:
            pass

    def flush_api(self, seed_url, output_dir):
        seen, k = set(), 0
        for url, body in self.api_store:
            if url in seen or k >= 50 or len(body) < 2:
                continue
            seen.add(url)
            k += 1
            try:
                body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
            except ValueError:
                pass
            path = unique_path(os.path.join(output_dir, f"{slugify_from_url(seed_url)}.api-{k}.json"))
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
            print(f"  API endpoint captured: {url}\n    -> {path}")
        self.api_store.clear()

    def close(self):
        try:
            self.browser.close()
        finally:
            self._pw.stop()


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Fetch URLs to Markdown/JSON, following pagination.")
    ap.add_argument("urls_file", nargs="?", default="urls.txt")
    ap.add_argument("output_dir", nargs="?", default="output")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    help=f"max pages followed per starting URL (default {DEFAULT_MAX_PAGES})")
    ap.add_argument("--no-paginate", action="store_true", help="fetch only the listed URLs")
    ap.add_argument("--js", action="store_true",
                    help="render with headless Chromium: infinite scroll, load-more, JS pagers")
    ap.add_argument("--max-scrolls", type=int, default=DEFAULT_MAX_SCROLLS,
                    help=f"JS mode: max scroll/load-more steps per page (default {DEFAULT_MAX_SCROLLS})")
    ap.add_argument("--capture-api", action="store_true",
                    help="JS mode: save JSON (XHR/fetch) responses the page makes")
    ap.add_argument("--chromium-path", help="JS mode: Chromium executable (or set CHROMIUM_PATH)")
    args = ap.parse_args()

    if not os.path.exists(args.urls_file):
        print(f"Error: {args.urls_file} not found.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    total = len(urls)
    mode = "JS (headless Chromium)" if args.js else "static"
    print(f"Found {total} URL(s) in {args.urls_file}. Saving to '{args.output_dir}/'. Mode: {mode}.\n")

    session = BrowserSession(args.chromium_path, args.capture_api) if args.js else None
    failures, total_pages = [], 0
    max_pages = max(1, args.max_pages)

    try:
        for i, url in enumerate(urls, start=1):
            print(f"[{i}/{total}] Fetching: {url}")
            if session:
                saved, err = crawl_js(session.page, url, args.output_dir, max_pages,
                                      not args.no_paginate, max(1, args.max_scrolls), session.api_store)
                if args.capture_api:
                    session.flush_api(url, args.output_dir)
            else:
                saved, err = crawl(url, args.output_dir, max_pages, not args.no_paginate)
            total_pages += saved
            if err:
                print(f"  FAILED: {err}")
                failures.append((url, err))
            print()
            if i < total:
                polite_sleep()
    finally:
        if session:
            session.close()

    print(f"Done. {total - len(failures)}/{total} URLs succeeded, {total_pages} page(s) saved.")
    if failures:
        print("\nFailed URLs:")
        for url, err in failures:
            print(f"  - {url}: {err}")


if __name__ == "__main__":
    main()
