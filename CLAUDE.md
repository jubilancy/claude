# Instructions for Claude

## How I use Claude

- I use Claude Code **in the browser (claude.ai/code cloud sessions), never locally**. Assume a remote, ephemeral container with no access to my machine, home directory, or local files. Don't tell me to run things "locally" or edit files in `~/.claude/` unless I ask; give browser/app settings paths instead.
- I use `uv` for Python. Never give `python3` or `pip` commands; use `uv run`, `uv add`, `uv pip install`.

## Verify, never write from memory

- Never write facts, links, repo names, versions, descriptions or lists from memory.
- Verify every URL and claim with a live tool (fetch, search, GitHub tools) before putting it in a file, PR, or answer.
- If something can't be verified, leave it out and say so. Don't hand unverified work back for me to check.
- For link lists, check that each link resolves, the project isn't archived, and the description matches the page.

## Book and ISBN lookups

- Messy pasted text (search-result dumps, "People also search for" blocks, descriptions) still contains books. Normalize it first: extract every book title mentioned, including ones named only inside descriptions, and de-duplicate variants of the same title.
- Look up every extracted title. Never skip a title because it sits in messy text. If no ISBN is found, keep the row and write "Not found".
