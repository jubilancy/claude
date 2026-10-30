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

`flickr_to_csv.py` does for Flickr what `pins_to_csv.py` does for Pinterest. It reads the dump from `gallery-dl -j` (the `flickr_*.json` file that `classify_flickr_urls.py` writes, or `gallery-dl -j -i urls.txt > flickr.json`) and writes the same CSV columns, so `arena_upload.py` takes it unchanged.

```
uv run arena/flickr_to_csv.py flickr_2026-10-11_09-30-00.json photos.csv --channel your-channel-slug
ARENA_TOKEN=... uv run arena/arena_upload.py photos.csv --channel your-channel-slug --dry-run
```

| Column | Source |
|---|---|
| `value` | the photo's sized image URL (`url` in the gallery-dl metadata, not the `_d` download variant) |
| `title`, `alt_text` | the photo title |
| `description` | the photo description (HTML stripped), `photo [source](photo page)`, `by [owner](profile)`, `Tags:`, the gallery, album or group it was found in, and the upload date |
| `original_source_url` | the Flickr photo page |
| `original_source_title` | `Flickr · <owner>` |

Photos that appear in several galleries or albums are written once. Videos are skipped (gallery-dl gives a player address, not a file). An "all albums" URL only queues the album URLs (gallery-dl entries of type 6): the script counts them but does not follow them, so run the album URLs themselves.

Tested only on a synthetic dump shaped from gallery-dl's [Flickr extractor](https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/flickr.py), not on a real run.
