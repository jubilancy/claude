# Pinterest → Are.na

Two scripts that turn a `gallery-dl` Pinterest dump into blocks in an Are.na channel. Both run with `uv`; neither needs installed packages.

```
uv tool run gallery-dl -j -i urls.txt --range 1-50 > pins.json
uv run arena/pins_to_csv.py pins.json pins.csv --channel your-channel-slug
ARENA_TOKEN=... uv run arena/arena_upload.py pins.csv --channel your-channel-slug
```

## `pins_to_csv.py`

Reads the JSON from `gallery-dl -j` (including several URLs back to back from `-i urls.txt`) and writes one CSV row per pin.

| Column | Source |
|---|---|
| `value` | original image URL (`i.pinimg.com/originals/...`) |
| `title` | longest of `title`, `grid_title`, `seo_title` (cut at ` \| `), `story_pin_data.metadata.pin_title` |
| `description` | see below |
| `original_source_url` | `link` (falls back to `tracked_link`), empty for pins uploaded straight to Pinterest |
| `original_source_title` | `domain`, only when there is a source link |
| `alt_text` | `alt_text`, else `auto_alt_text`, else `seo_alt_text` (often empty) |
| `channel_ids` | the `--channel` value, if given |

The description is, in order: the pin text, `pin [source](pin url)`, `link [domain](source url)` when there is one, `Tags:` (from `visual_annotation`, linked to Pinterest ideas pages when known) and `Dominant color:`. The pin text merges `description`, `closeup_unified_description`, `description_html`, `closeup_user_note`, `unified_user_note` and `seo_description` into one: HTML is stripped, dates like `20 Apr 2026 —` and Pinterest's "discover your own Pins" filler are removed, and any variant contained in a longer one is dropped.

Also: `original_pin` (the repeated copy of the starting pin) is ignored, and a pin that appears more than once is written once.

## `arena_upload.py`

Posts each CSV row to `POST /v3/blocks` ([Are.na docs](https://www.are.na/developers/explore/block/post-block)). It sends the columns as they are, so the description arrives exactly as in the CSV.

- Needs an Are.na token with **write** scope: paste it into `TOKEN` at the top of your local copy of the script, or set `ARENA_TOKEN`. Never commit a script with the token filled in.
- `--dry-run` prints what would be sent and uploads nothing.
- `--delay` sets seconds between posts (default 1).
- On a 429 it waits for the rate-limit reset and continues.
- Finished rows are recorded in `<csv>.uploaded`, so re-running skips them. Delete that file to upload everything again.
- Blocks are added one at a time, so their order in the channel will not match the CSV.

Only tested against a local fake server, not the live Are.na API (the 127-pin channel was filled with Are.na's tools, not this script). Try `--dry-run` and a throwaway channel first.

## Known gaps / to do

- Dates in other languages are not stripped from descriptions (e.g. `29 окт. 2025 г. —`). Only the English forms and a few day-month-year forms are handled.
- Pinterest's "discover your own Pins" filler text is only filtered for the languages seen so far (English, Dutch, Portuguese, French, Indonesian, Japanese). German ("Entdecke...") and others can slip through.
- Titles and descriptions come straight from Pinterest, so some are odd (doubled or cut-off titles, scraped site text, ad copy). Planned: browse the Are.na channels, fix weird titles and enrich blocks with `updateBlock` rather than re-uploading.
- `arena_upload.py` has only been tested against a fake local server.

## Flickr → Are.na

**One script: `arena/flickr.py`.** It has three steps and a `run` command that does all of them.

```
uv run arena/flickr.py run urls.txt --channel your-channel-slug --dry-run   # try it first
uv run arena/flickr.py run urls.txt --channel your-channel-slug
```

| Command | What it does |
|---|---|
| `fetch urls.txt [flickr_metadata.csv]` | Looks up every photo with gallery-dl (nothing is downloaded) and writes the metadata CSV: photo ID, title, description, creator, tags, image URL, Flickr page, license, attribution, albums, groups, galleries. Resumable. |
| `convert [flickr_metadata.csv] [flickr_arena.csv]` | Turns that CSV into the Are.na upload CSV. |
| `upload [flickr_arena.csv] --channel SLUG` | Uploads it by calling `arena_upload.py` (shared with the Pinterest scripts, so it is not copied). |
| `run urls.txt --channel SLUG` | `fetch`, then `convert`, then `upload`. `--dry-run` stops before anything is sent to Are.na. |

`urls.txt` takes whatever gallery-dl's Flickr extractor takes: photos, albums, galleries, group pools, favorites, user photostreams, search results. Lines starting with `#` are ignored.

**What ends up in Are.na**
- `value` is the image URL; the block's source is the Flickr page (`flickr_url`), not the image file; the source title is `Flickr · <creator>`.
- The description merges, in order: the Flickr description (HTML turned into plain text, links kept as markdown), the attribution line, `Tags:`, `License:`, `Albums:`, `Groups:`, `Galleries:` (markdown links), and `photo [source](…)`.
- A photo listed more than once (once per URL it was found under) is written once; rows without an image URL are skipped.

**Resuming.** Ctrl+C is safe at every step. `fetch` skips photos already in the metadata CSV (so no API calls are spent on them), and `upload` skips rows already uploaded (`<csv>.uploaded`). Run the same command again.

**Settings.** By default the script asks gallery-dl for each photo's license and the albums and groups it is in. Other gallery-dl settings go in a `gallery-dl.conf` next to the script, or in the current folder; it overrides these defaults. The Are.na token is read by `arena_upload.py` (`ARENA_TOKEN`, or `TOKEN` at the top of that file).

**Attribution.** A photo with no license gets `"Title" by Name (link)` and no license text, rather than a guess. "All Rights Reserved" gets `© Name, all rights reserved (link)`.

Tested with simulated gallery-dl results, not against live Flickr or Are.na. Your `classify_flickr_urls.py` (URL sorting, a run log, raw dumps) is separate and not part of this script.

## Wikimedia Commons → Are.na

`wiki_to_csv.py` turns Commons category and file pages into the same upload CSV, using the MediaWiki API's image metadata (the data behind a file page's "Summary" and "Licensing").

```
uv run arena/wiki_to_csv.py https://commons.wikimedia.org/wiki/Category:Flowers_in_graphic_ornaments flowers.csv --channel your-channel-slug
uv run arena/wiki_to_csv.py -i urls.txt flowers.csv --subcats 1
ARENA_TOKEN=... uv run arena/arena_upload.py flowers.csv --channel your-channel-slug --dry-run
```

- **Addresses:** `Category:` pages (every file in them; `--subcats N` also goes N levels down) and `File:` pages. Other page types are skipped with a message.
- **Columns:** same as `pins_to_csv.py`. `value` is the original image; `original_source_url` is the file's Commons page; the source title is `Wikimedia Commons`.
- **Description:** the file's own description (HTML turned into text, links kept as markdown, cut at `--max-desc` characters, default 2000, since some are whole pages of OCR text), then a credit line `"Title" by Author, License` with the license linked, then Date, Source (credit), Restrictions, the category it was found in, and a link to the file page. `--categories` adds the file's own categories.
- **Which file:** JPEG, PNG, GIF and WebP use the original. SVG, TIFF and similar use a resized copy (`--width`, default 1920, one of Commons' standard sizes). `--max-mb N` does the same for originals bigger than N MB. Audio, video and PDF are skipped and counted.
- **Politeness:** requests go one at a time, with gzip and `maxlag`; on a 429 it waits as long as the server asks. Wikimedia asks for a User-Agent with contact information, so set yours with `--user-agent` or `WIKI_USER_AGENT`.
- Tested against the live Commons API: a 37-file category (also paged 10 at a time), an SVG (resized copy), an audio file (skipped) and a missing file. Not uploaded to Are.na. Only Commons has been tried; other MediaWiki sites use the same API path but are untested.
