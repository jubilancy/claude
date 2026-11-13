---
name: raindrop-organize
description: Organize a Raindrop.io collection by splitting it into sub-collections. Use when the user gives a Raindrop collection URL or ID and says organize, sort, clean up, or tidy it. Needs no extra instructions.
---

# Organize a Raindrop collection

Input: a Raindrop collection URL (`app.raindrop.io/my/<id>`) or ID, or a collection name. Run end to end without asking questions. Move bookmarks only and never delete anything.

Requires the Raindrop MCP tools (`mcp__Raindrop_io__*`). Load them with ToolSearch first if their schemas are not loaded: `find_collections`, `find_bookmarks`, `create_collections`, `update_bookmarks`.

## Steps

1. **Resolve the collection.** Take the ID from the URL, or find it by name with `find_collections`. Read its `bookmarks_count`. Check its existing sub-collections (entries whose `parent_id` is the collection ID) and reuse any that fit instead of creating duplicates.
2. **Fetch every bookmark.** Call `find_bookmarks` with `collection_ids: [id]`, `limit: 150` and `page: 1..N` (N = ceil(count / 150)), all pages in parallel. Large results are saved to a file under the session's `tool-results` directory. Parse those files with `uv run python -I` and never from memory. Items have only `bookmark_id`, `title`, `link` and `type`.
   - Results over a size limit are saved to a file; smaller ones come back inline. For anything you cannot script, fetch it with a server-side filter instead (`has_tags`, `created` as `YYYY-MM-DD`, `url_pattern`, `exclude_collection_ids`) and move the IDs shown.
   - Items usually carry `tags` and a `created` timestamp. Imports often arrive as batches with one tag or one timestamp. These are the best topic signal, so profile by tag and date as well as domain.
3. **Profile before deciding.** Count bookmarks by domain and URL shape with a script. Then pick 4 to 9 sub-collections that fit what this collection actually holds. Typical buckets:
   - Search pages and Google junk (`google.com/search`, `/imgres`, `/webhp`, `/preferences`, Maps, My Activity, `accounts.google.com`)
   - Image thumbnails (`encrypted-tbn*.gstatic.com/images`)
   - Favicon-only links (`encrypted-tbn*.gstatic.com/faviconV2`)
   - Shops and listings (retailers, marketplaces, auction houses, dealers, publisher stores)
   - Forums and Q&A (forums, Stack Exchange, Quora, Reddit, Facebook groups)
   - Reference and academic (Wikipedia, Gutenberg, Archive.org, Goodreads, journals, YouTube, encyclopedias)
   - A bucket for any single large domain (e.g. one site with 20 or more links)
   - When a batch shares a tag or import timestamp, make it one topic bucket and keep its own thumbnails, favicons and search pages inside it instead of splitting them into a junk bucket.
   - Do not invent buckets that would hold fewer than about 10 items, and do not create a bucket that ends up empty. Ambiguous items stay in the parent collection.
4. **Create the sub-collections** with `create_collections`, setting `parent_id` to the collection ID and a one-line `description` for each.
5. **Classify with a script.** Match on URL and domain with regexes. When rules overlap, check in this order: Google junk, domain-specific bucket, forums, shops, reference. A Goodreads or LibraryThing link is Reference, not Forums. Print the ID list per bucket and list the unclassified remainder for manual review.
6. **Move with `update_bookmarks`.**
   - Use one operation per bucket: `{bookmark_ids: [...], collection_id: <sub id>}`.
   - The tool allows at most 150 IDs per call in total, across all operations. Split larger buckets into several calls.
   - Copy IDs exactly from the script output. A mistyped ID moves an unrelated bookmark.
   - IDs within one import batch are often consecutive, so a script can expand a range. Never move a range blind: the same range can contain gaps whose IDs belong to other collections. Take the exact ID list from a filtered query, compare it with the range, and drop the gaps.
   - Create sub-collections after you have decided buckets, and move topic batches before broad URL-based buckets so the broad rules cannot override them.
7. **Verify with counts, not search.** The search index lags behind moves, so `find_bookmarks` keeps returning moved items for a while. Use `find_collections` instead: the parent's `bookmarks_count` should fall and the sub-collection counts should add up to `total_bookmarks_count`.
   - If the index is stale and you need the leftovers, use `exclude_collection_ids` with the sub-collection IDs, or `exclude_ids`.
   - Fix stragglers by classifying them by hand and moving them in one more call.
8. **Report briefly.** Give a table of sub-collection name and count, say what was left in the parent and why, and note that the sorting was by domain and not by reading each page. Mention that junk buckets (thumbnails, favicons, search pages) can be reviewed and deleted in one go. Do not restate steps taken.

## Root front pages

When the user asks to move bare front pages (site root URLs) that have other links from the same site in the same collection, use `scripts/root_homepages.py`. The Raindrop tools cannot filter to root URLs, so dump the collection first (`find_bookmarks` pages saved as files) and run:

`uv run python -I .claude/skills/raindrop-organize/scripts/root_homepages.py FILE [FILE ...] --target <collection id>`

It prints `update_bookmarks` operations (150 IDs max per call). Without `--target` it prints the roots with the number of other links per site. Roots match by host, ignoring a leading `www.`, so a subdomain is a different site. Pages returned inline instead of as files must be saved to a file first, or the roots in them are missed.

## Rules

- Never delete bookmarks or collections, and never merge collections, unless the user asks.
- Do not rename or move the user's existing collections.
- Do not fetch or verify page contents. Classification is from the URL and title already returned.
- Use `uv run python -I` for any scripts, never `python3` or `pip`. Save any script you write to `scripts/raindrop/` in the repository (docstring convention in CLAUDE.md), then run `uv run scripts/build_readme.py`. `extract_bookmarks.py` there turns inline `find_bookmarks` results into a JSON file from the session transcript.
