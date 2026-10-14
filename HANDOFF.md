# Handoff

Context from the previous Claude Code cloud session (2026-10-14), written so a new session can continue without the conversation. Read `CLAUDE.md` first. It sets the standing rules.

## Standing rules (from `CLAUDE.md`)

- The user works in the browser (claude.ai/code cloud sessions), never locally. Don't give local-machine instructions.
- Python: use `uv` (`uv run`, `uv add`, `uv pip install`). Never `python3` or `pip`.
- Never write facts, links, versions or lists from memory. Verify each with a live tool before it goes in a file, PR or answer. If something can't be verified, leave it out and say so.
- Hyperlink every website. Use markdown tables or lists, not HTML or widgets, unless asked.
- Run searches silently and report findings only.

## What was done

1. **Awesome RSS tools list.** No dedicated awesome list of RSS tools existed. The closest were [voidfiles/awesome-rss](https://github.com/voidfiles/awesome-rss) and several feed lists. A new list lives in `README.md` (merged in [PR #3](https://github.com/jubilancy/claude/pull/3)).
2. **Link verification of that list.** The first draft was written from memory, which the user rejected. All 99 URLs were then checked. Removed: Nitter (archived), Feeder (archived), Podboat (404). Fixed: Read You and Eleventy RSS plugin repo moves, the Feedbro link, and the Wallabag description.
3. **`CLAUDE.md`** added with the standing rules above.

## Research already done (2026-10-14, recheck before relying on it)

### Data labeling and exploration tools

Best fit for a general ML or LLM labeling workflow on a budget:

- [Label Studio Community](https://github.com/HumanSignal/label-studio): Apache-2.0, self-host, any data type. PyPI `label-studio` 1.23.2. The Chat tag is not in Community ([comparison](https://labelstud.io/guide/label_studio_compare)). Hosted Starter Cloud is $99 per month plus $49 per extra user, with a free trial ([pricing](https://humansignal.com/pricing/)).
- [Argilla](https://docs.argilla.io/latest/): Apache-2.0, LLM and NLP human feedback. `argilla` 2.8.0.
- [Langfuse](https://langfuse.com/pricing): annotation queues for LLM traces. MIT. Cloud Hobby is free at 50k units per month, 30 days of data, 2 users ([clarifications](https://langfuse.com/resources/engineering/clarifications)).
- Images: [CVAT](https://github.com/cvat-ai/cvat) (MIT, self-host), [Roboflow](https://docs.roboflow.com/platform/billing-and-plans/plans) (free tier of 10 credits per month), [Labelbox](https://docs.labelbox.com/horizon/guides/limits) (free: 500 units per month, 30 users, 50 projects).
- Exploration: [FiftyOne](https://pypi.org/project/fiftyone/) 1.22.1, [cleanlab](https://pypi.org/project/cleanlab/) 2.9.0, [ydata-profiling](https://pypi.org/project/ydata-profiling/) 4.18.4, [datasette](https://pypi.org/project/datasette/) 0.65.5, [duckdb](https://pypi.org/project/duckdb/) 1.5.6.
- Hugging Face Spaces: only Static Spaces are free. Docker and Gradio Spaces need a paid plan ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview)). That conflicts with Argilla's "deploy free on the Hub" docs.
- Claude connectors and skills: the Roboflow and Hugging Face connectors are in the Claude directory. There is a [Label Studio MCP server](https://github.com/HumanSignal/label-studio-mcp-server) (stale, last push 2025-05-30). The Label Studio [`create-xml-labeling-config-skill`](https://docs.humansignal.com/skills) works on Community.
- Not confirmed and skipped: Nomic Atlas free tier, Cleanlab Studio free tier, SuperAnnotate (no free plan shown), V7, Datasaur (enterprise only), Perspective's npm version.
- No ready-made Cloudflare Workers labeling app was found. Free Cloudflare limits: [Workers](https://developers.cloudflare.com/workers/platform/limits/) 100k requests per day; [D1](https://developers.cloudflare.com/workers/platform/pricing) 5M rows read and 100k rows written per day, 5 GB; [R2](https://developers.cloudflare.com/r2/pricing/) 10 GB-month; [Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) 10,000 Neurons per day.

### WebFetch and web extraction

- WebFetch behavior is documented in the [tools reference](https://code.claude.com/docs/en/tools-reference) and [data usage](https://code.claude.com/docs/en/data-usage). It converts HTML to Markdown, answers the prompt through a separate model call (lossy), reads up to 100,000 characters per call, caches 15 minutes, refuses localhost, and returns cross-host redirects instead of following them. It sends only the hostname to `api.anthropic.com` for a safety check.
- Recommended tools: curl plus [trafilatura](https://pypi.org/project/trafilatura/) for static pages. [Cloudflare Browser Run](https://developers.cloudflare.com/browser-run/quick-actions/) `/markdown` for JavaScript pages (Workers Free: 10 browser minutes per day, 3 concurrent browsers). [Crawl4AI](https://github.com/unclecode/crawl4ai) (Apache-2.0, 0.9.4) for site crawls. [Firecrawl](https://github.com/firecrawl/firecrawl) is optional. Its license is AGPL-3.0, with MIT SDKs.

## Environment notes

- This environment blocks most outside hosts and the GitHub API. Link checking worked through the Tavily connector (extract and search) and through WebFetch. Tavily lost its connection late in the session ("needs authentication") and may need reconnecting.
- Suggested allowed domains for the cloud environment: `github.com`, `api.github.com`, `gitlab.com`, `docs.github.com`, `raw.githubusercontent.com`, `validator.w3.org`, `www.rssboard.org`. Set them under the environment's network settings. See [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments).
- The standing rules were also drafted for the user's Claude.ai personal preferences (Settings → Instructions for Claude). It's unconfirmed whether they apply to Claude Code cloud sessions, so `CLAUDE.md` is the one that definitely loads.

## Moving sessions (from the [cloud sessions docs](https://code.claude.com/docs/en/claude-code-on-the-web))

- No documented way to move a conversation into a new cloud session. Context carries through the repo, so this file is the handoff.
- `claude --teleport` pulls a cloud session into a terminal. Not relevant for a browser-only user.

## Open items

- Decide whether the RSS list should become its own `awesome-rss-tools` repo. The repo-name convention for awesome lists is the usual choice.
- Optional: turn the data-labeling research into its own awesome list, with the "Not confirmed" items re-verified first.
- Not checked: Firecrawl cloud pricing, Jina pricing, Cloudflare REST request limits on the free plan, whether Crawl4AI needs Playwright.
