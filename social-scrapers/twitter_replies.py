# /// script
# requires-python = ">=3.9"
# dependencies = ["gallery-dl==1.32.16"]
# ///
"""Save a tweet and all replies in its conversation to JSON, one file per URL.

Reads urls.txt (one tweet URL per line; blank lines and lines starting with #
are ignored) and writes replies_<tweet id>.json for each.
Each file has "replies" (readable: text, lang, author, date, likes) and
"tweets" (full metadata). To translate the replies to English, run
translate_replies.py afterwards.

Login: put a cookies.txt (Netscape format, exported from a browser logged in to
x.com) next to this script, or set COOKIES_FROM_BROWSER below.

Run:  uv run --no-project twitter_replies.py [urls.txt]
"""
import json
import os
import re
import sys

from gallery_dl import config, job

URLS_FILE = "urls.txt"
COOKIES_FILE = "cookies.txt"
COOKIES_FROM_BROWSER = None  # e.g. ["chrome"], ["firefox"], ["safari"]; used if no cookies.txt

TW = ("extractor", "twitter")


def setup():
    config.set(TW, "conversations", True)  # include replies in the conversation
    config.set(TW, "text-tweets", True)    # include replies that have no media
    if os.path.exists(COOKIES_FILE):
        config.set(TW, "cookies", COOKIES_FILE)
    elif COOKIES_FROM_BROWSER:
        config.set(TW, "cookies", COOKIES_FROM_BROWSER)
    else:
        print(f"Warning: no {COOKIES_FILE} found; replies usually need a logged-in session.")


def flatten(t):
    """Short, readable version of one tweet: the text comes first."""
    a = t.get("author") or {}
    return {
        "text": t.get("content"),
        "lang": t.get("lang"),
        "author": a.get("name"),
        "nick": a.get("nick"),
        "date": t.get("date"),
        "tweet_id": t.get("tweet_id"),
        "reply_to_tweet_id": t.get("reply_id"),
        "reply_to_user": t.get("reply_to"),
        "likes": t.get("favorite_count"),
        "retweets": t.get("retweet_count"),
        "replies": t.get("reply_count"),
        "url": f"https://x.com/{a.get('name')}/status/{t.get('tweet_id')}",
    }


def scrape(url):
    j = job.DataJob(url, file=None)
    j.run()
    errors = [m[-1] for m in j.data if m and m[0] == -1]
    if errors:
        raise RuntimeError(f"{errors[0].get('error')}: {errors[0].get('message')}")
    seen, tweets = set(), []
    for t in j.data_post:  # one entry per tweet, including text-only replies
        tid = t.get("tweet_id")
        if tid in seen:
            continue
        seen.add(tid)
        tweets.append(t)
    return tweets


def main(urls_file):
    with open(urls_file, encoding="utf-8") as f:
        urls = [l.strip().replace("&amp;", "&") for l in f
                if l.strip() and not l.lstrip().startswith("#")]
    if not urls:
        sys.exit(f"No URLs found in {urls_file}")
    setup()
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        m = re.search(r"/status/(\d+)", url)
        if not m:
            print("  FAILED: not a tweet URL (expected .../status/<id>)")
            continue
        try:
            tweets = scrape(url)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        flat = [flatten(t) for t in tweets]
        no_text = sum(1 for r in flat if not r["text"])
        out = f"replies_{m.group(1)}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"url": url, "tweet_id": m.group(1), "count": len(tweets),
                       "replies": flat,    # readable: text, author, date, likes...
                       "tweets": tweets},  # full gallery-dl metadata
                      f, ensure_ascii=False, indent=2, default=str)
        print(f"  saved {len(tweets)} tweets to {out} ({no_text} without text)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else URLS_FILE)
