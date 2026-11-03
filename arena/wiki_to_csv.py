# /// script
# requires-python = ">=3.10"
# ///
"""Turn Wikimedia Commons categories and files into an Are.na-ready CSV.

uv run arena/wiki_to_csv.py https://commons.wikimedia.org/wiki/Category:Flowers_in_graphic_ornaments flowers.csv
uv run arena/wiki_to_csv.py -i urls.txt flowers.csv --channel your-channel-slug --subcats 1
ARENA_TOKEN=... uv run arena/arena_upload.py flowers.csv --channel your-channel-slug --dry-run

Takes Category: pages (every file in them, optionally their subcategories too) and File: pages.
The metadata comes from the MediaWiki API (`extmetadata`, the same data Commons shows under
"Licensing" and "Summary"): description, author, credit, date, license and its link, categories.

Columns match pins_to_csv.py, so arena_upload.py takes the result unchanged. The block's source is
the file's Commons page, not the image file.

Requests follow https://www.mediawiki.org/wiki/API:Etiquette: one at a time, gzip, `maxlag`, a
User-Agent with contact information, and a wait when the server answers 429. Put your own contact
in the User-Agent with --user-agent or the WIKI_USER_AGENT environment variable.
"""
import argparse
import csv
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_UA = "arena-wiki-csv/0.1 (+https://github.com/jubilancy/claude)"
WEB_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}  # the original file is used as is
COLUMNS = ["value", "title", "description", "original_source_url", "original_source_title", "alt_text"]
PAGE_SIZE = 50  # the most a request may ask for with image information


# ───────────────────────── Talking to the API ─────────────────────────


class Api:
    def __init__(self, base, user_agent, delay=1.0):
        self.base, self.ua, self.delay, self.last = base, user_agent, delay, 0.0

    def get(self, **params):
        params = {"action": "query", "format": "json", "formatversion": "2", "maxlag": "5", **params}
        url = self.base + "?" + urllib.parse.urlencode(params)
        for attempt in range(8):
            wait = self.last + self.delay - time.time()  # in series, with a pause between requests
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "gzip"})
            retry = None
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    body = json.loads(raw)
                    self.last = time.time()
                    if body.get("error", {}).get("code") == "maxlag":
                        retry = int(r.headers.get("Retry-After") or 5)
                    elif "error" in body:
                        raise RuntimeError(f"{body['error'].get('code')}: {body['error'].get('info')}")
                    else:
                        return body
            except urllib.error.HTTPError as e:
                self.last = time.time()
                if e.code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"HTTP {e.code} for {url[:120]}") from None
                retry = int(e.headers.get("Retry-After") or 0) or 2 ** attempt
            except (urllib.error.URLError, TimeoutError) as e:
                retry = 2 ** attempt
                print(f"  network problem ({e}), retrying", file=sys.stderr)
            retry = max(retry, 1) + attempt  # wait a little longer each time
            print(f"  server asked to slow down, waiting {retry}s", file=sys.stderr)
            time.sleep(retry)
        raise RuntimeError("gave up after repeated rate limiting; try again later or raise --delay")

    def pages(self, **params):
        """Every page of a query, following `continue`."""
        cont = {}
        while True:
            body = self.get(**params, **cont)
            for w in body.get("warnings", {}).values():
                print(f"  API warning: {w}", file=sys.stderr)
            yield from body.get("query", {}).get("pages", [])
            # Older versions of a file come back as extra pages (iistart / iicontinue). Only the
            # current version is wanted, so follow nothing but the list of files itself.
            cont = {k: v for k, v in body.get("continue", {}).items() if k not in ("iistart", "iicontinue")}
            if not any(k != "continue" for k in cont):
                return


def parse_url(url):
    """(api endpoint, host, page title) from a wiki page address."""
    u = urllib.parse.urlsplit(url.strip())
    if not u.netloc:
        raise ValueError(f"not a web address: {url}")
    if u.path.startswith("/wiki/"):
        title = urllib.parse.unquote(u.path[len("/wiki/"):])
    else:
        title = (urllib.parse.parse_qs(u.query).get("title") or [""])[0]
    title = title.replace("_", " ").strip()
    if not title:
        raise ValueError(f"no page title in {url}")
    return f"https://{u.netloc}/w/api.php", u.netloc, title


# ───────────────────────── Reading the metadata ─────────────────────────

def md_url(url):
    """Parentheses in an address would end a markdown link early."""
    return url.replace("(", "%28").replace(")", "%29")


ANCHOR = re.compile(r'<a\s[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def plain(text, host="commons.wikimedia.org"):
    """Wiki metadata is HTML: keep links as markdown, drop the rest."""
    def absolute(href):
        href = html.unescape(href)
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return f"https://{host}{href}"
        return href
    absolute_md = lambda href: md_url(absolute(href))

    text = ANCHOR.sub(lambda m: f"[{re.sub(r'<[^>]+>', '', m[2]).strip() or m[1]}]({absolute_md(m[1])})", text or "")
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r" *\n *", "\n", text)).strip()


def meta(info, key, host):
    return plain((info.get("extmetadata", {}).get(key) or {}).get("value", ""), host)


def clean_url(url):
    """The API appends tracking parameters to upload.wikimedia.org addresses; the file does not need them."""
    p = urllib.parse.urlsplit(url or "")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", "")) if p.netloc.endswith("wikimedia.org") else (url or "")


def pick_file(info, max_mb):
    """The address to upload, or None when there is no usable image."""
    mime = info.get("mime", "")
    if not mime.startswith("image/"):
        return None  # audio, video, PDF...
    too_big = max_mb and info.get("size", 0) > max_mb * 1024 * 1024
    if mime in WEB_MIMES and not too_big:
        return clean_url(info.get("url"))
    return clean_url(info.get("thumburl")) or None  # SVG, TIFF... or a very large original: a resized copy


def shorten(text, limit):
    if not limit or len(text) <= limit:
        return text
    return text[:limit].rsplit(None, 1)[0].rstrip(".,;:([ ") + " …"


def row(page, host, site_name, from_category=None, categories=False, max_mb=0, max_desc=2000):
    info = (page.get("imageinfo") or [{}])[0]
    value = pick_file(info, max_mb)
    if not value:
        return None
    file_page = info.get("descriptionurl") or f"https://{host}/wiki/{urllib.parse.quote(page['title'].replace(' ', '_'))}"
    name = re.sub(r"\.[A-Za-z0-9]+$", "", page["title"].split(":", 1)[-1])
    title = meta(info, "ObjectName", host) or name
    description = meta(info, "ImageDescription", host)
    shown = shorten(description, max_desc)  # some are whole pages of OCR text

    artist = meta(info, "Artist", host)
    license_name = meta(info, "LicenseShortName", host) or meta(info, "UsageTerms", host)
    license_url = meta(info, "LicenseUrl", host)
    license_text = (f"[{license_name}]({md_url(license_url)})" if license_url else license_name) if license_name else ""
    credit_line = f'"[{title}]({md_url(file_page)})"' + (f" by {artist}" if artist else "") + (f", {license_text}" if license_text else "")

    lines = [shown, credit_line]
    required = meta(info, "Attribution", host)
    if required:
        lines.append(f"Required attribution: {required}")
    if meta(info, "DateTimeOriginal", host):
        lines.append(f"Date: {meta(info, 'DateTimeOriginal', host)}")
    if meta(info, "Credit", host):
        lines.append(f"Source: {meta(info, 'Credit', host)}")
    if meta(info, "Restrictions", host):
        lines.append(f"Restrictions: {meta(info, 'Restrictions', host)}")
    if from_category:
        lines.append(f"Category: [{from_category}]({md_url(f'https://{host}/wiki/' + urllib.parse.quote('Category:' + from_category.replace(' ', '_'), safe=':'))})")
    if categories and meta(info, "Categories", host):
        lines.append("Categories: " + ", ".join(c.strip() for c in meta(info, "Categories", host).split("|") if c.strip()))
    lines.append(f"file [source]({md_url(file_page)})")
    return {
        "value": value,
        "title": title,
        "description": "\n\n".join(l for l in lines if l),
        "original_source_url": file_page,
        "original_source_title": site_name,
        "alt_text": shorten(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", (description or title)).replace("\n", " "), 300),
    }


# ───────────────────────── Collecting files ─────────────────────────

IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|size|mime|timestamp|user|extmetadata"}


def category_files(api, category, width, seen_pages):
    """Files directly in one category."""
    for p in api.pages(generator="categorymembers", gcmtitle=f"Category:{category}", gcmtype="file", gcmlimit=PAGE_SIZE,
                       iiurlwidth=width, **IMAGEINFO):
        if p.get("pageid") in seen_pages or "imageinfo" not in p:
            continue
        seen_pages.add(p.get("pageid"))
        yield p


def subcategories(api, category):
    return [p["title"].split(":", 1)[1] for p in api.pages(generator="categorymembers", gcmtitle=f"Category:{category}",
                                                          gcmtype="subcat", gcmlimit=500, prop="info")]


def collect(api, host, title, width, subcats, limit):
    """Yield (page, category name or None) for a Category: or File: address."""
    ns, _, name = title.partition(":")
    seen = set()
    if ns.lower() == "category":
        queue, visited, count = [(name, 0)], {name}, 0
        while queue:
            cat, depth = queue.pop(0)
            print(f"  Category:{cat}", file=sys.stderr)
            for p in category_files(api, cat, width, seen):
                yield p, cat
                count += 1
                if limit and count >= limit:
                    return
            if depth < subcats:
                for sub in subcategories(api, cat):
                    if sub not in visited:
                        visited.add(sub)
                        queue.append((sub, depth + 1))
    elif ns.lower() in ("file", "image"):
        for p in api.pages(titles=title, iiurlwidth=width, **IMAGEINFO):
            if p.get("pageid") in seen:
                continue
            seen.add(p.get("pageid"))
            if "imageinfo" in p:
                yield p, None
            else:
                print(f"  not found: {title}", file=sys.stderr)
    else:
        raise ValueError(f"only Category: and File: pages are supported, got “{title}”")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="Category: or File: addresses (then the output CSV last)")
    ap.add_argument("-i", "--input", help="a text file with one address per line")
    ap.add_argument("--channel", help="channel slug/id, adds a channel_ids column")
    ap.add_argument("--subcats", type=int, default=0, help="also read subcategories this many levels down (default 0)")
    ap.add_argument("--categories", action="store_true", help="add the file's own categories to the description")
    ap.add_argument("--width", type=int, default=1920, help="pixel width of the resized copy used for SVG, TIFF and oversized files (default 1920, one of Commons' standard sizes)")
    ap.add_argument("--max-mb", type=float, default=0, help="use the resized copy for originals bigger than this many MB (default: never)")
    ap.add_argument("--max-desc", type=int, default=2000, help="cut the file's own description at this many characters (default 2000, 0 = never)")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many files per address (default: all)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1)")
    ap.add_argument("--user-agent", default=os.environ.get("WIKI_USER_AGENT", DEFAULT_UA), help="User-Agent with contact information")
    a = ap.parse_args()

    args = list(a.urls)
    if not args:
        ap.error("give the output CSV (and addresses, or -i urls.txt)")
    out = args.pop()
    urls = args
    if a.input:
        with open(a.input, encoding="utf-8-sig") as f:
            urls += [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    if not urls:
        ap.error("no addresses given")

    rows, seen_values, skipped = [], set(), 0
    for n, url in enumerate(urls, 1):
        print(f"[{n}/{len(urls)}] {url}", file=sys.stderr)
        try:
            endpoint, host, title = parse_url(url)
            site_name = "Wikimedia Commons" if host == "commons.wikimedia.org" else host
            api = Api(endpoint, a.user_agent, a.delay)
            for page, cat in collect(api, host, title, a.width, a.subcats, a.limit):
                r = row(page, host, site_name, cat, a.categories, a.max_mb, a.max_desc)
                if not r:
                    skipped += 1
                elif r["value"] not in seen_values:
                    seen_values.add(r["value"])
                    rows.append(r)
        except (ValueError, RuntimeError) as e:
            print(f"  skipped: {e}", file=sys.stderr)

    cols = list(COLUMNS)
    if a.channel:
        cols.append("channel_ids")
        for r in rows:
            r["channel_ids"] = a.channel
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files -> {out}" + (f" ({skipped} skipped: not an image, or no resized copy)" if skipped else ""))


if __name__ == "__main__":
    main()
