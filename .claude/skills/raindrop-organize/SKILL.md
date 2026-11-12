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
3. **Profile before deciding.** Count bookmarks by domain and URL shape with a script. Then pick 4 to 9 sub-collections that fit what this collection actually holds. Typical buckets:
   - Search pages and Google junk (`google.com/search`, `/imgres`, `/webhp`, `/preferences`, Maps, My Activity, `accounts.google.com`)
   - Image thumbnails (`encrypted-tbn*.gstatic.com/images`)
   - Favicon-only links (`encrypted-tbn*.gstatic.com/faviconV2`)
   - Shops and listings (retailers, marketplaces, auction houses, dealers, publisher stores)
   - Forums and Q&A (forums, Stack Exchange, Quora, Reddit, Facebook groups)
   - Reference and academic (Wikipedia, Gutenberg, Archive.org, Goodreads, journals, YouTube, encyclopedias)
   - A bucket for any single large domain (e.g. one site with 20 or more links)
   - Do not invent buckets that would hold fewer than about 10 items. Ambiguous items stay in the parent collection.
4. **Create the sub-collections** with `create_collections`, setting `parent_id` to the collection ID and a one-line `description` for each.
5. **Classify with a script.** Match on URL and domain with regexes. When rules overlap, check in this order: Google junk, domain-specific bucket, forums, shops, reference. A Goodreads or LibraryThing link is Reference, not Forums. Print the ID list per bucket and list the unclassified remainder for manual review.
6. **Move with `update_bookmarks`.**
   - Use one operation per bucket: `{bookmark_ids: [...], collection_id: <sub id>}`.
   - The tool allows at most 150 IDs per call in total, across all operations. Split larger buckets into several calls.
   - Copy IDs exactly from the script output. A mistyped ID moves an unrelated bookmark.
7. **Verify with counts, not search.** The search index lags behind moves, so `find_bookmarks` keeps returning moved items for a while. Use `find_collections` instead: the parent's `bookmarks_count` should fall and the sub-collection counts should add up to `total_bookmarks_count`.
   - If the index is stale and you need the leftovers, use `exclude_collection_ids` with the sub-collection IDs, or `exclude_ids`.
   - Fix stragglers by classifying them by hand and moving them in one more call.
8. **Report briefly.** Give a table of sub-collection name and count, say what was left in the parent and why, and note that the sorting was by domain and not by reading each page. Mention that junk buckets (thumbnails, favicons, search pages) can be reviewed and deleted in one go. Do not restate steps taken.

## Rules

- Never delete bookmarks or collections, and never merge collections, unless the user asks.
- Do not rename or move the user's existing collections.
- Do not fetch or verify page contents. Classification is from the URL and title already returned.
- Use `uv run python -I` for any scripts, never `python3` or `pip`. Keep scripts in the scratchpad, not the repository.
