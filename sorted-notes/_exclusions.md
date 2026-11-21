---
title: "Exclusions"
description: "Everything not carried over verbatim, grouped by source file."
concepts:
  - "exclusions"
  - "merged duplicates"
  - "removed syntax"
tags:
  - exclusions
  - audit
sources:
  - "3 TweetDetail 11 items received.md"
  - "completed searches.md"
  - "Dec.6.25.md"
  - "doc holliday llm prompt.md"
  - "Fool's Cap World Map.md"
  - "Fringechan Archive.md"
  - "Georgia O'Keeffe and Oppenheimer.md"
  - "Global Language Resources.md"
  - "index → to-sort.md"
  - "info.md"
  - "lens by google.md"
  - "Libre Cloud Services - OpenDesktop.org.md"
  - "links.md"
  - "Metadata.md"
  - "new!!.md"
  - "notes.md"
  - "old-st-pauls.md"
  - "Page Token.md"
  - "Queen Bouddica.md"
  - "r-Fantasy books.md"
  - "research base.base"
  - "Returns images from given page of booruproject.md"
  - "Series Harvard Classics.md"
  - "Squirrel Emojis.md"
  - "summarizer.md"
  - "the origin of going to church.md"
  - "Third-party Licenses.md"
---

# Exclusions

Presentation fixes are applied only to the cleaned text. The original text is untouched in `_ledger.csv`.

## Whole-batch notes

- Ignored macOS AppleDouble metadata files in `__MACOSX/` (names starting with `._`): resource-fork data, not notes.
- URLs inside fenced code blocks are kept verbatim there and also listed as clickable links in [the appendix](97-appendix-other-urls.md).
- HTML tags are removed; of their attributes only href, src and alt are kept (as links). Other attributes (width, height, style, frameborder, colspan, SVG path data and similar) are dropped. Tag names and counts are listed per source below.
- Exact duplicates are merged only within the same output file, and never for headings, separators or units under 3 words.
- No image files were attached, so no OCR was done. Images are kept as links; an image with no alt text is marked *(image-only, not captured)*.

## S01 3 TweetDetail 11 items received.md

### S01 Merged duplicates

- S01-L207-207: exact duplicate of S01-L203-203

### S01 Units not carried over (no text content)

- markdown separator line (no text content): 18 (units S01-L20-20, S01-L29-29, S01-L39-39, S01-L48-48, S01-L57-57, S01-L66-66, S01-L75-75, S01-L85-85, S01-L94-94, S01-L103-103, S01-L112-112, S01-L218-218, S01-L222-222, S01-L226-226, S01-L230-230, S01-L234-234, S01-L238-238, S01-L294-294)
  - examples: `---`; `---`; `---`
- empty heading (marker only, no text): 2 (units S01-L118-118, S01-L193-193)
  - examples: `##`; `##`

### S01 Removed or changed syntax (counts and examples)

- Thematic break line removed (no text): 18 (examples: `---`)
- Plain multi-line block converted to a bullet list: 15
- Empty-text link converted to an autolink: 14 (examples: `[](https://x.com/funnyprettynice)`; `[](https://x.com/FKAelusive)`; `[](https://x.com/BolshevikNoir)`)
- Image syntax converted to a link: 4 (examples: `![🏗](https://abs.twimg.com/emoji/v2/svg/1f3d7.svg)`; `![💻](https://abs.twimg.com/emoji/v2/svg/1f4bb.svg)`; `![🦋](https://abs.twimg.com/emoji/v2/svg/1f98b.svg)`)
- Space-like character replaced by a space: NO-BREAK SPACE: 4 (examples: `'\xa0'`)
- Empty heading marker removed: 2 (examples: `##`)
- Trailing whitespace / double-space line break removed: 2 (examples: `'1740) '`; `'alus) '`)
- Link lines converted to a Title | URL table: 1

### S01 Image-only items

None

## S02 completed searches.md

### S02 Merged duplicates

None

### S02 Units not carried over (no text content)

- markdown separator line (no text content): 5 (units S02-L36-36, S02-L64-64, S02-L66-66, S02-L108-108, S02-L110-110)
  - examples: `---`; `---`; `---`

### S02 Removed or changed syntax (counts and examples)

- Thematic break line removed (no text): 5 (examples: `---`)
- Plain multi-line block converted to a bullet list: 4
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S02 Image-only items

None

## S03 Dec.6.25.md

### S03 Merged duplicates

None

### S03 Units not carried over (no text content)

- markdown separator line (no text content): 1 (units S03-L266-266)
  - examples: `---`

### S03 Removed or changed syntax (counts and examples)

- Space-like character replaced by a space: NO-BREAK SPACE: 121 (examples: `'\xa0'`)
- Bare URL converted to an angle-bracket autolink: 10 (examples: `https://eliana.lol/`; `https://huffduffer.com/eliana`; `https://pixabay.com/users/etmr`)
- Plain multi-line block converted to a bullet list: 5
- Link list converted to a Title | URL table: 4
- Trailing whitespace / double-space line break removed: 4 (examples: `'el**  '`; `'e/).  '`; `'try.  '`)
- Combining strikethrough U+0336 converted to markdown strikethrough: 3 (examples: ` buy a cheap second-hand surfboard`; `read blockchain chicken farm`; ` fix my oven`)
- Link lines converted to a Title | URL table: 1
- Thematic break line removed (no text): 1 (examples: `---`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S03 Image-only items

None

## S04 doc holliday llm prompt.md

### S04 Merged duplicates

None

### S04 Units not carried over (no text content)

- markdown separator line (no text content): 5 (units S04-L9-9, S04-L34-34, S04-L56-56, S04-L88-88, S04-L94-94)
  - examples: `---`; `---`; `---`

### S04 Removed or changed syntax (counts and examples)

- Trailing whitespace / double-space line break removed: 38 (examples: `'day.  '`; `'nce.  '`; `'ink.  '`)
- Thematic break line removed (no text): 5 (examples: `---`)
- Plain multi-line block converted to a bullet list: 4
- Space-like character replaced by a space: NARROW NO-BREAK SPACE: 3 (examples: `'\u202f'`)

### S04 Image-only items

None

## S05 Fool's Cap World Map.md

### S05 Merged duplicates

- S05-L81-81: exact duplicate of S05-L4-4
- S05-L87-87: exact duplicate of S05-L10-10
- S05-L95-95: exact duplicate of S05-L18-18
- S05-L107-107: exact duplicate of S05-L30-30
- S05-L109-109: exact duplicate of S05-L32-32
- S05-L111-111: exact duplicate of S05-L34-34
- S05-L113-113: exact duplicate of S05-L36-36
- S05-L157-157: exact duplicate of S05-L155-155

### S05 Units not carried over (no text content)

- markdown separator line (no text content): 2 (units S05-L73-73, S05-L175-175)
  - examples: `* * *`; `---`

### S05 Removed or changed syntax (counts and examples)

- Image syntax converted to a link: 52 (examples: `![🗺](https://static.xx.fbcdn.net/images/emoji.php/v9/t67/2/16/1f5)`; `![🍀](https://static.xx.fbcdn.net/images/emoji.php/v9/t26/2/16/1f3)`; `![🏰](https://static.xx.fbcdn.net/images/emoji.php/v9/t34/2/16/1f3)`)
- Space-like character replaced by a space: NO-BREAK SPACE: 51 (examples: `'\xa0'`)
- Trailing whitespace / double-space line break removed: 4 (examples: `'-R) · '`; `'ists. '`; `'tury. '`)
- Lone closing square bracket escaped: 2 (examples: `nce of self-reflection.[3] In the left-h`)
- Lone opening square bracket escaped: 2 (examples: `elf-reflection.[3] In the left-hand corn`)
- Thematic break line removed (no text): 2 (examples: `* * *`; `---`)
- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://www.facebook.com/share/p/1FaBDU6Yw3/`)
- Empty-text link converted to an autolink: 1 (examples: `[](https://www.facebook.com/sosruko.3?__cft__[0]=AZiz4AIE7Buo-c)`)
- HTML tag removed: iframe: 1 (examples: `<iframe>`)
- Plain multi-line block converted to a bullet list: 1

### S05 Image-only items

1 image(s) with no alt text kept as links and marked image-only, not captured.

## S06 Fringechan Archive.md

### S06 Merged duplicates

- S06-L171-171: exact duplicate of S06-L165-165
- S06-L191-191: exact duplicate of S06-L183-183

### S06 Units not carried over (no text content)

None

### S06 Removed or changed syntax (counts and examples)

- Empty-text link converted to an autolink: 2 (examples: `[](https://web.archive.org/web/http://fringechan.org/library/sr)`)
- Image syntax converted to a link: 2 (examples: `![](https://web.archive.org/web/http://fringechan.org/library/th)`)
- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://fringearchives.top/archive/fringechan/library/1.html`)
- Lone closing square bracket escaped: 1 (examples: `[x] **Vampires/is`)
- Lone opening square bracket escaped: 1 (examples: `[x] **Vampires/ism & ener`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S06 Image-only items

2 image(s) with no alt text kept as links and marked image-only, not captured.

## S07 Georgia O'Keeffe and Oppenheimer.md

### S07 Merged duplicates

None

### S07 Units not carried over (no text content)

None

### S07 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://www.tiktok.com/@sineatahh/video/7697929282387053855`)
- Plain multi-line block converted to a bullet list: 1
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S07 Image-only items

None

## S08 Global Language Resources.md

### S08 Merged duplicates

- S08-L62-64: exact duplicate of S08-L34-36
- S08-L66-68: exact duplicate of S08-L38-40
- S08-L104-104: exact duplicate of S08-L102-102
- S08-L134-134: exact duplicate of S08-L128-128
- S08-L136-136: exact duplicate of S08-L130-130
- S08-L248-248: exact duplicate of S08-L244-244
- S08-L252-252: exact duplicate of S08-L244-244
- S08-L260-260: exact duplicate of S08-L244-244
- S08-L270-270: exact duplicate of S08-L266-266
- S08-L282-282: exact duplicate of S08-L276-276
- S08-L284-284: exact duplicate of S08-L278-278
- S08-L294-294: exact duplicate of S08-L290-290
- S08-L308-308: exact duplicate of S08-L302-302
- S08-L322-322: exact duplicate of S08-L316-316
- S08-L332-332: exact duplicate of S08-L328-328
- S08-L346-346: exact duplicate of S08-L340-340
- S08-L356-356: exact duplicate of S08-L352-352

### S08 Units not carried over (no text content)

- stray symbols only (no words, URLs or emoji): 1 (units S08-L120-120)
  - examples: `<svg aria-hidden="true" fill="currentColor" height="24px" vi`
- markdown separator line (no text content): 1 (units S08-L383-383)
  - examples: `---`

### S08 Removed or changed syntax (counts and examples)

- Space-like character replaced by a space: NO-BREAK SPACE: 21 (examples: `'\xa0'`)
- Bare URL converted to an angle-bracket autolink: 19 (examples: `https://www.google.com/search?q=Global+Language+Resources&sourceid=chrome&ie=UTF-8&source=chrome.ctxt`; `https://www.worldlanguageresources.com`; `https://globaledge.msu.edu`)
- Plain multi-line block converted to a bullet list: 16
- HTML entity decoded: 3 (examples: `&amp;`)
- HTML tag removed: iframe: 1 (examples: `<iframe>`)
- HTML tag removed: path: 1 (examples: `<path>`)
- HTML tag removed: svg: 1 (examples: `<svg>`)
- Stray-symbol-only unit removed: 1 (examples: `<svg aria-hidden="true" fill="currentCol`)
- Thematic break line removed (no text): 1 (examples: `---`)
- Trailing whitespace / double-space line break removed: 1 (examples: `'ng**? '`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S08 Image-only items

None

## S09 index → to-sort.md

### S09 Merged duplicates

None

### S09 Units not carried over (no text content)

None

### S09 Removed or changed syntax (counts and examples)

- Wikilink double brackets removed (text kept): 26 (examples: `[[to-sort/3 TweetDetail 11 items received|3 TweetDetail 11 items received]]`; `[[to-sort/completed searches|completed searches]]`; `[[to-sort/Dec.6.25|Dec.6.25]]`)
- Obsidian percent-percent comment markers removed (text kept): 2 (examples: `%% Zoottelkeeper: Beginning of the autogenerated index file list  %%`; `%% Zoottelkeeper: End of the autogenerated index file list  %%`)
- Trailing whitespace / double-space line break removed: 2 (examples: `' list '`)
- Plain multi-line block converted to a bullet list: 1

### S09 Image-only items

None

## S10 info.md

### S10 Merged duplicates

None

### S10 Units not carried over (no text content)

- markdown separator line (no text content): 1 (units S10-L108-108)
  - examples: `---`

### S10 Removed or changed syntax (counts and examples)

- Trailing whitespace / double-space line break removed: 63 (examples: `'u/).  '`; `'act)  '`; `'ear)  '`)
- Link lines converted to a Title | URL table: 5
- Link list converted to a Title | URL table: 1
- Plain multi-line block converted to a bullet list: 1
- Thematic break line removed (no text): 1 (examples: `---`)

### S10 Image-only items

None

## S11 lens by google.md

### S11 Merged duplicates

None

### S11 Units not carried over (no text content)

None

### S11 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://lens.google.com/uploadbyurl?url=https%3A%2F%2Fwww.mediafire.com%2Fconvkey%2F57c2%2F8fz7b34tliwn7my9g.jpg`)

### S11 Image-only items

None

## S12 Libre Cloud Services - OpenDesktop.org.md

### S12 Merged duplicates

None

### S12 Units not carried over (no text content)

None

### S12 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 41 (examples: `https://my.opendesktop.org/apps/files/`; `https://my.opendesktop.org/apps/calendar/`; `https://my.opendesktop.org/apps/contacts/`)
- Trailing whitespace / double-space line break removed: 2 (examples: `'ase.  '`; `'org.  '`)
- Link list converted to a Title | URL table: 1
- Plain multi-line block converted to a bullet list: 1

### S12 Image-only items

None

## S13 links.md

### S13 Merged duplicates

None

### S13 Units not carried over (no text content)

None

### S13 Removed or changed syntax (counts and examples)

- Trailing whitespace / double-space line break removed: 11 (examples: `'pp#)  '`; `'ure)  '`; `'ers)  '`)
- Bare URL converted to an angle-bracket autolink: 8 (examples: `https://ely.mataroa.blog/blog/1093671090783256632/`; `https://snackprompt.com/cute`; `https://promptden.com/profile/ely`)
- Link lines converted to a Title | URL table: 2

### S13 Image-only items

None

## S14 Metadata.md

### S14 Merged duplicates

None

### S14 Units not carried over (no text content)

- markdown separator line (no text content): 1 (units S14-L38-38)
  - examples: `---`

### S14 Removed or changed syntax (counts and examples)

- Space-like character replaced by a space: NO-BREAK SPACE: 23 (examples: `'\xa0'`)
- HTML tag removed: td: 7 (examples: `<td>`)
- HTML tag removed: tr: 7 (examples: `<tr>`)
- HTML tag removed: th: 6 (examples: `<th>`)
- HTML tag removed: a: 2 (examples: `<a>`)
- Trailing whitespace / double-space line break removed: 2 (examples: `'(++): '`; `'ries: '`)
- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://commons.wikimedia.org/wiki/File:Faust_dans_son_cabinet_(Faust_in_his_study)_(BM_1924,1014.7.3).jpg`)
- HTML tag removed: span: 1 (examples: `<span>`)
- HTML tag removed: table: 1 (examples: `<table>`)
- HTML tag removed: tbody: 1 (examples: `<tbody>`)
- Thematic break line removed (no text): 1 (examples: `---`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S14 Image-only items

None

## S15 new!!.md

### S15 Merged duplicates

None

### S15 Units not carried over (no text content)

- markdown separator line (no text content): 3 (units S15-L78-78, S15-L89-89, S15-L161-161)
  - examples: `---`; `---`; `---`

### S15 Removed or changed syntax (counts and examples)

- HTML tag removed: li: 76 (examples: `<li>`)
- HTML tag removed: p: 57 (examples: `<p>`)
- HTML tag removed: strong: 53 (examples: `<strong>`)
- HTML tag removed: code: 35 (examples: `<code>`)
- HTML tag removed: h2: 16 (examples: `<h2>`)
- HTML tag removed: h3: 15 (examples: `<h3>`)
- HTML tag removed: ul: 15 (examples: `<ul>`)
- HTML tag removed: a: 14 (examples: `<a>`)
- Lone closing square bracket escaped: 11 (examples: `[1, 2, 3, 4, 5]`; ` break page rendering. [6]`; ` string used above. [7, 8]`)
- Lone opening square bracket escaped: 11 (examples: `[1, 2, 3, 4, 5]`; `age rendering. [6]`; `ng used above. [7, 8]`)
- HTML entity decoded: 6 (examples: `&lt;`)
- Bare URL converted to an angle-bracket autolink: 4 (examples: `https://www.instagram.com/yourname/`; `https://www.reddit.com/user/yourname/saved/`; `https://x.com/i/bookmarks`)
- HTML tag removed: ol: 4 (examples: `<ol>`)
- Trailing whitespace / double-space line break removed: 4 (examples: `'b.txt '`; `'own)  '`; `'txt)  '`)
- Thematic break line removed (no text): 3 (examples: `---`)
- HTML tag removed: div: 1 (examples: `<div>`)
- HTML tag removed: main: 1 (examples: `<main>`)
- HTML tag removed: name: 1 (examples: `<name>`)
- Link lines converted to a Title | URL table: 1

### S15 Image-only items

None

## S16 notes.md

### S16 Merged duplicates

- S16-L7-11: exact duplicate of S16-L1-5

### S16 Units not carried over (no text content)

None

### S16 Removed or changed syntax (counts and examples)

- Plain multi-line block converted to a bullet list: 2

### S16 Image-only items

None

## S17 old-st-pauls.md

### S17 Merged duplicates

None

### S17 Units not carried over (no text content)

- markdown separator line (no text content): 12 (units S17-L121-121, S17-L123-123, S17-L148-148, S17-L158-158, S17-L616-616, S17-L634-634, S17-L648-648, S17-L664-664, S17-L695-695, S17-L713-713, S17-L727-727, S17-L1147-1147)
  - examples: `---`; `---`; `---`

### S17 Removed or changed syntax (counts and examples)

- Plain multi-line block converted to a bullet list: 58
- Trailing whitespace / double-space line break removed: 25 (examples: `'e1).  '`; `'e2).  '`; `'e3).  '`)
- Space-like character replaced by a space: NO-BREAK SPACE: 22 (examples: `'\xa0'`)
- Lone closing square bracket escaped: 21 (examples: `ave been borrowed[page 76] in the forego`; `[plate 34]`; `[page 77]`)
- Lone opening square bracket escaped: 21 (examples: `e been borrowed[page 76] in the foregoin`; `[plate 34]`; `[page 77]`)
- Bare URL converted to an angle-bracket autolink: 15 (examples: `https://www.gutenberg.org/files/16531/16531-h/images/0142-3cranes-320.jpg`; `https://www.gutenberg.org/files/16531/16531-h/16531-h.htm#plate34`; `https://www.gutenberg.org/files/16531/16531-h/images/titlepage.png`)
- Thematic break line removed (no text): 12 (examples: `---`)
- Stray * decoration removed: 3 (examples: `*** END OF THIS PROJECT GUTENBERG EBOOK OLD ST. PAUL'S CATHEDRAL ***`; `***** This file should be named 16531-h.htm or 16531-h.zip *****`; `*** START: FULL LICENSE ***`)
- Image syntax converted to a link: 2 (examples: `![OLD ST. PAUL'S IN FLAMES.](https://www.gutenberg.org/files/16531/16531-h/images/0171-bu)`; `![κανων](https://www.gutenberg.org/files/16531/16531-h/images/094-Gre)`)
- Link lines converted to a Title | URL table: 1
- Wikilink double brackets removed (text kept): 1 (examples: `[[OLD ST. PAUL'S CATHEDRAL By WILLIAM BENHAM]]`)

### S17 Image-only items

None

## S18 Page Token.md

### S18 Merged duplicates

None

### S18 Units not carried over (no text content)

None

### S18 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 4 (examples: `https://serpapi.com/searches/EC_YmnDE0Frz20_XdGN81mtWMxZPiDbnCMVdlCjTwrY/6abff44c22abf70705934a25.json`; `https://serpapi.com/searches/EC_YmnDE0Frz20_XdGN81mtWMxZPiDbnCMVdlCjTwrY/6abff44c22abf70705934a25.md`; `https://www.google.com/search?q=%22flickr+frontend%22&oq=%22flickr+frontend%22&hl=en&gl=us&sourceid=chrome&ie=UTF-8`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S18 Image-only items

None

## S19 Queen Bouddica.md

### S19 Merged duplicates

None

### S19 Units not carried over (no text content)

None

### S19 Removed or changed syntax (counts and examples)

- Plain multi-line block converted to a bullet list: 2
- Space-like character replaced by a space: EN SPACE: 2 (examples: `'\u2002'`)
- HTML tag removed: iframe: 1 (examples: `<iframe>`)
- Lone opening square bracket escaped: 1 (examples: `Panther party….[`)

### S19 Image-only items

None

## S20 r-Fantasy books.md

### S20 Merged duplicates

- S20-L44-44: exact duplicate of S20-L17-17
- S20-L52-52: exact duplicate of S20-L13-13
- S20-L54-54: exact duplicate of S20-L15-15
- S20-L118-118: exact duplicate of S20-L98-98
- S20-L120-120: exact duplicate of S20-L100-100
- S20-L148-148: exact duplicate of S20-L30-30
- S20-L150-150: exact duplicate of S20-L32-32
- S20-L158-158: exact duplicate of S20-L138-138
- S20-L160-160: exact duplicate of S20-L140-140
- S20-L225-225: exact duplicate of S20-L201-201
- S20-L227-227: exact duplicate of S20-L203-203
- S20-L231-231: exact duplicate of S20-L207-207
- S20-L456-456: exact duplicate of S20-L174-174
- S20-L462-462: exact duplicate of S20-L174-174

### S20 Units not carried over (no text content)

- markdown separator line (no text content): 13 (units S20-L261-261, S20-L277-277, S20-L287-287, S20-L295-295, S20-L303-303, S20-L311-311, S20-L334-334, S20-L342-342, S20-L380-380, S20-L407-407, S20-L420-420, S20-L471-471, S20-L521-521)
  - examples: `---`; `---`; `---`
- empty heading (marker only, no text): 12 (units S20-L263-263, S20-L279-279, S20-L289-289, S20-L297-297, S20-L305-305, S20-L313-313, S20-L336-336, S20-L344-344, S20-L382-382, S20-L409-409, S20-L422-422, S20-L473-473)
  - examples: `##`; `##`; `##`

### S20 Removed or changed syntax (counts and examples)

- Empty-text link converted to an autolink: 39 (examples: `[](https://www.reddit.com/user/FernandoFartti/)`; `[](https://www.reddit.com/user/Hiretsuna_Ketsuruki/)`; `[](https://www.reddit.com/user/pineappplethief/)`)
- Image syntax converted to a link: 13 (examples: `![u/AliceTheGamedev avatar](https://www.redditstatic.com/avatars/defaults/v2/avatar_defa)`; `![u/grownpatchwork avatar](https://www.redditstatic.com/avatars/defaults/v2/avatar_defa)`; `![u/Mournelithe avatar](https://www.redditstatic.com/avatars/defaults/v2/avatar_defa)`)
- Thematic break line removed (no text): 13 (examples: `---`)
- Empty heading marker removed: 12 (examples: `##`)
- Link list converted to a Title | URL table: 5
- Lone closing square bracket escaped: 4 (examples: `[deleted]`)
- Lone opening square bracket escaped: 4 (examples: `[deleted]`)
- Plain multi-line block converted to a bullet list: 2
- Trailing whitespace / double-space line break removed: 1 (examples: `'sue.  '`)

### S20 Image-only items

4 image(s) with no alt text kept as links and marked image-only, not captured.

## S21 research base.base

### S21 Merged duplicates

None

### S21 Units not carried over (no text content)

None

### S21 Removed or changed syntax (counts and examples)

None

### S21 Image-only items

None

## S22 Returns images from given page of booruproject.md

### S22 Merged duplicates

None

### S22 Units not carried over (no text content)

None

### S22 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 25 (examples: `https://booru.org/`; `https://danbooru.donmai.us/`; `https://derpibooru.org/`)
- Link lines converted to a Title | URL table: 1

### S22 Image-only items

None

## S23 Series Harvard Classics.md

### S23 Merged duplicates

- S23-L181-181: exact duplicate of S23-L177-177
- S23-L251-251: exact duplicate of S23-L237-237
- S23-L304-304: exact duplicate of S23-L299-299
- S23-L341-341: exact duplicate of S23-L193-193
- S23-L349-349: exact duplicate of S23-L203-203
- S23-L405-405: exact duplicate of S23-L395-395
- S23-L407-407: exact duplicate of S23-L397-397
- S23-L409-409: exact duplicate of S23-L399-399
- S23-L413-413: exact duplicate of S23-L395-395
- S23-L415-415: exact duplicate of S23-L397-397
- S23-L417-417: exact duplicate of S23-L399-399
- S23-L427-427: exact duplicate of S23-L327-327
- S23-L433-433: exact duplicate of S23-L333-333
- S23-L457-457: exact duplicate of S23-L451-451
- S23-L469-469: exact duplicate of S23-L465-465
- S23-L537-537: exact duplicate of S23-L185-185
- S23-L561-561: exact duplicate of S23-L257-257
- S23-L584-584: exact duplicate of S23-L321-321
- S23-L596-596: exact duplicate of S23-L185-185
- S23-L656-656: exact duplicate of S23-L257-257
- S23-L660-660: exact duplicate of S23-L237-237
- S23-L702-704: exact duplicate of S23-L573-575
- S23-L726-726: exact duplicate of S23-L299-299
- S23-L731-731: exact duplicate of S23-L299-299
- S23-L738-740: exact duplicate of S23-L709-711
- S23-L744-744: exact duplicate of S23-L321-321
- S23-L748-748: exact duplicate of S23-L588-588
- S23-L752-752: exact duplicate of S23-L185-185
- S23-L773-773: exact duplicate of S23-L229-229
- S23-L787-787: exact duplicate of S23-L257-257
- S23-L793-793: exact duplicate of S23-L628-628
- S23-L813-815: exact duplicate of S23-L573-575
- S23-L823-823: exact duplicate of S23-L299-299
- S23-L828-828: exact duplicate of S23-L299-299
- S23-L837-837: exact duplicate of S23-L321-321
- S23-L841-841: exact duplicate of S23-L588-588
- S23-L845-845: exact duplicate of S23-L185-185
- S23-L875-875: exact duplicate of S23-L555-555
- S23-L877-877: exact duplicate of S23-L557-557
- S23-L879-879: exact duplicate of S23-L789-789
- S23-L891-892: exact duplicate of S23-L570-571
- S23-L901-901: exact duplicate of S23-L321-321
- S23-L905-905: exact duplicate of S23-L588-588
- S23-L909-909: exact duplicate of S23-L185-185
- S23-L934-934: exact duplicate of S23-L622-622
- S23-L936-936: exact duplicate of S23-L624-624
- S23-L938-938: exact duplicate of S23-L628-628
- S23-L940-940: exact duplicate of S23-L630-630
- S23-L948-948: exact duplicate of S23-L634-634
- S23-L950-950: exact duplicate of S23-L644-644
- S23-L952-952: exact duplicate of S23-L646-646
- S23-L958-958: exact duplicate of S23-L257-257
- S23-L968-968: exact duplicate of S23-L674-674
- S23-L970-970: exact duplicate of S23-L676-676
- S23-L976-977: exact duplicate of S23-L685-686
- S23-L982-984: exact duplicate of S23-L688-690
- S23-L990-992: exact duplicate of S23-L709-711
- S23-L994-994: exact duplicate of S23-L299-299
- S23-L999-999: exact duplicate of S23-L299-299
- S23-L1004-1004: exact duplicate of S23-L299-299
- S23-L1006-1007: exact duplicate of S23-L728-729
- S23-L1013-1013: exact duplicate of S23-L321-321
- S23-L1017-1017: exact duplicate of S23-L588-588
- S23-L1021-1021: exact duplicate of S23-L185-185
- S23-L1029-1029: exact duplicate of S23-L193-193
- S23-L1056-1056: exact duplicate of S23-L942-942
- S23-L1058-1058: exact duplicate of S23-L944-944
- S23-L1062-1062: exact duplicate of S23-L789-789
- S23-L1072-1072: exact duplicate of S23-L257-257
- S23-L1089-1090: exact duplicate of S23-L979-980
- S23-L1103-1103: exact duplicate of S23-L299-299
- S23-L1108-1108: exact duplicate of S23-L299-299
- S23-L1113-1113: exact duplicate of S23-L299-299
- S23-L1122-1122: exact duplicate of S23-L321-321
- S23-L1126-1126: exact duplicate of S23-L588-588
- S23-L1130-1130: exact duplicate of S23-L185-185
- S23-L1157-1157: exact duplicate of S23-L229-229
- S23-L1169-1169: exact duplicate of S23-L634-634
- S23-L1171-1171: exact duplicate of S23-L865-865
- S23-L1173-1173: exact duplicate of S23-L867-867
- S23-L1175-1175: exact duplicate of S23-L219-219
- S23-L1177-1177: exact duplicate of S23-L221-221
- S23-L1181-1181: exact duplicate of S23-L257-257
- S23-L1202-1204: exact duplicate of S23-L688-690
- S23-L1206-1208: exact duplicate of S23-L883-885
- S23-L1210-1211: exact duplicate of S23-L271-272
- S23-L1213-1215: exact duplicate of S23-L709-711
- S23-L1217-1217: exact duplicate of S23-L299-299
- S23-L1222-1222: exact duplicate of S23-L299-299
- S23-L1227-1227: exact duplicate of S23-L299-299
- S23-L1236-1236: exact duplicate of S23-L321-321
- S23-L1240-1240: exact duplicate of S23-L588-588
- S23-L1244-1244: exact duplicate of S23-L185-185
- S23-L1295-1295: exact duplicate of S23-L219-219
- S23-L1324-1324: exact duplicate of S23-L321-321
- S23-L1328-1328: exact duplicate of S23-L588-588
- S23-L1332-1332: exact duplicate of S23-L185-185
- S23-L1356-1356: exact duplicate of S23-L219-219
- S23-L1360-1360: exact duplicate of S23-L229-229
- S23-L1366-1366: exact duplicate of S23-L551-551
- S23-L1368-1368: exact duplicate of S23-L553-553
- S23-L1376-1376: exact duplicate of S23-L789-789
- S23-L1388-1388: exact duplicate of S23-L257-257
- S23-L1392-1392: exact duplicate of S23-L797-797
- S23-L1403-1404: exact duplicate of S23-L567-568
- S23-L1417-1419: exact duplicate of S23-L709-711
- S23-L1429-1429: exact duplicate of S23-L321-321
- S23-L1433-1433: exact duplicate of S23-L588-588
- S23-L1445-1445: exact duplicate of S23-L1439-1439
- S23-L1447-1447: exact duplicate of S23-L1441-1441
- S23-L1463-1463: exact duplicate of S23-L1457-1457
- S23-L1473-1473: exact duplicate of S23-L1469-1469
- S23-L1485-1485: exact duplicate of S23-L1479-1479
- S23-L1487-1487: exact duplicate of S23-L1481-1481
- S23-L1507-1507: exact duplicate of S23-L1285-1285
- S23-L1513-1513: exact duplicate of S23-L1285-1285
- S23-L1515-1515: exact duplicate of S23-L1509-1509
- S23-L1525-1525: exact duplicate of S23-L1521-1521

### S23 Units not carried over (no text content)

- no content after cleaning: 2 (units S23-L439-439, S23-L1560-1560)
  - examples: `<svg aria-hidden="true" fill="currentColor" height="24px" vi`; `-`

### S23 Removed or changed syntax (counts and examples)

- Space-like character replaced by a space: NO-BREAK SPACE: 121 (examples: `'\xa0'`)
- Plain multi-line block converted to a bullet list: 97
- Image syntax converted to a link: 47 (examples: `![Go to Google home](/logos/doodles/2026/labor-day-2026-6753651837111014-lsg2x.pn)`; `![](https://ssl.gstatic.com/gb/images/ring/pr_32px_asknjuyerc.pn)`; `![](https://lh3.google.com/u/0/ogw/AF2bZyjOHcnnTHrKSi3Pb4equpP6L)`)
- Lone closing square bracket escaped: 40 (examples: ` Classic Shelf Of Fiction] eBook by Adam`; `assic%20works%20from%20w)]`; `sics/29223/bn_7023354016)]`)
- Lone opening square bracket escaped: 37 (examples: `181196?hl=en)- [[![Go to Google home](/l`; `Deer Classics) [51 Volumes + The Harvard`; ` 1909 and 1910 [0.6.5, 0.6.13]. ### Over`)
- Bare URL converted to an angle-bracket autolink: 17 (examples: `https://www.google.com/search?q=Series+Harvard+Classics&sourceid=chrome&ie=UTF-8&source=chrome.ctxt`; `https://en.wikipedia.org`; `https://www.delphiclassics.com`)
- HTML entity decoded: 11 (examples: `&amp;`)
- HTML tag removed: strong: 8 (examples: `<strong>`)
- HTML tag removed: td: 8 (examples: `<td>`)
- HTML tag removed: tr: 5 (examples: `<tr>`)
- Trailing whitespace / double-space line break removed: 4 (examples: `'.28s) '`; `'ation '`; `'an**? '`)
- HTML tag removed: th: 2 (examples: `<th>`)
- Bold marks around punctuation only removed: 1 (examples: `**?**`)
- Empty list item removed: 1 (examples: ` -`)
- Empty-text link converted to an autolink: 1 (examples: `[](https://accounts.google.com/SignOutOptions?hl=en&continue=ht)`)
- HTML tag removed: followup: 1 (examples: `<followup>`)
- HTML tag removed: iframe: 1 (examples: `<iframe>`)
- HTML tag removed: path: 1 (examples: `<path>`)
- HTML tag removed: svg: 1 (examples: `<svg>`)
- HTML tag removed: table: 1 (examples: `<table>`)
- HTML tag removed: tbody: 1 (examples: `<tbody>`)
- Orphan link syntax converted to an autolink: 1 (examples: `abor Day 2026")](https://www.google.com/webhp?hl=en&ict`)
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S23 Image-only items

29 image(s) with no alt text kept as links and marked image-only, not captured.

## S24 Squirrel Emojis.md

### S24 Merged duplicates

- S24-L24-24: exact duplicate of S24-L18-18
- S24-L30-30: exact duplicate of S24-L18-18
- S24-L42-42: exact duplicate of S24-L18-18
- S24-L60-60: exact duplicate of S24-L48-48
- S24-L66-66: exact duplicate of S24-L18-18
- S24-L78-78: exact duplicate of S24-L18-18

### S24 Units not carried over (no text content)

- markdown separator line (no text content): 1 (units S24-L80-80)
  - examples: `---`

### S24 Removed or changed syntax (counts and examples)

- Image syntax converted to a link: 12 (examples: `![squirrelpumpkin](https://cdn3.emoji.gg/emojis/722856-squirrelpumpkin.gif)`; `![squirrelpumpkin Emoji](https://cdn3.emoji.gg/emojis/722856-squirrelpumpkin.gif)`; `![Squirrel Emoji](https://cdn3.emoji.gg/emojis/169575-squirrel.png)`)
- HTML entity decoded: 4 (examples: `&Theta;`)
- Bare URL converted to an angle-bracket autolink: 1 (examples: `https://emoji.gg/emojis/squirrel`)
- Thematic break line removed (no text): 1 (examples: `---`)

### S24 Image-only items

None

## S25 summarizer.md

### S25 Merged duplicates

None

### S25 Units not carried over (no text content)

None

### S25 Removed or changed syntax (counts and examples)

- Lone closing square bracket escaped: 20 (examples: `r%2C+Thomas%2C+1807-1874)]`; `ream-i-know-jm-dent-1909)]`; `commonobjectsofs00wood_2)]`)
- Wikilink double brackets removed (text kept): 1 (examples: `[[collections/llm/exports|exports]]`)

### S25 Image-only items

None

## S26 the origin of going to church.md

### S26 Merged duplicates

None

### S26 Units not carried over (no text content)

None

### S26 Removed or changed syntax (counts and examples)

- Bare URL converted to an angle-bracket autolink: 3 (examples: `https://pinterest.com/pin/create/button/?desc=`; `https://www.tiktok.com/@sineatahh/video/7698404699434716447`; `https://lf16-tiktok-web.ttwstatic.com/obj/tiktok-web-common-sg/mtact/static/images/share_img.png`)
- Link lines converted to a Title | URL table: 1
- Plain multi-line block converted to a bullet list: 1
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S26 Image-only items

None

## S27 Third-party Licenses.md

### S27 Merged duplicates

None

### S27 Units not carried over (no text content)

None

### S27 Removed or changed syntax (counts and examples)

- Space-like character replaced by a space: NO-BREAK SPACE: 3 (examples: `'\xa0'`)
- Link list converted to a Title | URL table: 1
- YAML frontmatter delimiters removed; fields shown as a bullet list: 1

### S27 Image-only items

None

## Full text of excluded units

- S01-L20-20: `---`
- S01-L29-29: `---`
- S01-L39-39: `---`
- S01-L48-48: `---`
- S01-L57-57: `---`
- S01-L66-66: `---`
- S01-L75-75: `---`
- S01-L85-85: `---`
- S01-L94-94: `---`
- S01-L103-103: `---`
- S01-L112-112: `---`
- S01-L118-118: `##`
- S01-L193-193: `##`
- S01-L218-218: `---`
- S01-L222-222: `---`
- S01-L226-226: `---`
- S01-L230-230: `---`
- S01-L234-234: `---`
- S01-L238-238: `---`
- S01-L294-294: `---`
- S02-L36-36: `---`
- S02-L64-64: `---`
- S02-L66-66: `---`
- S02-L108-108: `---`
- S02-L110-110: `---`
- S03-L266-266: `---`
- S04-L9-9: `---`
- S04-L34-34: `---`
- S04-L56-56: `---`
- S04-L88-88: `---`
- S04-L94-94: `---`
- S05-L73-73: `* * *`
- S05-L175-175: `---`
- S08-L120-120: `<svg aria-hidden="true" fill="currentColor" height="24px" viewBox="0 -960 960 960" width="24px">\<path d="M480-80q-75 0-140.5-28.5t-114-77q-48.5-48.5-77-114T120-440h80q0 117 81.5 198.5T480-160q117 0 1`
- S08-L383-383: `---`
- S10-L108-108: `---`
- S14-L38-38: `---`
- S15-L78-78: `---`
- S15-L89-89: `---`
- S15-L161-161: `---`
- S17-L121-121: `---`
- S17-L123-123: `---`
- S17-L148-148: `---`
- S17-L158-158: `---`
- S17-L616-616: `---`
- S17-L634-634: `---`
- S17-L648-648: `---`
- S17-L664-664: `---`
- S17-L695-695: `---`
- S17-L713-713: `---`
- S17-L727-727: `---`
- S17-L1147-1147: `---`
- S20-L261-261: `---`
- S20-L263-263: `##`
- S20-L277-277: `---`
- S20-L279-279: `##`
- S20-L287-287: `---`
- S20-L289-289: `##`
- S20-L295-295: `---`
- S20-L297-297: `##`
- S20-L303-303: `---`
- S20-L305-305: `##`
- S20-L311-311: `---`
- S20-L313-313: `##`
- S20-L334-334: `---`
- S20-L336-336: `##`
- S20-L342-342: `---`
- S20-L344-344: `##`
- S20-L380-380: `---`
- S20-L382-382: `##`
- S20-L407-407: `---`
- S20-L409-409: `##`
- S20-L420-420: `---`
- S20-L422-422: `##`
- S20-L471-471: `---`
- S20-L473-473: `##`
- S20-L521-521: `---`
- S23-L439-439: `<svg aria-hidden="true" fill="currentColor" height="24px" viewBox="0 -960 960 960" width="24px"><path d="M480-80q-75 0-140.5-28.5t-114-77q-48.5-48.5-77-114T120-440h80q0 117 81.5 198.5T480-160q117 0 19`
- S23-L1560-1560: `-`
- S24-L80-80: `---`
