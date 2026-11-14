# Prompt template: "pull a kind of media from a source into a CSV backend"

Copy everything below the line, fill in each `[BRACKET]`, delete the lines you don't need, and paste it into a new Claude Code session. The fixed directions (resumable, timestamped, log format, `--info`, `--md`) are the same every time; only the brackets change.

Attach `scripts/wikimedia/wiki_to_markdown.py` (the log format reference) and, if you want the same structure, `scripts/wikimedia/commons_to_csv.py` (a finished example of this template: Wikimedia Commons images).

---

I want a script like the attached `wiki_to_markdown.py`, but for **[TYPE OF MEDIA / THING: e.g. images, audio files, videos, books, species pages, artworks, posters]** from **[SOURCE: e.g. Wikimedia Commons, Flickr, Internet Archive, a museum API, a website]**.

**Input URLs.** It reads `urls.txt` (one per line, `#` comments and blank lines ok) and must support these URL types: **[URL TYPE 1: e.g. commons.wikimedia.org/wiki/File:...]**, **[URL TYPE 2: e.g. commons.wikimedia.org/wiki/Category:...]**, **[URL TYPE 3, or delete this]**. Anything else (search pages, special pages, other sites) is skipped on purpose and listed in the log, not treated as an error.

**Output.** One CSV row per **[ONE ITEM: e.g. image, track, book]**, written as it goes so an interrupted run keeps what it already got. Columns:
- **[FIELD GROUP 1: e.g. the item in different sizes or formats: original plus thumbnails at several widths]**
- **[FIELD GROUP 2: e.g. title, description, author, license, date]**
- **[FIELD GROUP 3: e.g. categories as the source gives them]**
- **[FIELD GROUP 4: e.g. taxonomy / classification / genre / period, from the source's own structured data]**
- **[FIELD GROUP 5, or delete this]**
- If possible, add **theme / tags / similar** to each row, built from the source's own data (categories, structured statements, classifications), not guessed. Say in the docstring exactly where each comes from.
- This CSV is the backend for **[FUTURE PROJECT: e.g. a gallery site, a recommendation engine, an Are.na import, a search index]**, so keep columns stable, use `|` between multiple values in one cell, and keep every URL absolute.

**Timestamps, no overwrites.** Every run writes a new `<name>_YYYY-MM-DD_HHMMSS.csv`. Never overwrite or append to an older CSV. Each CSV gets a matching `log_YYYY-MM-DD_HHMMSS.txt` with the same timestamp, in the same format as the log in `wiki_to_markdown.py` (header with run time, input file, output, URL counts; SUMMARY; then WRITTEN, SKIPPED, ERRORS and WARNINGS lists, each with the URL and a detail line).

**Large inputs: `--info`.** A flag that makes `info.txt` and does not fetch any items. It reports what is in `urls.txt` (lines, comments, duplicates, unsupported or special URLs), and for each URL its type and its item count, plus the total number of rows the CSV would have, a rough run time, and the row count of any existing CSVs in the output folder. For containers (categories, albums, playlists), `--subcats N` also counts N levels of sub-containers.

**Markdown: `--md`.** A flag that turns an existing CSV (not a new fetch) into a markdown gallery, either the whole file or only some of it: `--rows 1-20,35`, `--category TEXT`, `--tag TEXT`. It writes a timestamped `.md` file plus a matching log.

**Behavior I always want**
- Python with `uv` only: a `#!/usr/bin/env -S uv run --script` header with inline dependencies. No `python3`, no `pip`.
- Retry on 429 and 503, honoring `Retry-After`; one request at a time with a polite pause; a descriptive User-Agent with contact information, overridable with a flag.
- Skip special or generated pages up front, before any network request.
- Ctrl+C is safe: close the CSV cleanly and still write the log.
- Docstring in the repo's format: `name.py - one-line summary`, a "What it does" list, and a `Usage:` block of indented commands. Then run `uv run scripts/build_readme.py` and commit the result. Put the script in `scripts/[TOPIC]/`.
- **Verify, don't guess.** Check every API field, URL pattern and limit against the live source before using it; if something can't be verified, leave it out and say so. Test with a small real example, report exactly what was tested live and what was not, and do not claim more.

**Test inputs.** Use these to test: **[2-3 REAL EXAMPLE URLS, ideally one small container, one single item, and one that should be skipped]**.
