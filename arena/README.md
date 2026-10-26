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

- Needs an Are.na token with **write** scope in `ARENA_TOKEN`.
- `--dry-run` prints what would be sent and uploads nothing.
- `--delay` sets seconds between posts (default 1).
- On a 429 it waits for the rate-limit reset and continues.
- Finished rows are recorded in `<csv>.uploaded`, so re-running skips them. Delete that file to upload everything again.
- Blocks are added one at a time, so their order in the channel will not match the CSV.

Tested against a local fake server and on one 127-pin channel; try `--dry-run` and a throwaway channel first.

## Known gaps / to do

- Dates in other languages are not stripped from descriptions (e.g. `29 окт. 2025 г. —`). Only the English forms and a few day-month-year forms are handled.
- Pinterest's "discover your own Pins" filler text is only filtered for the languages seen so far (English, Dutch, Portuguese, French, Indonesian, Japanese). German ("Entdecke...") and others can slip through.
- Titles and descriptions come straight from Pinterest, so some are odd (doubled or cut-off titles, scraped site text, ad copy). Planned: browse the Are.na channels, fix weird titles and enrich blocks with `updateBlock` rather than re-uploading.
- `arena_upload.py` has only been tested against a fake local server.
