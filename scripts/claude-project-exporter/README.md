# Claude Project ZIP Exporter

A userscript that exports one claude.ai Project as a single ZIP: custom instructions, knowledge files, every chat as Markdown plus raw JSON, chat attachments, artifacts, and a count check that refuses to say "complete" when anything is missing.

- One file: [`claude-project-exporter.user.js`](claude-project-exporter.user.js). No framework, no `@require`, `@grant none`.
- Same-origin `GET` requests only, with the session the page already has. No tokens or cookies are read or copied. Any URL that is not on `https://claude.ai` is refused, not fetched.
- The ZIP is built in the page by a small built-in ZIP writer, so there is no third-party library to pin or trust.

**Status: not yet run against live claude.ai.** The build environment gets HTTP 403 from claude.ai, so every endpoint below is taken from the published source of other exporters, not observed. Read "What is verified and what is not" before you delete a project.

## Install (browser only)

You need a userscript manager extension: [Violentmonkey](https://violentmonkey.github.io/) or [Tampermonkey](https://www.tampermonkey.net/).

1. Open [`claude-project-exporter.user.js`](claude-project-exporter.user.js) on GitHub, click **Raw**, select all, copy.
2. Create a new script in the manager and replace its template with what you copied:
   - Violentmonkey: click the toolbar icon, then the **+** icon ([guide](https://violentmonkey.github.io/guide/creating-a-userscript/)).
   - Tampermonkey: open the dashboard and click **Add a new script** ([FAQ Q102](https://www.tampermonkey.net/faq.php?q=Q102)).
3. Save. In a Chrome-based browser Tampermonkey also needs the **Allow User Scripts** toggle or Developer Mode ([FAQ Q209](https://www.tampermonkey.net/faq.php?q=Q209)).

## Use

1. Open the project: `https://claude.ai/project/<id>`. An **Export project ZIP** button appears bottom right.
2. Click it. In the panel, either paste the project's memory text into the box (copy it from the project page) or tick **This project has no memory**. Memory has no verified endpoint, so the script cannot read it for you.
3. Click **Start export**. Keep the tab open. **Cancel** stops the run and still downloads what was collected, marked incomplete.
4. Read the result table: chats found vs in ZIP, files found vs in ZIP.
   - **COMPLETE**: everything found is in the ZIP.
   - **COMPLETE WITH WARNINGS**: everything found is in the ZIP, but something is not the original (extracted text or a preview image), or a cross-check was not possible. Read `_errors.md`.
   - **INCOMPLETE**: something is missing. The file name ends in `-INCOMPLETE.zip` and the panel lists why. Do not delete the project.

## What is in the ZIP

| Path | Contents |
| --- | --- |
| `project/instructions.md` | Custom instructions (`prompt_template`) |
| `project/memory.md` | Memory text you pasted into the panel |
| `project/project.json` | Raw project details |
| `knowledge/` | Knowledge files. `knowledge/_index.json` flags each one: `original`, `text_content`, `extracted_text` or `preview` |
| `chats/<date>-<slug>-<id8>.md` | Transcript with YAML frontmatter. Active branch first, then every edited or regenerated message under "Other branches" |
| `raw/<date>-<slug>-<id8>.json` | Untouched API response for that chat |
| `files/<chat>/attachments/` | Uploads: pasted text as `.extracted.txt`, files as downloaded |
| `files/<chat>/artifacts/` | Every artifact version (`<id>-v<n>.<ext>`) |
| `files/<chat>/container/` | Files from the chat's code-execution container, when claude.ai still serves them |
| `_manifest.json` | Verdict, counts, project, every chat and knowledge file |
| `chat_db.json` | One row per chat: id, title, url, created, updated, message_count, attachment_count, status |
| `attachment_db.json` | One row per attachment, artifact version, container file and knowledge file, with its chat, source URL, saved path and status |
| `_errors.md` | Everything that failed or was skipped, with the reason |
| `results-log-<timestamp>.txt` | Run log in this repo's results-log format |

## What is verified and what is not

**Verified here**

- 23 Node tests pass: slugs, safe file names, duplicate titles, Markdown conversion (code blocks byte-for-byte, tool calls, file references, unknown block types kept), branch handling, artifact version replay, the count check, the ZIP writer (checked with `unzip -t`), and the whole export run against an in-memory fake API covering pagination with a capped page size, a 429 retry, a chat that always returns 500, an unretrievable file, cancel, and an unreadable project.
- A headless Chromium run on a faked `claude.ai` page: the button appears after in-app navigation, the download is a valid ZIP, the panel shows the counts, capture mode logs shapes with ids and values removed, and no request goes to any other origin.

**Not verified: nothing has been run against the real site**

- Every endpoint and field name. They are copied from other exporters' source (table below), which is evidence that they worked for those authors, not that they work today.
- Whether `projects/<id>/conversations` pages. The script cross-checks it against the full, paged conversation list filtered by project id, and warns if that cross-check is not available.
- Whether the docs and files lists page. A project with a very large knowledge base could be cut short without the script knowing. Compare the knowledge count with the project page.
- Project memory: no endpoint was found in any source. Paste it manually.
- Whether uploaded images and PDFs come back as original bytes. Anything saved from a preview URL is flagged as `preview`.
- Behavior inside Violentmonkey and Tampermonkey themselves. The UI test injected the script directly.
- Very large projects. The ZIP is built in memory, and ZIP64 is not supported (limits: 4 GB, 65,534 entries; hitting one is reported as an error).

## Manual test (browser only)

1. Install as above. Open a small project you do not mind testing on.
2. Count by hand on the project page: chats, knowledge files.
3. Run the export with **This project has no memory** ticked (or memory pasted).
4. Check the panel: "Chats found" must equal your hand count. If it is lower, stop and send me the capture log.
5. Open the ZIP (your OS can open it, or upload it to a new Claude chat and ask for a listing). Check that `_manifest.json` has `"complete": true`, that `counts.chats.found` equals `counts.chats.exported`, and that `chat_db.json` has one row per chat.
6. Open one long chat's `.md` and compare the first and last message with the site. Open `project/instructions.md` and compare with the project's instructions.
7. Read `_errors.md` even when the verdict is COMPLETE.

## Capture mode

If an endpoint has changed, tick **Capture mode** in the panel and reload the page. Click around the project (open the files list, the memory panel, a chat). The box fills with each `/api/` request the page made and the shape of its JSON response: keys and types only, with ids replaced by `{uuid}`. Click **Copy capture log** and paste it to me.

If entries show `"via": "performance"` with no `shape`, the manager ran the script outside the page context ([Violentmonkey `@inject-into`](https://violentmonkey.github.io/api/metadata-block/) falls back to this when the site's CSP blocks page injection). Click **Probe URLs without a body**: the script then GETs those same URLs once itself to read their shapes.

## Where the endpoints come from

| Endpoint (under `/api/organizations/<org>/` unless shown in full) | Source |
| --- | --- |
| `/api/organizations` | Claude Project Files Extractor |
| `projects/<id>` and its `prompt_template` field | Claude Project Documents Exporter Library |
| `projects/<id>/docs` | Claude Project Files Extractor, Claude Project Documents Exporter Library |
| `projects/<id>/files`, `/api/<org>/files/<id>/document_pdf`, `document_asset.url`, `preview_url` | Claude Project Files Extractor |
| `projects/<id>/conversations` | Claude Mass Exporter Library |
| `chat_conversations?limit=&offset=` | Claude Chat Exporter (all chats, all organizations) |
| `chat_conversations/<id>?tree=True&rendering_mode=messages&render_all_tools=true` | Claude Conversation Exporter (socketteer) |
| `project_uuid` on conversations | claude-exporter (agoramachina), Claude API Exporter |
| `files/<id>/contents`, `files_v2` | Claude Powerest Manager Enhancer |
| `conversations/<id>/wiggle/list-files`, `wiggle/download-file`, artifact `tool_use` fields | Claude API Exporter |

## Credits and licenses

No code was copied from any of these. They were read for endpoints, field names and ideas, and each license was checked on the date of this build.

- [socketteer/Claude-Conversation-Exporter](https://github.com/socketteer/Claude-Conversation-Exporter): **no license** (the README's License section still reads "[Add your chosen license here]" and there is no LICENSE file), so nothing was reused beyond the endpoint URL and the idea of walking `current_leaf_message_uuid` back to the root.
- [Claude Project Files Extractor](https://greasyfork.org/scripts/541467-claude-project-files-extractor) by sharmanhall, MIT. The order of download candidates for a file follows its approach.
- [Claude API Exporter](https://greasyfork.org/scripts/542117-claude-api-exporter), [Claude Mass Exporter Library](https://greasyfork.org/scripts/543706-claude-mass-exporter-library) and [Claude Project Documents Exporter Library](https://greasyfork.org/scripts/546704-claude-project-documents-exporter-library) by Mero Tah, MIT.
- [Claude Chat Exporter (all chats, all organizations)](https://greasyfork.org/scripts/598747-claude-chat-exporter-all-chats-all-organizations) by Ivan Velikanov, MIT.
- [Claude Powerest Manager Enhancer](https://greasyfork.org/scripts/539886) by f14xuanlv, MIT.
- [agoramachina/claude-exporter](https://github.com/agoramachina/claude-exporter), MIT.

The Greasy Fork pages and both GitHub pages return 403 to the build environment's browser-style requests. The scripts were fetched through the Greasy Fork API and `update.greasyfork.org`, and the two repositories were cloned, so the links are confirmed to exist; whether a GitHub repository is archived could not be checked.

## Tests

```bash
node --test scripts/claude-project-exporter/claude-project-exporter.test.js
```

```bash
node scripts/claude-project-exporter/ui-smoke.js
```

The second one needs Playwright, which Claude Code cloud sessions have preinstalled.
