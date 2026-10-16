# /// script
# requires-python = ">=3.9"
# dependencies = ["TikTokApi==7.3.3"]
# ///
"""Save the comments and replies of TikTok videos to JSON.

Reads urls.txt (one video URL per line; blank lines and lines starting with
# are ignored) and writes comments_<video id>.json for each video.

First time only:  uv run --no-project --with TikTokApi==7.3.3 playwright install chromium webkit firefox
Run:              uv run --no-project tiktok_comments.py [urls.txt] [max_comments_per_video]

If TikTok returns empty responses ("detecting you're a bot"), try, in order:
  TIKTOK_BROWSER=webkit uv run --no-project tiktok_comments.py
  TIKTOK_BROWSER=firefox uv run --no-project tiktok_comments.py
  PROXY=http://user:pass@host:port uv run --no-project tiktok_comments.py
  ms_token= uv run --no-project tiktok_comments.py   (let the browser get its own token)
Set HEADLESS=1 to hide the browser window (it is visible by default).
"""
import asyncio
import json
import os
import re
import sys

from TikTokApi import TikTokApi

# Your tiktok.com "msToken" cookie. The ms_token environment variable overrides it.
MS_TOKEN = "PASTE_YOUR_MSTOKEN_COOKIE_HERE"

URLS_FILE = "urls.txt"
MAX_COMMENTS = 1_000_000  # effectively "all"; stops when TikTok says there are no more
INCLUDE_REPLIES = True
PAUSE = 1.0  # seconds between requests, to look less like a bot

COMMENT_URL = "https://www.tiktok.com/api/comment/list/"
REPLY_URL = "https://www.tiktok.com/api/comment/list/reply/"


def simplify(raw: dict) -> dict:
    user = raw.get("user") or {}
    return {
        "id": raw.get("cid"),
        "text": raw.get("text"),
        "likes": raw.get("digg_count"),
        "created": raw.get("create_time"),
        "username": user.get("unique_id"),
        "nickname": user.get("nickname"),
        "reply_count": raw.get("reply_comment_total"),
        "replies": [],
        "raw": raw,
    }


async def fetch_pages(api, url, params, limit):
    """Yield raw comment dicts from a paginated TikTok comment endpoint."""
    cursor, found = 0, 0
    while found < limit:
        resp = await api.make_request(url=url, params={**params, "count": 20, "cursor": cursor})
        if resp is None:
            raise RuntimeError("TikTok returned an invalid response")
        for raw in resp.get("comments") or []:
            yield raw
            found += 1
        if not resp.get("has_more"):
            return
        cursor = resp.get("cursor")
        await asyncio.sleep(PAUSE)


async def fetch_replies(api, video_id, comment):
    params = {"item_id": video_id, "comment_id": comment["id"]}
    return [simplify(r) async for r in fetch_pages(api, REPLY_URL, params, MAX_COMMENTS)]


async def scrape_video(api, url, limit):
    m = re.search(r"/video/(\d+)", url)
    video_id = m.group(1) if m else api.video(url=url).id  # short links need a redirect lookup
    comments = []
    async for raw in fetch_pages(api, COMMENT_URL, {"aweme_id": video_id}, limit):
        comments.append(simplify(raw))
        print(f"  {len(comments)} comments", end="\r")
    print()

    if INCLUDE_REPLIES:
        n = 0
        for c in comments:
            if c["reply_count"] == 0:  # skip when TikTok says there are none
                continue
            c["replies"] = await fetch_replies(api, video_id, c)
            n += len(c["replies"])
            await asyncio.sleep(PAUSE)
        print(f"  {n} replies")

    out = f"comments_{video_id}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {"url": url, "video_id": video_id, "comments": comments},
            f, ensure_ascii=False, indent=2,
        )
    print(f"  saved {out}")


async def main(urls_file, limit):
    with open(urls_file, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    if not urls:
        sys.exit(f"No URLs found in {urls_file}")

    async with TikTokApi() as api:
        token = os.environ["ms_token"] if "ms_token" in os.environ else MS_TOKEN
        proxy = os.environ.get("PROXY")
        await api.create_sessions(
            ms_tokens=[token] if token else None,
            num_sessions=1,
            sleep_after=5,
            headless=os.getenv("HEADLESS", "0") == "1",
            browser=os.getenv("TIKTOK_BROWSER", "chromium"),
            proxies=[{"server": proxy}] if proxy else None,
        )
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}")
            try:
                await scrape_video(api, url, limit)
            except Exception as e:  # keep going if one video fails
                print(f"  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main(
        sys.argv[1] if len(sys.argv) > 1 else URLS_FILE,
        int(sys.argv[2]) if len(sys.argv) > 2 else MAX_COMMENTS,
    ))
