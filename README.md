# claude

Scripts, notes and small projects, kept in one repo and slowly turning into dotfiles. The layout follows the topic-centric approach of [holman/dotfiles](https://github.com/holman/dotfiles) (everything grouped by topic, not by file type) and keeps runnable tools in their own folder like the `bin/` directory of [mathiasbynens/dotfiles](https://github.com/mathiasbynens/dotfiles).

## Layout

| Path | What lives there |
|---|---|
| [`scripts/`](scripts/README.md) | Command-line tools, one folder per topic (`books`, `cosmos`, `discord`, `tumblr`, `web`, `wikimedia`). Its README is generated. |
| [`arena/`](arena/README.md) | Pinterest and Flickr to Are.na scripts, plus `wiki_to_csv.py`. |
| [`awesome/`](awesome) | Curated lists in Markdown: Claude Code CLI tools, RSS tools. |
| [`bluesky-bulk/`](bluesky-bulk) | Bulk-post to Bluesky from a CSV. |
| [`social-archive/`](social-archive) | Download Instagram, Twitter/X and TikTok posts with gallery-dl. |
| [`social-scrapers/`](social-scrapers/README.md) | Scraping notes and scripts for TikTok comments and Twitter replies. |
| [`generative-art-template/`](generative-art-template/README.md) | Dependency-free starting point for canvas art. |
| [`sept-01/`](sept-01) | A canvas sketch in plain HTML, CSS and JavaScript. |
| [`isbn/`](isbn) | ISBN lookup results as CSV. |
| [`data/`](data) | Loose data files that belong to no single tool. |
| [`.claude/skills/`](.claude/skills) | Claude Code skills (`glossary`, `pinimg-dedupe`, `raindrop-organize`). |
| [`CLAUDE.md`](CLAUDE.md), [`HANDOFF.md`](HANDOFF.md) | Standing instructions for Claude sessions, and notes from an earlier one. |

## Conventions

- **Run from the repo root** with [uv](https://docs.astral.sh/uv/): `uv run scripts/<topic>/<script>.py`. Python scripts declare their dependencies inline, so there is nothing to install.
- **A topic folder holds a tool and its data**: the script, its example URL list, and any files it reads. Add a folder instead of adding files at the root.
- **Every script starts with a docstring** whose first line is `name.py - one-line summary`, followed by a `Usage:` block. [`scripts/README.md`](scripts/README.md) is built from those headers by `uv run scripts/build_readme.py`, and a GitHub Action rebuilds it on pushes to `main`.
- **Secrets never go in the repo.** Tokens come from environment variables.
