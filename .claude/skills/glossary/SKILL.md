---
name: glossary
description: Turn a pasted paragraph, word list, vibe, or set of themes into a themed glossary of related terms (no definitions), saved as a titled markdown file. Use when the user pastes words or a mood and asks for a glossary, related terms, vocabulary, or keyword ideas.
---

# Glossary

Input: whatever the user pastes (paragraph, word list, vibe, file tree, channel names). Output: a markdown file of related terms, grouped by theme, with no definitions.

## Steps

1. Extract the themes and every concrete word or phrase in the input. Messy text counts; pull terms out of descriptions too. De-duplicate.
2. Group related terms under 5-10 bold theme headings drawn from the input's own subjects (e.g. materials, objects, people, motifs, movements, places, collecting). Don't force empty groups.
3. Under each heading give one comma-separated line of terms: the input's own words that fit, plus closely related terms the user didn't list. A term may appear in more than one group only if it truly bridges them.
4. Terms only. No definitions, no explanations, no examples.
5. Write the file as `glossaries/<title-slug>.md` in the working directory, starting with a `# Title` line (a short evocative name for the vibe, 2-5 words, not "Glossary of ...").
6. Under the title, add one italic line: `*Related terms from my own associations; not checked against any source.*`
7. In chat, reply with the file path and the title only. Don't paste the glossary again.

## Rules

- Don't state facts about the terms (origins, dates, meanings). It is a vocabulary list.
- If the user asks for channel/slug/name ideas from it, check availability with a live lookup before listing any as free.
- Keep markdown plain: headings, bold group names, comma lists. No tables or HTML.
