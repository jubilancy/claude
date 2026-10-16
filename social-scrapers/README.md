# Scraping notes: gallery-dl, TikTok comments, Twitter replies, Flickr URLs

Notes and scripts from one working session. Everything here is for local use with `uv`
(`uv run`, never `python3` or `pip`). **None of the scripts were tested against the live
sites** (the session ran in a cloud container with no login and a datacenter IP), except where
a section says otherwise. Treat them as starting points.

## Files

| File | What it is |
|---|---|
| `twitter_replies.py` | Reads `urls.txt` (tweet URLs), saves each tweet plus its conversation to `replies_<tweet id>.json` using gallery-dl as a library |
| `translate_replies.py` | Optional second step: adds English `text_translated` to those JSON files (free, via deep-translator) |
| `tiktok_comments.py` | Reads `urls.txt` (TikTok video URLs), saves comments and replies to `comments_<video id>.json` using TikTok-Api. **Token removed; paste your own** |
| `flickr_sorted.md` | 416 Flickr URLs sorted by page type (no duplicates found) |

## Run with `--no-project`

Always run the scripts as `uv run --no-project script.py`. Without the flag, `uv run` searches the
current folder and every parent folder for a `pyproject.toml`, and builds that project first.
In one case a parent folder (`.../dev/uv`) held a broken project named `uv`, so every command
failed before it started (`Failed to build uv ... Expected a Python module at ...`).
The scripts declare their own dependencies in a header comment, so they need no project.
You can drop the flag if the folder has no `pyproject.toml` above it.

---

## gallery-dl

Docs: [configuration.rst](https://github.com/mikf/gallery-dl/blob/master/docs/configuration.rst),
[supported sites](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md).
Checked against the master branch during the session.

### Comments
There is no general "download comments" feature. These extractors have a `comments` option
(default `false`). It adds `comments` to the metadata, so combine it with `--write-metadata`:

| Site | Option | Notes |
|---|---|---|
| DeviantArt | `extractor.deviantart.comments` | `comments-avatars` also adds avatars |
| Fanbox | `extractor.fanbox.comments` | 1+ extra API requests per post |
| Kemono | `extractor.kemono.comments` | 1 extra request per post |
| Pixiv | `extractor.pixiv.comments` | 1+ extra requests per post |
| Pixiv Novel | `extractor.pixiv-novel.comments` | same, per novel |
| Reddit | `extractor.reddit.comments` | integer API `limit`; `0` ignores comments; `morecomments` resolves "more" stubs |
| Plurk | `extractor.plurk.comments` | only searches comments for media URLs, does not save the text |

On the command line: `gallery-dl -o comments=true URL`. CHZZK is the only site that lists
"Comments" as a capability. Bluesky and the Nitter sites list "Replies" instead.

### Twitter / X bookmarks
Supported. URL: `https://x.com/i/bookmarks`. Needs a logged-in `cookies.txt`.
Each tweet gets a `date_bookmarked` field.
```
uv run --no-project --with gallery-dl gallery-dl --cookies cookies.txt https://x.com/i/bookmarks
```

### Twitter / X replies
Supported through `extractor.twitter.conversations` (default `false`). For a single-tweet URL it
fetches the tweets and replies in that conversation. Replies without media need
`extractor.twitter.text-tweets` plus a metadata post processor with `"event": "post"`.
The reply text is in the `content` field; `reply_id` and `reply_to` give the threading.
`twitter_replies.py` does all of this through gallery-dl's Python API.

gallery-dl has **no translation feature**. The tweet's original language is in the `lang` field.

---

## Twitter replies script

1. Put tweet URLs in `urls.txt`, one per line (`#` lines and blanks are ignored; `&amp;` is fixed).
2. Put a Netscape-format `cookies.txt` (exported from a browser logged in to x.com) next to the
   script, or set `COOKIES_FROM_BROWSER` (for example `["safari"]`) at the top of the script.
   Without login, gallery-dl stops with `AuthRequired` (seen in the session).
3. `uv run --no-project twitter_replies.py`

Output `replies_<id>.json`:
```json
{"url": "...", "tweet_id": "...", "count": 372,
 "replies": [ {"text", "lang", "author", "nick", "date", "tweet_id",
               "reply_to_tweet_id", "reply_to_user", "likes", "retweets", "replies", "url"} ],
 "tweets":  [ ...full gallery-dl metadata, including "content"... ]}
```

### Known limit: replies can be missing
A real run saved 372 tweets for a tweet showing 508 replies. Reading
[twitter.py](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/twitter.py):
- Replies to replies **are** included (whole conversation threads are kept).
- gallery-dl only follows the `cursor-bottom-` link. It never follows `cursor-showmore-`
  ("Show more replies" inside a long thread), so long threads can be cut short.
- Hidden or filtered replies ("Show additional replies") are probably not fetched either, and
  Twitter's displayed count may include deleted, blocked or muted replies. These two are
  inferences, not verified.

To see the split of direct replies versus replies to replies:
```
uv run --no-project python -c "
import json
d = json.load(open('replies_<id>.json'))
ts = d['tweets']; root = d['tweet_id']
direct = [t for t in ts if str(t.get('reply_id')) == root]
print('total', len(ts), '| direct', len(direct), '| replies to replies', len(ts) - len(direct) - 1)
"
```
An untested idea for completeness: change the script to follow the "show more" links.

## Translating replies (optional, run rarely)

`uv run --no-project translate_replies.py` (all `replies_*.json` in the folder, or name files).
Adds `text_translated` (English) to every entry in `replies`, in place. English and empty
replies are copied. Uses [deep-translator](https://pypi.org/project/deep-translator/) 1.11.4
(Google Translate, free, no key; last release June 2023, so it may break).
- 0.5 s pause between requests; the library's error text says Google allows 5 requests/second
  and 200,000/day. On `TooManyRequests` it waits 5 s, doubling up to 6 tries.
- Results are cached in `translations_cache.json`; failures are written as `null`.
- Time for 372 replies: estimated 5 to 10 minutes if all need translating (not measured).
- Copy the JSON first if you want to keep an untranslated version.
- Paid alternative: Claude API with Haiku 5.5 at $0.10 / $0.50 per million input / output tokens
  ([pricing](https://platform.claude.com/docs/en/about-claude/pricing)); roughly two cents for
  500 short replies (own estimate).

---

## TikTok comments

Findings:
- **yt-dlp**: does not download TikTok comments (only `comment_count`). The
  [feature request](https://github.com/yt-dlp/yt-dlp/issues/5037) was closed in 2022.
- **gallery-dl**: no TikTok comment support.
- **Official Research API**: [video comments endpoint](https://developers.tiktok.com/doc/research-api-specs-query-video-comments),
  max 100 per request, includes replies. Only for [qualifying researchers](https://developers.tiktok.com/products/research-api/)
  (academic institutions in the US, EEA, UK, Canada, Switzerland, plus some non-profit research bodies; must be independent of commercial interests).
- **Paid scrapers** such as [Apify's TikTok comments scraper](https://apify.com/deepmine/tiktok-comments-scraper/api/python) are the most reliable fallback.
- **[TikTok-Api](https://github.com/davidteather/TikTok-Api)** (unofficial, Playwright-based, v7.3.3): the free option, used by `tiktok_comments.py`.
  Selenium is not needed; this library already automates a browser.

### `tiktok_comments.py`
1. Put video URLs in `urls.txt`.
2. Paste your `msToken` cookie value (tiktok.com, DevTools, Application, Cookies) into `MS_TOKEN`
   at the top, or set the `ms_token` environment variable. **Never commit a real token**; it is a
   session cookie. If it is ever shared, log out and back in to replace it.
3. One-time browser install: `uv run --no-project --with TikTokApi==7.3.3 playwright install chromium webkit firefox`
4. `uv run --no-project tiktok_comments.py` (optional arguments: urls file, max comments)

Output `comments_<video id>.json`: url, video id, comments (text, likes, created, username,
nickname, reply count, replies, raw data). By default it fetches everything TikTok returns
(`count` is only a cap you set; paging stops when TikTok says `has_more` is false).

Replies: the library's `comment.replies()` sends the comment author's user ID as `item_id`,
which looks wrong. The script sends the video ID instead. Unverified; if replies come back empty
for comments that have replies, change `item_id`.

### Known problem: bot detection
The one real run failed with `EmptyResponseException` ("They are detecting you're a bot").
The script was then changed to open a visible browser by default and to read env switches.
Try these in order (separate alternatives, run one at a time):
```
uv run --no-project tiktok_comments.py
TIKTOK_BROWSER=webkit uv run --no-project tiktok_comments.py
TIKTOK_BROWSER=firefox uv run --no-project tiktok_comments.py
ms_token= uv run --no-project tiktok_comments.py        # browser makes its own token
PROXY=http://user:pass@host:port uv run --no-project tiktok_comments.py
```
`HEADLESS=1` hides the window. Avoid VPNs. If everything fails, use a paid scraper.
It was not confirmed whether the changed script gets past the block; this is the open item.
Also not checked: TikTok's terms of service on scraping.

---

## Flickr URL sorting
`flickr_sorted.md` holds 416 URLs from `safari_flickr2scrape_more.txt`, grouped by page type, with
the original order kept inside each group. No duplicates were found. Groups: 209 photos in the
`sephisunset` gallery, 113 in gallery `195489122@N08-72157722166924671`, 57 in favorites
`59022515@N08`, 17 in favorites `26518458@N05`, 20 albums of `apenguinaweek`.
An earlier list of 85 pasted URLs was sorted in chat only (51 single photos, 14 sephisunset
gallery photos, 8 favorites photos, 11 photostreams, 1 tag page); it is not saved here.
All 22 gallery and favorites photos from that first list (14 + 8) also appear in `flickr_sorted.md`, so the two lists overlap. A few URLs use `flickr.com` without `www.`; they were left as given.
