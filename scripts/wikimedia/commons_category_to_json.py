#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
commons_category_to_json.py - Wikimedia Commons category (and its sub-categories) -> one nested JSON file + results log.

What it does:
- Takes a Commons category URL (or "Category:Name") and fetches the category itself, every
  file in it (title, page url, direct url, size, mime, dates, uploader, description, author,
  license, credit, hidden/visible categories) and, recursively, every sub-category with
  its own files. Output is nested: category -> files + subcategories[].
- A category reached twice (loops, or shared sub-categories) is only expanded once; later
  appearances are kept as a stub marked "already_listed".
- Retries on 429/503 (and the Wikimedia "too many requests" page), honoring Retry-After.
- Writes <Category_name>-<timestamp>.json (never overwrites) in --output (default: current folder).
- Writes results-log-{timestamp}.txt in the current folder every run: SUMMARY plus lists for
  written, skipped on purpose, errors and warnings. The log is written even if the run fails.

Usage:
    uv run scripts/wikimedia/commons_category_to_json.py "https://commons.wikimedia.org/wiki/Category:Endpieces_(book_illustration)"
    uv run scripts/wikimedia/commons_category_to_json.py "Category:Endpieces (book illustration)" --output out/
    uv run scripts/wikimedia/commons_category_to_json.py URL --depth 0      # this category only, no sub-categories
    uv run scripts/wikimedia/commons_category_to_json.py URL --no-meta      # titles/urls only, skip descriptions/licences
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse as up
import urllib.request as ur
from datetime import datetime
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "commons-category-to-json/1.0 (personal bookmark tooling)"
REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 6
RETRY_BASE_SECONDS = 5.0
RETRY_MAX_WAIT_SECONDS = 120.0


def api_get(params: dict) -> dict:
    """GET the MediaWiki API with retry on 429/503 and on non-JSON rate-limit pages."""
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    url = API + "?" + up.urlencode(params)
    delay = RETRY_BASE_SECONDS
    for attempt in range(MAX_RETRIES + 1):
        wait = None
        try:
            req = ur.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
            with ur.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = None  # rate-limit text page
            if data is not None:
                err = data.get("error")
                if not err:
                    time.sleep(REQUEST_DELAY_SECONDS)
                    return data
                if err.get("code") != "maxlag":
                    raise RuntimeError(f"API error {err.get('code')}: {err.get('info')}")
            wait = delay
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
            ra = e.headers.get("Retry-After", "")
            wait = float(ra) if ra.isdigit() else delay
        if attempt == MAX_RETRIES:
            raise RuntimeError("gave up after repeated rate limiting")
        wait = min(wait, RETRY_MAX_WAIT_SECONDS)
        print(f"  rate limited, waiting {wait:.0f}s (retry {attempt + 1}/{MAX_RETRIES})")
        time.sleep(wait)
        delay *= 2


def parse_category(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http"):
        u = up.urlparse(raw)
        if u.hostname not in ("commons.wikimedia.org", "commons.m.wikimedia.org"):
            raise ValueError("not a commons.wikimedia.org URL")
        if u.path.startswith("/wiki/"):
            title = up.unquote(u.path[len("/wiki/"):])
        else:
            title = up.parse_qs(u.query).get("title", [""])[0]
    else:
        title = raw
    title = title.replace("_", " ").strip()
    if not title.lower().startswith("category:"):
        raise ValueError("not a Category: page")
    return "Category:" + title.split(":", 1)[1].strip()


def page_url(title: str) -> str:
    return "https://commons.wikimedia.org/wiki/" + up.quote(title.replace(" ", "_"), safe="/:()")


def clean(s):
    if s is None:
        return None
    s = re.sub(r"<[^>]+>", "", str(s))
    return html.unescape(s).strip()


def ext(meta: dict, key: str):
    v = (meta or {}).get(key)
    return clean(v.get("value")) if isinstance(v, dict) else None


def file_record(page: dict, with_meta: bool) -> dict:
    ii = (page.get("imageinfo") or [{}])[0]
    rec = {
        "title": page["title"],
        "page_url": page_url(page["title"]),
        "url": ii.get("url"),
        "description_url": ii.get("descriptionurl"),
        "mime": ii.get("mime"),
        "width": ii.get("width"),
        "height": ii.get("height"),
        "bytes": ii.get("size"),
        "uploaded": ii.get("timestamp"),
        "uploader": ii.get("user"),
    }
    if with_meta:
        m = ii.get("extmetadata") or {}
        rec.update({
            "description": ext(m, "ImageDescription"),
            "author": ext(m, "Artist"),
            "credit": ext(m, "Credit"),
            "date": ext(m, "DateTimeOriginal"),
            "license": ext(m, "LicenseShortName"),
            "license_url": ext(m, "LicenseUrl"),
            "attribution": ext(m, "Attribution"),
            "categories": [c for c in (ext(m, "Categories") or "").split("|") if c],
        })
    return rec


def fetch_files(cat: str, with_meta: bool) -> list:
    """All files directly in a category, merged across continuation batches."""
    pages = {}
    cont = {}
    while True:
        params = {"action": "query", "generator": "categorymembers", "gcmtitle": cat,
                  "gcmtype": "file", "gcmlimit": "50", "prop": "imageinfo",
                  "iiprop": "url|size|mime|timestamp|user" + ("|extmetadata" if with_meta else ""),
                  **cont}
        data = api_get(params)
        for p in data.get("query", {}).get("pages", []):
            cur = pages.setdefault(p["pageid"], p)
            if cur is not p and p.get("imageinfo"):
                cur["imageinfo"] = p["imageinfo"]
        if "continue" not in data:
            break
        cont = data["continue"]
    return [file_record(p, with_meta) for p in sorted(pages.values(), key=lambda x: x["title"])]


def fetch_subcats(cat: str) -> list:
    out, cont = [], {}
    while True:
        data = api_get({"action": "query", "list": "categorymembers", "cmtitle": cat,
                        "cmtype": "subcat", "cmlimit": "500", **cont})
        out += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data:
            return sorted(out)
        cont = data["continue"]


def fetch_info(cat: str) -> dict:
    data = api_get({"action": "query", "titles": cat, "prop": "categoryinfo|info|categories|revisions",
                    "inprop": "url", "cllimit": "500", "rvprop": "content", "rvslots": "main"})
    p = data["query"]["pages"][0]
    if p.get("missing"):
        raise RuntimeError(f"{cat} does not exist")
    ci = p.get("categoryinfo", {})
    content = ((p.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content"))
    return {
        "title": p["title"], "page_url": page_url(p["title"]), "pageid": p["pageid"],
        "counts": {"files": ci.get("files", 0), "subcats": ci.get("subcats", 0), "pages": ci.get("pages", 0)},
        "parent_categories": [c["title"] for c in p.get("categories", [])],
        "wikitext": content,
    }


def build(cat: str, depth: int, with_meta: bool, seen: set, ctx: dict, level: int = 0) -> dict:
    print(f"{'  ' * level}{cat}")
    if cat in seen:
        ctx["skipped"].append((cat, "already listed elsewhere in this tree (stub kept)"))
        return {"title": cat, "page_url": page_url(cat), "already_listed": True}
    seen.add(cat)
    node = {}
    try:
        node = fetch_info(cat)
        node["files"] = fetch_files(cat, with_meta)
        ctx["files"] += len(node["files"])
        exp = node["counts"]["files"]
        if exp != len(node["files"]):
            ctx["warnings"].append((cat, f"category says {exp} files, got {len(node['files'])}"))
        ctx["written"].append((cat, f"{len(node['files'])} files"))
    except Exception as e:  # noqa: BLE001 - one category failing must not stop the run
        ctx["errors"].append((cat, f"{type(e).__name__}: {e}"))
        node.setdefault("title", cat)
        node.setdefault("page_url", page_url(cat))
        node.setdefault("files", [])
        node["error"] = str(e)
    node["subcategories"] = []
    if level < depth:
        try:
            for sub in fetch_subcats(cat):
                node["subcategories"].append(build(sub, depth, with_meta, seen, ctx, level + 1))
        except Exception as e:  # noqa: BLE001
            ctx["errors"].append((cat, f"sub-categories: {type(e).__name__}: {e}"))
    elif node.get("counts", {}).get("subcats"):
        ctx["skipped"].append((cat, f"{node['counts']['subcats']} sub-categories not expanded (--depth)"))
    return node


def write_log(path: Path, meta: dict, ctx: dict) -> None:
    started, finished = meta["started"], datetime.now()
    L = [
        "commons_category_to_json results log",
        f"Run started : {started:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {finished:%Y-%m-%d %H:%M:%S}  (duration {str(finished - started).split('.')[0]})",
        f"Input       : {meta['input']}",
        f"Output file : {meta['output']}",
        "",
        "SUMMARY",
        f"  Categories in tree                 : {len(ctx['written']) + len(ctx['errors'])}",
        f"  Done this run (categories written) : {len(ctx['written'])}",
        f"  Files collected                    : {ctx['files']}",
        f"  Already done (skipped)             : 0",
        f"  Skipped on purpose                 : {len(ctx['skipped'])}",
        f"  Errors                             : {len(ctx['errors'])}",
        f"  Warnings                           : {len(ctx['warnings'])}",
    ]
    for head, items in [("SUCCESSFUL: WRITTEN", ctx["written"]),
                        ("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", []),
                        ("SKIPPED ON PURPOSE", ctx["skipped"]),
                        ("ERRORS", ctx["errors"]), ("WARNINGS", ctx["warnings"])]:
        L += ["", f"{head} ({len(items)})"]
        L += [f"  {a}\n    {b}" for a, b in items] or ["  (none)"]
    L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Commons category -> nested JSON")
    ap.add_argument("category", help="Commons category URL or 'Category:Name'")
    ap.add_argument("--output", default=".", help="folder for the JSON (default: current folder)")
    ap.add_argument("--depth", type=int, default=99, help="sub-category levels to expand (0 = none; default all)")
    ap.add_argument("--no-meta", action="store_true", help="skip description/author/licence/categories")
    a = ap.parse_args()

    started = datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M%S")
    log_path = Path(f"results-log-{stamp}.txt")
    ctx = {"written": [], "skipped": [], "errors": [], "warnings": [], "files": 0}
    meta = {"started": started, "input": a.category, "output": "(not written)"}
    try:
        cat = parse_category(a.category)
        tree = build(cat, a.depth, not a.no_meta, set(), ctx)
        out_dir = Path(a.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w\-]+", "_", cat.split(":", 1)[1]).strip("_")
        out = out_dir / f"{name}-{stamp}.json"
        doc = {"source": "https://commons.wikimedia.org", "retrieved": started.isoformat(timespec="seconds"),
               "total_files": ctx["files"], "category": tree}
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        meta["output"] = str(out)
        print(f"\nJSON: {out}  ({ctx['files']} files)")
    except Exception as e:  # noqa: BLE001
        ctx["errors"].append((a.category, f"{type(e).__name__}: {e}"))
        print(f"FAILED: {e}", file=sys.stderr)
    finally:
        write_log(log_path, meta, ctx)
        print(f"Log: {log_path}")
    return 1 if ctx["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
