#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "pyyaml"]
# ///
"""
tumblr_to_jekyll.py - import a whole Tumblr blog (posts, reblogs, asks) into
Jekyll posts, uploading every image to Cloudinary.

What it does:
- Pages through the Tumblr API (npf=true) for every published post on a blog.
- Saves each post's full API response to <out>/raw/<id>.json (the source of
  truth: re-render the Jekyll files later without calling the API again).
- Writes one Jekyll post per Tumblr post to <out>/_posts/YYYY-MM-DD-<id>.md with
  front matter: id, date, tags, type (photo/text/reblog/ask), images,
  reblog_trail, ask, source_url, permalink (/post/<id>/).
- Uploads every image to Cloudinary as <folder>/<post-id>_<n>, where n is the
  image's order in the post (own content first, then the reblog trail).
  Cloudinary fetches the image from Tumblr by URL, so nothing is downloaded here.
  Uploads use overwrite=false, so re-running never duplicates or replaces.
- Resumable: <out>/state.json records finished posts. Finished posts are skipped
  before any network request for them. A post finished in --dry-run mode is
  redone by the next real run, because its image URLs are placeholders.
- Retries on 429/5xx with backoff. One failing post never stops the run.
- Writes results-log-{timestamp}.txt in the current folder on every run (even
  if everything fails) and prints its path at the end.

Setup (secrets go in environment variables, never in the repo):
    TUMBLR_API_KEY   Tumblr OAuth consumer key (read-only is enough)
    CLOUDINARY_URL   cloudinary://<api_key>:<api_secret>@<cloud_name>
                     (not needed with --dry-run; --cloud-name is then optional)

Usage:
    uv run scripts/tumblr/tumblr_to_jekyll.py --dry-run --max-posts 50
    uv run scripts/tumblr/tumblr_to_jekyll.py
    uv run scripts/tumblr/tumblr_to_jekyll.py --blog fromdaysoff.tumblr.com --out site-import
    uv run scripts/tumblr/tumblr_to_jekyll.py --force     # redo posts already finished

Known limits: text formatting offsets are applied by Python character index
(posts with emoji before a link may be off by a few characters); video and audio
blocks become links, not uploads; asks sent to the blog are only included when
they appear as published posts.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

API = "https://api.tumblr.com/v2/blog/{blog}/posts"
USER_AGENT = "tumblr-to-jekyll/1.0 (personal blog archive)"
API_DELAY = 0.4
MAX_RETRIES = 5
RETRY_BASE = 4.0


class SkipPost(Exception):
    """A post that is left out on purpose (not an error)."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def request_with_retry(method, url, **kw):
    delay = RETRY_BASE
    for attempt in range(MAX_RETRIES + 1):
        resp = requests.request(method, url, timeout=60, headers={"User-Agent": USER_AGENT}, **kw)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
            wait = delay
            ra = resp.headers.get("Retry-After")
            if ra and ra.isdigit():
                wait = max(wait, float(ra))
            time.sleep(min(wait, 120))
            delay *= 2
            continue
        return resp
    return resp


def fetch_page(blog, key, offset, limit):
    resp = request_with_retry(
        "GET", API.format(blog=blog),
        params={"api_key": key, "npf": "true", "limit": limit, "offset": offset},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["response"]


# --------------------------------------------------------------------------
# NPF -> markdown
# --------------------------------------------------------------------------

def apply_formatting(text, formatting):
    """Insert markdown markers for NPF inline formatting."""
    if not formatting:
        return text
    marks = []  # (index, order, string)
    for f in formatting:
        s, e, t = f.get("start", 0), f.get("end", 0), f.get("type")
        if t == "bold":
            o, c = "**", "**"
        elif t == "italic":
            o, c = "*", "*"
        elif t == "strikethrough":
            o, c = "~~", "~~"
        elif t == "link" and f.get("url"):
            o, c = "[", f"]({f['url']})"
        elif t == "mention" and f.get("blog", {}).get("url"):
            o, c = "[", f"]({f['blog']['url']})"
        else:
            continue
        marks.append((s, 1, o))
        marks.append((e, 0, c))
    out, last = [], 0
    for idx, _, m in sorted(marks, key=lambda x: (x[0], x[1])):
        out.append(text[last:idx])
        out.append(m)
        last = idx
    out.append(text[last:])
    return "".join(out)


class Collector:
    """Turns NPF blocks into markdown, collecting images with placeholders."""

    def __init__(self):
        self.images = []  # dicts: url, width, height, alt, type
        self.warnings = []

    def image_placeholder(self, block):
        media = block.get("media") or []
        if not media:
            return ""
        best = max(media, key=lambda m: m.get("width", 0) or 0)
        self.images.append({
            "src": best["url"], "width": best.get("width"), "height": best.get("height"),
            "alt": block.get("alt_text") or "", "mime": best.get("type", ""),
        })
        return f"{{{{IMG:{len(self.images) - 1}}}}}"

    def blocks_to_md(self, blocks):
        lines, prev_list = [], False
        for b in blocks:
            t = b.get("type")
            if t == "text":
                sub = b.get("subtype")
                body = apply_formatting(b.get("text", ""), b.get("formatting"))
                indent = "  " * int(b.get("indent_level", 0) or 0)
                is_list = sub in ("ordered-list-item", "unordered-list-item")
                if sub == "heading1":
                    body = f"## {body}"
                elif sub == "heading2":
                    body = f"### {body}"
                elif sub in ("quote", "indented"):
                    body = "> " + body.replace("\n", "\n> ")
                elif sub == "ordered-list-item":
                    body = f"{indent}1. {body}"
                elif sub == "unordered-list-item":
                    body = f"{indent}- {body}"
                if lines and not (is_list and prev_list):
                    lines.append("")
                lines.append(body)
                prev_list = is_list
            elif t == "image":
                ph = self.image_placeholder(b)
                if ph:
                    if lines:
                        lines.append("")
                    lines.append(ph)
                prev_list = False
            elif t == "link":
                title = b.get("title") or b.get("display_url") or b.get("url", "")
                desc = b.get("description")
                if lines:
                    lines.append("")
                lines.append(f"[{title}]({b.get('url', '')})" + (f"  \n{desc}" if desc else ""))
                prev_list = False
            elif t in ("video", "audio"):
                url = b.get("url") or (b.get("media") or {}).get("url", "")
                label = b.get("title") or t
                if lines:
                    lines.append("")
                lines.append(f"[{label}]({url})" if url else f"<!-- {t} block with no url -->")
                prev_list = False
            elif t == "paywall":
                self.warnings.append("paywall block skipped")
            else:
                self.warnings.append(f"unknown block type: {t}")
        return "\n".join(lines).strip()


def quote(md):
    return "\n".join(("> " + ln) if ln.strip() else ">" for ln in md.splitlines())


# --------------------------------------------------------------------------
# Cloudinary
# --------------------------------------------------------------------------

def parse_cloudinary_url(url):
    p = urlparse(url)
    if p.scheme != "cloudinary" or not (p.username and p.password and p.hostname):
        raise ValueError("CLOUDINARY_URL must look like cloudinary://key:secret@cloud_name")
    return p.username, p.password, p.hostname


def upload_image(src, public_id, creds):
    key, secret, cloud = creds
    ts = str(int(time.time()))
    params = {
        "asset_folder": public_id.rsplit("/", 1)[0],
        "overwrite": "false",
        "public_id": public_id,
        "timestamp": ts,
    }
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sig = hashlib.sha1((to_sign + secret).encode()).hexdigest()
    data = {**params, "api_key": key, "signature": sig, "file": src}
    resp = request_with_retry("POST", f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", data=data)
    if resp.status_code != 200:
        raise RuntimeError(f"Cloudinary {resp.status_code}: {resp.text[:200]}")
    return resp.json()


# --------------------------------------------------------------------------
# Post conversion
# --------------------------------------------------------------------------

def ask_block_indexes(post):
    idx = set()
    for lay in post.get("layout") or []:
        if lay.get("type") == "ask":
            idx.update(lay.get("blocks", []))
    return idx


def convert_post(post):
    """Return (front_matter dict, body md with {{IMG:n}} placeholders, collector)."""
    col = Collector()
    content = post.get("content") or []
    ask_idx = ask_block_indexes(post)
    ask_md, own_blocks = "", []
    if ask_idx:
        ask_md = col.blocks_to_md([b for i, b in enumerate(content) if i in ask_idx])
        own_blocks = [b for i, b in enumerate(content) if i not in ask_idx]
    else:
        own_blocks = content
    own_md = col.blocks_to_md(own_blocks)
    own_image_count = len(col.images)

    trail_meta, trail_md = [], []
    for item in post.get("trail") or []:
        blog = (item.get("blog") or {}).get("name") or (item.get("broken_blog_name") or "unknown")
        pid = (item.get("post") or {}).get("id", "")
        md = col.blocks_to_md(item.get("content") or [])
        trail_meta.append({
            "blog": blog, "post_id": str(pid),
            "url": f"https://{blog}.tumblr.com/post/{pid}" if pid else "",
        })
        trail_md.append(f"**{blog}:**\n\n{quote(md)}" if md else f"**{blog}:**")

    asker = ""
    for lay in post.get("layout") or []:
        if lay.get("type") == "ask":
            attr = lay.get("attribution") or {}
            asker = (attr.get("blog") or {}).get("name") or "anonymous"

    ptype = "ask" if ask_idx else "reblog" if trail_meta else "photo" if own_image_count else "text"

    parts = []
    if ask_md:
        parts.append(f"**{asker} asked:**\n\n{quote(ask_md)}")
    if own_md:
        parts.append(own_md)
    parts.extend(trail_md)
    body = "\n\n".join(parts).strip()

    ts = int(post.get("timestamp", 0))
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    pid = post["id_string"]
    fm = {
        "layout": "post",
        "id": pid,
        "title": "",
        "date": dt.strftime("%Y-%m-%d %H:%M:%S +0000"),
        "tags": post.get("tags") or [],
        "type": ptype,
        "source_url": post.get("post_url", ""),
        "permalink": f"/post/{pid}/",
        "note_count": post.get("note_count", 0),
        "reblog_trail": trail_meta,
    }
    if asker:
        fm["ask_from"] = asker
    return fm, body, col, dt


def process_post(post, out, cloud_creds, cloud_name, folder, dry_run):
    pid = post["id_string"]
    fm, body, col, dt = convert_post(post)
    images_out, warns = [], list(col.warnings)

    for n, im in enumerate(col.images, start=1):
        public_id = f"{folder}/{pid}_{n}"
        ext = re.sub(r"[^a-z0-9]", "", (im["mime"].split("/")[-1] or "jpg").lower()) or "jpg"
        if ext == "jpeg":
            ext = "jpg"
        if dry_run:
            url = f"https://res.cloudinary.com/{cloud_name or 'YOUR_CLOUD'}/image/upload/{public_id}.{ext}"
        else:
            res = upload_image(im["src"], public_id, cloud_creds)
            url = res["secure_url"]
            im["width"], im["height"] = res.get("width"), res.get("height")
        images_out.append({
            "public_id": public_id, "url": url, "width": im["width"], "height": im["height"],
            "alt": im["alt"], "tumblr_src": im["src"],
        })
        body = body.replace(f"{{{{IMG:{n - 1}}}}}", f"![{im['alt']}]({url})")

    fm["images"] = images_out
    fm["summary"] = (post.get("summary") or "")[:200]
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "_posts").mkdir(parents=True, exist_ok=True)
    (out / "raw" / f"{pid}.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False, width=120)
    md_path = out / "_posts" / f"{dt.strftime('%Y-%m-%d')}-{pid}.md"
    md_path.write_text(f"---\n{front}---\n\n{body}\n", encoding="utf-8")
    return md_path, len(images_out), warns


# --------------------------------------------------------------------------
# Results log
# --------------------------------------------------------------------------

def fmt_items(items):
    if not items:
        return "  (none)\n"
    return "".join(f"  {a}\n      {b}\n" for a, b in items)


def write_log(path, started, finished, args, out, total, buckets):
    done = len(buckets["written"])
    already = len(buckets["already"])
    skipped = len(buckets["skipped"])
    errors = len(buckets["errors"])
    dur = finished - started
    lines = [
        "tumblr_to_jekyll results log",
        "=" * 60,
        f"Run started : {started.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Run finished: {finished.strftime('%Y-%m-%d %H:%M:%S')}  (duration {str(dur).split('.')[0]})",
        f"Input       : https://api.tumblr.com/v2/blog/{args.blog}/posts"
        + (" (dry run)" if args.dry_run else ""),
        f"Output      : {out}",
        "",
        "SUMMARY",
        "-" * 60,
        f"  Total posts            : {total}",
        f"  Done this run          : {done}",
        f"  Already done (skipped) : {already}",
        f"  Skipped on purpose     : {skipped}",
        f"  Errors                 : {errors}",
        "",
        f"SUCCESSFUL: WRITTEN ({done})",
        fmt_items(buckets["written"]).rstrip("\n"),
        "",
        f"SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT ({already})",
        fmt_items(buckets["already"]).rstrip("\n"),
        "",
        f"SKIPPED ON PURPOSE: {buckets['skip_reason']} ({skipped})",
        fmt_items(buckets["skipped"]).rstrip("\n"),
        "",
        f"ERRORS ({errors})",
        fmt_items(buckets["errors"]).rstrip("\n"),
        "",
        f"WARNINGS ({len(buckets['warnings'])})",
        fmt_items(buckets["warnings"]).rstrip("\n"),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Import a Tumblr blog into Jekyll posts + Cloudinary images.")
    ap.add_argument("--blog", default="fromdaysoff.tumblr.com")
    ap.add_argument("--out", default="site-import", help="output folder (default ./site-import)")
    ap.add_argument("--folder", default="tumblr/fromdaysoff", help="Cloudinary folder")
    ap.add_argument("--cloud-name", default="", help="only used for placeholder URLs in --dry-run")
    ap.add_argument("--dry-run", action="store_true", help="write posts with placeholder image URLs; upload nothing")
    ap.add_argument("--max-posts", type=int, default=0, help="stop after N posts (0 = all)")
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--force", action="store_true", help="redo posts already finished")
    args = ap.parse_args()

    started = datetime.now()
    out = Path(args.out).resolve()
    log_path = Path(f"results-log-{started.strftime('%Y-%m-%d_%H%M%S')}.txt")
    buckets = {"written": [], "already": [], "skipped": [], "errors": [], "warnings": [],
               "skip_reason": "IMAGE UPLOAD, DRY RUN (no images uploaded)" if args.dry_run else "(nothing skipped on purpose)"}
    total = 0

    try:
        key = os.environ.get("TUMBLR_API_KEY", "")
        if not key:
            raise SystemExit("Set TUMBLR_API_KEY (Tumblr OAuth consumer key).")
        creds = None
        if not args.dry_run:
            cu = os.environ.get("CLOUDINARY_URL", "")
            if not cu:
                raise SystemExit("Set CLOUDINARY_URL=cloudinary://key:secret@cloud_name, or use --dry-run.")
            creds = parse_cloudinary_url(cu)
        cloud_name = creds[2] if creds else args.cloud_name

        out.mkdir(parents=True, exist_ok=True)
        state_path = out / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}

        offset, seen = 0, 0
        while True:
            try:
                page = fetch_page(args.blog, key, offset, args.page_size)
            except Exception as e:  # noqa: BLE001 - keep going, log it
                buckets["errors"].append((f"API page offset={offset}", f"{type(e).__name__}: {e}"))
                break
            posts = page.get("posts", [])
            if not posts:
                break
            total_posts = page.get("total_posts", 0)
            for post in posts:
                if args.max_posts and seen >= args.max_posts:
                    break
                seen += 1
                total += 1
                pid = post.get("id_string", "?")
                label = f"post {pid} ({post.get('post_url', '')})"
                prior = state.get(pid)
                if prior and not args.force and (prior["uploaded"] or args.dry_run):
                    buckets["already"].append((label, f"already finished ({prior['file']})"))
                    continue
                try:
                    md_path, n_img, warns = process_post(post, out, creds, cloud_name, args.folder, args.dry_run)
                    state[pid] = {"file": md_path.name, "uploaded": not args.dry_run, "images": n_img}
                    state_path.write_text(json.dumps(state, indent=2))
                    detail = f"{md_path.name}, {n_img} image(s)"
                    buckets["written"].append((label, detail))
                    if args.dry_run and n_img:
                        buckets["skipped"].append((label, f"{n_img} image(s) not uploaded (dry run)"))
                    for w in warns:
                        buckets["warnings"].append((label, w))
                except Exception as e:  # noqa: BLE001 - one bad post never stops the run
                    buckets["errors"].append((label, f"{type(e).__name__}: {e}"))
            if args.max_posts and seen >= args.max_posts:
                break
            offset += len(posts)
            if offset >= total_posts:
                break
            time.sleep(API_DELAY)
    except SystemExit as e:
        buckets["errors"].append(("startup", str(e)))
    except Exception as e:  # noqa: BLE001
        buckets["errors"].append(("unexpected", f"{type(e).__name__}: {e}"))
    finally:
        write_log(log_path, started, datetime.now(), args, out, total, buckets)
        print(f"Results log: {log_path.resolve()}")
        print(f"Output     : {out}")
        print(f"Done {len(buckets['written'])}, already {len(buckets['already'])}, "
              f"errors {len(buckets['errors'])}")
    sys.exit(1 if buckets["errors"] else 0)


if __name__ == "__main__":
    main()
