# Awesome CLI Tools for Claude Code

Command-line tools worth giving Claude Code in a cloud session (browser-only, no local machine). Every entry was checked on 2026-10-14: repo is public, not archived, and the description, license and install line come from the repo or docs page. Star counts are as shown that day.

Python tools are written with `uv`. Where a README only documents `pip`, the `uv` form is the standard equivalent and was not separately tested, except Crawl4AI, which was installed and run with `uv` in a Claude Code cloud session.

## Web to Markdown and crawling

- [Crawl4AI](https://github.com/unclecode/crawl4ai) - Open-source crawler that turns sites into LLM-ready Markdown. Apache-2.0, 85.5k stars. `uv add crawl4ai`, then `uv run crawl4ai-setup`. No API key needed except for LLM-based extraction.
- [Trafilatura](https://github.com/adbar/trafilatura) - Finds pages via sitemaps and feeds, extracts main text and metadata to Markdown, JSON and more. Apache-2.0, 7.0k stars. Does not render JavaScript.
- [MarkItDown](https://github.com/microsoft/markitdown) - Converts PDF, Word, PowerPoint, Excel, images, audio, HTML, EPUB and YouTube URLs to Markdown. MIT, about 190k stars. README install: `pip install 'markitdown[all]'`; CLI: `markitdown file.pdf -o out.md`.
- [shot-scraper](https://github.com/simonw/shot-scraper) - Screenshots, video demos and JavaScript-driven scraping from the command line, built on Playwright. Apache-2.0, 2.6k stars. README install: `pip install shot-scraper`, then `shot-scraper install`.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Audio and video downloader. The Unlicense, about 197.5k stars (release binaries are GPLv3+). Options such as `--skip-download` with `--write-subs` suggest transcript-only downloads, but the page shows no combined example, so check before relying on it.

## Data and search

- [DuckDB](https://github.com/duckdb/duckdb) - In-process analytical SQL database with a standalone CLI. MIT, 42.2k stars.
- [sqlite-utils](https://github.com/simonw/sqlite-utils) - CLI and library for SQLite: import JSON/CSV/TSV, query files in memory, set up full-text search. Apache-2.0, 2.2k stars.
- [Datasette](https://github.com/simonw/datasette) - Multi-tool for exploring and publishing data. Apache-2.0, 11.5k stars.
- [Pagefind](https://github.com/Pagefind/pagefind) - Fully static search for built sites, no server. MIT, 5.5k stars. Run `npx -y pagefind --site public` ([docs](https://pagefind.app/docs/)).
- [llm](https://github.com/simonw/llm) - Run language models from the command line, with embeddings commands (`llm embed`, `llm embed-multi`, `llm similar`). Apache-2.0, 12.6k stars. Install: `uv tool install llm`. Hosted providers need API keys; local models work through plugins such as `llm-ollama`.

## Quality gates

- [lychee](https://github.com/lycheeverse/lychee) - Fast link checker for Markdown, HTML and websites. Apache-2.0 / MIT, 4.0k stars. Useful for the verify-every-link rule.
- [actionlint](https://github.com/rhysd/actionlint) - Static checker for GitHub Actions workflow files. MIT, 4.3k stars.

## Everyday essentials

- [uv](https://github.com/astral-sh/uv) - Python package and project manager; `uvx` runs tools in an ephemeral environment and scripts can carry inline dependencies. Apache-2.0 / MIT, 90.7k stars.
- [ripgrep](https://github.com/BurntSushi/ripgrep) - Recursive regex search that respects `.gitignore`. MIT / Unlicense, 69.1k stars.
- [jq](https://github.com/jqlang/jq) - Command-line JSON processor. MIT, 35.8k stars.

## Deploy

- [Wrangler](https://github.com/cloudflare/workers-sdk) - Cloudflare Workers CLI. MIT / Apache-2.0, 4.6k stars. Install per the [docs](https://developers.cloudflare.com/workers/wrangler/install-and-update/): `npm i -D wrangler@latest`. How it authenticates non-interactively is not covered on that page and was not verified.

## Not included

- Anything not checked live. Newsboat and other RSS tools are in the [README](README.md) list instead.
