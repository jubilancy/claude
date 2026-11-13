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

## Scripts

- **Always add the scripts you write to the repo.** Every script (including ones the user shares) goes in `scripts/<topic>/`, not left in the scratchpad.
- **Every script writes a results log on every run**, modelled on `scripts/wikimedia/wiki_info.py` (and `wiki_to_markdown.py`):
  - File name `results-log-{YYYY-MM-DD_HHMMSS}.txt` (the run's start time), written to the current folder. Never overwrite an earlier log.
  - A header with `Run started :`, `Run finished:` (with duration), the input and the output paths.
  - A `SUMMARY` block with counts: total, done this run, already done (skipped), skipped on purpose, errors.
  - Then one list per outcome, each headed with its count, for example `SUCCESSFUL: WRITTEN (n)`, `SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT (n)`, `SKIPPED ON PURPOSE: <why> (n)`, `ERRORS (n)` and `WARNINGS (n)`. Each item is the input on one line and the detail or reason on an indented line under it. An empty list shows `(none)`.
  - The log is written even when every item fails, and a failure on one item never stops the run.
  - Mention the log in the script's docstring and print its path at the end of the run.
  - Applies to scripts that process many items or change things. A small read-only helper that just prints to the screen may skip it, but say so in its docstring.
- Standalone scripts live in `scripts/`. Give each a docstring that starts `name.py - one-line summary` and a `Usage:` block with indented commands (see `scripts/wikimedia/wiki_info.py`).
- `scripts/README.md` is generated. After adding or editing a script, run `uv run scripts/build_readme.py` and commit the result. A GitHub Action also rebuilds it on pushes to `main`.
