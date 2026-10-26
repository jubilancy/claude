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


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}\s+[—-]\s+", "", text.strip())  # seo_description date prefix
    text = re.sub(r"(\.\.\.|…)$", "", text.strip())  # seo_description truncation
    return re.sub(r"\s+", " ", text).strip()


def description(pin):
    """One copy of the description: drop variants that are contained in a longer one."""
    cands = {clean(pin.get(k)) for k in DESC_KEYS} - {""}
    keep = [c for c in cands if not any(c != o and c in o for o in cands)]
    return "\n\n".join(sorted(keep, key=len, reverse=True))


def tags(pin):
    va = (pin.get("pin_join") or {}).get("visual_annotation") or []
    return ", ".join(va)


def row(pin, url):
    user = pin.get("pinner") or {}
    board = pin.get("board") or {}
    pin_url = PIN + pin["seo_url"] if pin.get("seo_url") else f"{PIN}/pin/{pin['id']}/"
    lines = [description(pin), f"Pin URL: {pin_url}"]
    if user:
        lines.append(f"Creator: {user.get('full_name', '')} (@{user.get('username', '')})")
    if board:
        lines.append(f"Board: {board.get('name', '')} {PIN}{board.get('url', '')}")
    if tags(pin):
        lines.append(f"Tags: {tags(pin)}")
    lines.append(f"Created: {pin.get('created_at', '')}")
    lines.append(f"Dominant color: {pin.get('dominant_color', '')}")
    return {
        "value": url,
        "title": pin.get("title") or "",
        "description": "\n\n".join(l for l in lines if l),
        "original_source_url": pin.get("link") or "",
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
