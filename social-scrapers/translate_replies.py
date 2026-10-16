# /// script
# requires-python = ">=3.9"
# dependencies = ["deep-translator==1.11.4"]
# ///
"""Add English translations to the replies_*.json files made by twitter_replies.py.

Run:  uv run --no-project translate_replies.py [file.json ...]
With no arguments it processes every replies_*.json in the current folder.

For each entry in "replies" it adds "text_translated". Replies already in English
(lang == "en") and empty ones are copied as is. Translation uses the free Google
Translate wrapper deep-translator. Results are cached in translations_cache.json,
so re-running or resuming after a crash does not redo finished translations.
"""
import glob
import json
import sys
import time

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TooManyRequests

TARGET_LANG = "en"
CACHE_FILE = "translations_cache.json"
PAUSE = 0.5  # seconds between requests (the library says Google allows 5 per second)


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def translate_one(translator, text):
    """Translate text, retrying with a growing pause if Google says slow down."""
    chunks = [text[i:i + 4500] for i in range(0, len(text), 4500)]  # 5000-char limit
    out = []
    for chunk in chunks:
        for attempt in range(6):
            try:
                out.append(translator.translate(chunk) or chunk)
                break
            except TooManyRequests:
                wait = 5 * 2 ** attempt
                print(f"    rate limited, waiting {wait}s")
                time.sleep(wait)
        else:
            raise TooManyRequests()
        time.sleep(PAUSE)
    return " ".join(out)


def process(path, translator, cache):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # older files have no "lang" in "replies"; fall back to the full metadata
    langs = {str(t.get("tweet_id")): t.get("lang") for t in data.get("tweets", [])}
    done = failed = 0
    for r in data.get("replies", []):
        text = r.get("text")
        lang = r.get("lang") or langs.get(str(r.get("tweet_id")))
        if not text or lang == TARGET_LANG:
            r["text_translated"] = text
            continue
        if text not in cache:
            try:
                cache[text] = translate_one(translator, text)
                done += 1
                if done % 20 == 0:
                    save_cache(cache)
            except Exception as e:
                failed += 1
                print(f"    failed for {r.get('tweet_id')}: {type(e).__name__}")
                r["text_translated"] = None
                continue
        r["text_translated"] = cache[text]
    save_cache(cache)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  translated {done} new replies, {failed} failed")


def main(paths):
    paths = paths or sorted(glob.glob("replies_*.json"))
    if not paths:
        sys.exit("No replies_*.json files found in this folder.")
    translator = GoogleTranslator(source="auto", target=TARGET_LANG)
    cache = load_cache()
    for i, path in enumerate(paths, 1):
        print(f"[{i}/{len(paths)}] {path}")
        try:
            process(path, translator, cache)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
