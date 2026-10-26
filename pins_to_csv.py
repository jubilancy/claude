# /// script
# requires-python = ">=3.10"
# ///
"""Flatten gallery-dl Pinterest JSON (-j output) into an Are.na-ready CSV.

uv run pins_to_csv.py pin_pinn_newww_oct19.json pins.csv [--channel my-channel-slug]
"""
import argparse
import csv
import html
import json
import re

PIN = "https://www.pinterest.com"
DESC_KEYS = (
    "description",
    "closeup_unified_description",
    "description_html",
    "closeup_user_note",
    "unified_user_note",
    "seo_description",
)


DATE_RE = re.compile(
    r"\b\d{1,2} [A-Z][a-z]{2,8} \d{4}\s*[—-]?\s*"  # 20 Apr 2026 —
    r"|\b[A-Z][a-z]{2,8} \d{1,2}, \d{4}\s*[—-]?\s*"  # Oct 1, 2026 —
)
TITLE_KEYS = ("title", "grid_title", "seo_title")


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = DATE_RE.sub(" ", text)
    text = re.sub(r"(\.\.\.|…)\s*$", "", re.sub(r"\s+", " ", text).strip())  # truncation marker
    return text.strip()


def variants(pin, keys, split_seo=False):
    out = set()
    for k in keys:
        v = pin.get(k) or ""
        if split_seo and k == "seo_title":
            v = v.split(" | ")[0]  # seo_title appends ' | tag, tag'
        out.add(clean(v))
    return out - {""}


def description(pin):
    """Collapse the description variants; drop any contained in a longer one."""
    cands = variants(pin, DESC_KEYS)
    keep = [c for c in cands if not any(c != o and c in o for o in cands)]
    return "\n\n".join(sorted(keep, key=len, reverse=True))


def title(pin):
    cands = variants(pin, TITLE_KEYS, split_seo=True)
    pt = (((pin.get("story_pin_data") or {}).get("metadata") or {}).get("pin_title"))
    if pt:
        cands.add(clean(pt))
    return max(cands, key=len) if cands else ""


def tags(pin):
    """visual_annotation names, hyperlinked to their Pinterest ideas page when known."""
    pj = pin.get("pin_join") or {}
    links = {t.get("name"): t.get("url") for t in (pj.get("annotations_with_links") or {}).values() if isinstance(t, dict)}
    names = list(pj.get("visual_annotation") or [])
    names += [n for n in links if n not in names]
    return ", ".join(f"[{n}]({PIN}{links[n]})" if links.get(n) else n for n in names)


def row(pin, url):
    pin_url = PIN + pin["seo_url"] if pin.get("seo_url") else f"{PIN}/pin/{pin['id']}/"
    link = pin.get("link") or pin.get("tracked_link") or ""
    lines = [description(pin), f"pin [source]({pin_url})"]
    if link:
        lines.append(f"link [{pin.get('domain') or 'source'}]({link})")
    if tags(pin):
        lines.append(f"Tags: {tags(pin)}")
    if pin.get("dominant_color"):
        lines.append(f"Dominant color: {pin['dominant_color']}")
    return {
        "value": url,
        "title": title(pin),
        "description": "\n\n".join(l for l in lines if l),
        "original_source_url": link,
        "original_source_title": pin.get("domain") or "",
        "alt_text": pin.get("auto_alt_text") or pin.get("seo_alt_text") or "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--channel", help="channel slug/id, adds a channel_ids column")
    a = ap.parse_args()

    with open(a.src, encoding="utf-8") as f:
        data = json.load(f)

    rows, seen = [], set()
    for e in data:
        # gallery-dl -j: [2, {dir meta}] and [3, "file url", {file meta}]
        if not (isinstance(e, list) and e and e[0] == 3 and len(e) >= 3):
            continue
        url, pin = e[1], e[2]
        pin.pop("original_pin", None)  # full copy of the start pin, repeated on every related pin
        if pin.get("id") in seen:
            continue
        seen.add(pin.get("id"))
        if "pinimg.com" not in url:
            url = ((pin.get("images") or {}).get("orig") or {}).get("url", url)
        rows.append(row(pin, url))

    cols = ["value", "title", "description", "original_source_url", "original_source_title", "alt_text"]
    if a.channel:
        cols.append("channel_ids")
        for r in rows:
            r["channel_ids"] = a.channel
    with open(a.dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} pins -> {a.dst}")


if __name__ == "__main__":
    main()
