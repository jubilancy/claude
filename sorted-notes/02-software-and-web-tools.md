---
title: "Software and Web Tools"
description: "Tool notes: chat clients, newsletter services, bookmarking alternatives, headless browsers, Puter.js, user agent strings, OpenDesktop and software licenses."
concepts:
  - "software tools"
  - "browser automation"
  - "user agents"
  - "bookmarking"
  - "open source licenses"
  - "hosting"
tags:
  - tools
  - software
  - web
  - reference
sources:
  - "Dec.6.25.md"
  - "Libre Cloud Services - OpenDesktop.org.md"
  - "new!!.md"
  - "summarizer.md"
  - "Third-party Licenses.md"
---

# Software and Web Tools

## Contents

1. [1. Pidgin and Adium on macOS](#1-pidgin-and-adium-on-macos)
    1. [1.1 From: Dec.6.25.md](#11-from-dec625md)
2. [2. Email newsletter services](#2-email-newsletter-services)
    1. [2.1 From: Dec.6.25.md](#21-from-dec625md)
3. [3. Pinboard alternatives and Pastebot](#3-pinboard-alternatives-and-pastebot)
    1. [3.1 From: Dec.6.25.md](#31-from-dec625md)
4. [4. Headless browsers, test automation and Puter.js](#4-headless-browsers-test-automation-and-puterjs)
    1. [4.1 From: summarizer.md](#41-from-summarizermd)
5. [5. User agent strings and random notes](#5-user-agent-strings-and-random-notes)
    1. [5.1 From: new!!.md](#51-from-newmd)
6. [6. OpenDesktop and Opencode](#6-opendesktop-and-opencode)
    1. [6.1 From: Libre Cloud Services - OpenDesktop.org.md](#61-from-libre-cloud-services---opendesktoporgmd)
7. [7. Spotify third-party licenses](#7-spotify-third-party-licenses)
    1. [7.1 From: Third-party Licenses.md](#71-from-third-party-licensesmd)
8. [8. See also](#8-see-also)

## 1. Pidgin and Adium on macOS

### 1.1 From: Dec.6.25.md

###### macOS

For a native macOS experience we recommend [Adium](https://adium.im/), which uses libpurple (the core of Pidgin) for much of its protocol support.

If you’re sure you want to use Pidgin on macOS, you may find the packages provided through [Homebrew](https://brew.sh/), [pkgin](https://pkgsrc.joyent.com/),[Fink](https://finkproject.org/download/) or [Macports](https://www.macports.org/install.php) more convenient than compiling from source. Please note, _we do not provide support for issues related to installing Homebrew, pkgin, Fink, Macports, or their packages of Pidgin_. Contact those projects directly with questions or concerns.

If you’re sure you want to use Pidgin on macOS and you don’t want to use Homebrew, Fink or Macports, you can [download the Pidgin source](https://pidgin.im/install/#source) and compile.

## 2. Email newsletter services

### 2.1 From: Dec.6.25.md

- Mailchimp
- FloDesk
- Substack
- Drip
- Keap (formerly known as Infusionsoft)
- ActiveCampaign
- AWeber
- MailerLite
- GetResponse
- Beehiiv

## 3. Pinboard alternatives and Pastebot

### 3.1 From: Dec.6.25.md

##### Alternatives

Don't like Pinboard? Try one of my fine competitors:

- [Diigo](http://www.diigo.com/) — Freemium bookmarking site. Free tier shows ads.
- [Historio.us](http://historio.us/) — Freemium site with emphasis on search.
- [Raindrop.io](http://raindrop.io/) — a one-developer competitor!
- [Pearltrees](http://pearltrees.com/) — Flash-intensive bookmarking and visualization tool.
- [BibSonomy](http://www.bibsonomy.org/) — University-sponsored bookmarking and publication tracking site.
- [Wallabag](https://wallabag.org/) — I think it's a bookmarking site?
- [Pocket](https://getpocket.com/) — bookmarking site bought by Mozilla and now baked into Firefox.
- [Tefter](https://www.tefter.io/) — not even sure what this one is, but costs 12x what Pinboard does.

###### Pastebot

Command Copy & Paste

## 4. Headless browsers, test automation and Puter.js

### 4.1 From: summarizer.md

Here's a summary of the software items mentioned, grouped by category:

##### Headless Browser APIs

- Splash, Zombie.js, SimpleBrowser, DotNetBrowser

##### Browser Automation (Unified Interface)

- Selenium WebDriver, Playwright, Puppeteer

##### Test Automation

- Capybara, Jasmine, Cypress, QF-Test

##### Browser API Alternatives

- Deno (built-in browser APIs), jsdom (for Node.js), HtmlUnit (Java-based, uses Rhino engine for JS/Ajax)

Here's a summary of the key tools, concepts, and items mentioned in the conversation:

##### Primary Tool

**Puter.js** — A JavaScript library (`https://js.puter.com/v2/`) that gives developers free access to AI models using a "User-Pays" model, requiring no API keys or server-side setup.

##### AI Models Available via Puter.js (as of April 2026)

- **GPT-5.5 / GPT-5.5 Pro** — Flagship, complex reasoning

- **GPT-5.4 Nano/Mini** — Fast, lightweight daily-use models

- **GPT-5.3-Codex** — Optimized for coding and terminal commands

- **GPT Image** — Image generation

##### Other Tools & Platforms Referenced

- **Quartz** — A static site generator (quartz.jzhao.xyz) used as the deployment target

- **Obsidian** — Note-taking app mentioned in a usage example

- **OpenAI API** — The traditional paid alternative being replaced here

##### Key Concepts

- **User-Pays Model** — Developers pay $0; each user covers their own costs via their Puter account

- **Free Tier Limits** — ~200 requests/day (1 question = 1 request, regardless of length)

- **Tokens vs. Requests** — Puter counts by requests, not token length, unlike the official OpenAI API

##### Puter.js API Methods Mentioned

- `puter.ai.chat()` — Send text prompts to GPT models

- `puter.ai.txt2img()` — Generate images

## 5. User agent strings and random notes

### 5.1 From: new!!.md

#### random. notes

3da35dc2abb99d8ef3fdb1dec3166c39189f7cb29974a225e7bbca04c1b2c6e0 composer.phar

The Social Archiver Chrome Extension is for fast capture while you browse on desktop. With a Social Archiver account it shares one archive library with the Obsidian plugin, mobile app, and web app — and without an account it can still clip posts locally to Obsidian, a Markdown file, or your clipboard.

Install

Install [Social Archiver from the Chrome Web Store](https://chromewebstore.google.com/detail/social-archiver/gifddgdekeffpnadpdcgjaehmlblomaf)

Open the extension popup

Sign in with your email address — or skip sign-in and use [local clipping](#clip-without-an-account-local-save) only

Use the same email as your Obsidian plugin or mobile app if you want all clients to share one archive library

Signing in unlocks the server-side features: cloud archiving, podcasts, subscriptions, mobile sync, and share links. Local clipping works either way.

Archive Supported URLs

Use Archive Current Page when the current tab is a supported social post or source page. The extension submits the URL to Social Archiver, tracks the background job, and shows the result in the popup history.

You can also archive faster with:

Keyboard shortcut: Ctrl+Shift+S (Cmd+Shift+S on Mac)

Right-click menu: Archive to Social Archiver on the current page or a link

Active icon state: the extension icon changes when the current page is recognized as archivable

Web Clipping

For regular web pages, use Clip instead of Archive. Clipping extracts the readable page content, opens a side panel preview, and lets you edit the title, Markdown body, and personal note before saving.

Use clipping for articles, blog posts, documentation, and other web pages that are not handled by a platform-specific archiver.

Clip Destinations

A clip can go to different places. The Default clip destination in extension Settings controls where the main Clip button sends, and several flows let you pick per-clip:

Obsidian plugin — sends the clip straight to the Social Archiver Obsidian plugin through an obsidian:// link. The plugin turns it into a Markdown note and downloads media into your vault. Requires the Social Archiver plugin 4.0.0 or later.

Desktop app — hands the clip to the Social Archiver [desktop app](https://docs.social-archive.org/en/guide/desktop-app) over a socialarchiver-desktop:// deep link. The app saves it to your library — into your local library when signed out, or your account when signed in. The desktop app must be installed.

Account (cloud) — uploads to your Social Archiver account so the archive appears across the web app, mobile, and synced Obsidian. Requires sign-in.

Local file or clipboard — Download ZIP, Copy Markdown, or Copy HTML, with no account.

Sending a clip straight to the Obsidian plugin or the desktop app works without a Social Archiver account.

Clip Without an Account (Local Save)

Since extension 1.6 you can save posts locally without signing in. When the current tab is a supported post page, the logged-out popup shows a Local destinations card with these actions:

Clip to Obsidian — sends the extracted post to the Social Archiver Obsidian plugin through an obsidian:// link. The plugin converts it into a Markdown note and downloads media into your vault. Requires the Social Archiver plugin 4.0.0 or later.

Download ZIP — downloads a bundle containing the post as Markdown and HTML, media files when they can be downloaded, an import manifest, and the raw post data. Use this if you don't use Obsidian.

Copy Markdown — copies the post as Markdown to paste into any notes app or editor.

Copy HTML — copies richer formatting where the browser supports it.

Local saves run entirely in your browser:

No account or sign-in is required

Nothing is sent to Social Archiver servers

They never consume archive quota or credits

Extraction uses your existing browser session on the platform page, so posts that are visible to you — including login-walled Facebook posts — can be clipped, often with comments included.

Supported pages: Instagram posts, reels, and stories; Facebook post permalinks; X posts; Threads posts; Reddit posts; YouTube videos; TikTok videos; LinkedIn posts; Substack Notes; Bluesky posts; Mastodon posts; Naver Blog; Naver Cafe; Kakao Brunch; and any ordinary web article through the generic web clip.

Good to know:

TikTok videos and Instagram stories save the actual media file, so the Obsidian destination needs a vault folder selected in extension Settings first.

When you are signed in, the same Clip to Obsidian action is available from the archive button dropdown. Local clips stay local — they don't create server archives.

Platform Clipping Tips

Several platforms only allow clipping from a single-post page, not from the feed.

Facebook: open the post page first

Clipping works on a post's own permalink page, not on the news feed or a profile timeline. To clip a post you see in the feed:

Click the post's timestamp — the "3h" or date text under the author name. This opens the post's own page, such as facebook.com//posts/..., /reel/..., /photo?fbid=..., or /watch?v=....

Open the extension popup there and use Clip to Obsidian (or Archive when signed in).

The extension reads the post with your logged-in Facebook session, so posts behind a login wall are included, along with comments, link cards, and shared/quoted posts. For reels that deliver audio and video as separate streams, the [Local Media Helper](https://docs.social-archive.org/en/guide/local-media-helper) merges them into one file; without the helper the clip falls back to a video-only file.

Instagram: open the post page first

Open the individual post page so the URL looks like instagram.com/p// or instagram.com/reel//. From the feed, click the post's timestamp; from a profile grid, click the post itself. Then clip from the popup.

Stories and highlights can be clipped from the story viewer. Like TikTok, story clips save the media file directly, so a vault folder must be set in extension Settings. Stories whose audio and video arrive as separate streams cannot be merged locally — use Archive for those.

LinkedIn: copy the post link, open it in a new tab

LinkedIn feed pages cannot be clipped in place. Get the post's own URL first:

On the post, open the ⋯ menu (or Share) and choose Copy link to post.

Open the copied link in a new tab. The URL looks like linkedin.com/posts/... or linkedin.com/feed/update/urn:li:activity:....

Open the extension popup on that tab, then clip or archive.

LinkedIn articles (Pulse) and lnkd.in short links are not supported by the post clipper; articles can still be saved with the generic web Clip.

TikTok: vault folder, and the Local Media Helper for some videos

TikTok clips capture the video that is visible or playing in the current tab and save the video file straight into your vault:

A vault folder must be selected in extension Settings first.

Many TikTok videos deliver audio and video as separate streams. Those require the [Local Media Helper](https://docs.social-archive.org/en/guide/local-media-helper) to merge them into a single MP4 — if it is not set up, the popup asks you to enable it.

On feed pages with several loaded videos, the popup shows a candidate list so you can pick the right one. Opening the video's own page (tiktok.com/@user/video/...) is the most reliable.

YouTube

YouTube video pages clip with structured video metadata, and extension 1.6.2 and later also include the transcript/captions when available.

Instagram Saved Posts Import

When you open the popup on instagram.com, the extension can show Import Instagram Saved Posts. This is marked beta because it relies on Instagram's browser session and private web API behavior.

You choose where the import should go before starting:

Desktop / Obsidian: the extension downloads ZIP parts to your computer. Each ZIP contains the selected saved posts, media files, and an import manifest. Import those ZIP files from the Obsidian plugin to create Markdown files and attachments in your vault while also registering the archives in your Social Archiver account.

Web: the extension uploads the selected saved posts directly to your Social Archiver account. It does not create ZIP files. The web app can show the imported posts after processing, and Obsidian can pick them up later through sync.

Key behavior:

You choose which saved collections to import

Selected media is downloaded locally in the browser first before it is packaged into ZIP files or uploaded to Social Archiver

Imports can be paused and resumed

Instagram may require account verification or change the web API without notice

Instagram My Posts Import

Chrome Extension 1.4.9 adds My Posts import for Instagram. It is designed for backing up your own Instagram posts, but the current version works from the Instagram profile grid that is open in Chrome. It imports posts and reels that are visible to your logged-in Instagram session, including older posts or posts that are restricted for logged-out viewers.

How to use it:

Open Chrome and sign in to instagram.com

Open the Instagram profile grid you want to import from, for example your own profile at <https://www.instagram.com/yourname/>

Open the Social Archiver extension popup

Choose Instagram Import → My Posts

Select how many recent posts to import, from 50 up to 5,000

Start the import

Important details:

My Posts import uses Web upload mode only. It uploads directly to your Social Archiver account and does not create ZIP files.

The extension uses your existing logged-in Instagram browser session, so it can access posts that are visible in your browser but not visible to logged-out visitors.

The import scrolls the current profile grid to discover post and reel links, then rehydrates each post before archiving so captions, media, comments, and author details can be preserved when available.

Duplicates are skipped automatically. You can import a smaller range first, then run a larger range later.

Large imports may take a while and can be paused or resumed from the extension popup.

For very large profiles, importing 1,000-2,000 posts at a time is usually more reliable than starting with the full 5,000 range.

My Posts import is optimized for backing up your own profile. Use it only for profiles and content you have permission to archive; it is not designed as a general-purpose crawler.

For individual post and story capture, optional mobile and desktop sessions, subscriptions, Immich export, privacy, and troubleshooting, see the [Instagram guide](https://docs.social-archive.org/en/guide/instagram).

Reddit Saved Posts Import

When you open the popup on a Reddit saved page such as reddit.com/user/yourname/saved, the extension can show Import Reddit Saved Posts. This is also marked beta because it depends on Reddit's saved listing pages and the current browser session.

Choose where the import should go: Upload to my account, Archive to Obsidian vault, or Desktop app. Account uploads sync through Social Archiver; the Obsidian and desktop destinations use a local handoff and do not create an account archive.

Key behavior:

The extension discovers your saved Reddit posts and saved comments from your logged-in Reddit session

Supported media is downloaded in the browser and uploaded through Social Archiver's media pipeline

Saved comments are preserved as Reddit comment archives; saved posts can include available thread comments

The import can be paused, resumed, retried, or discarded from the popup

Unsupported Reddit item types or unavailable media may be skipped or imported with warnings

For single-post capture, optional signed-in sessions, privacy, and troubleshooting, see the [Reddit guide](https://docs.social-archive.org/en/guide/reddit).

X (Twitter) Bookmarks Import

When you open the popup on x.com/i/bookmarks (or twitter.com/i/bookmarks), the extension can show Import X Bookmarks. This is marked beta because it depends on X's bookmarks GraphQL endpoint and the current browser session.

Choose Upload to my account, Archive to Obsidian vault, or Desktop app. Only the account destination creates Social Archiver account archives; the other destinations hand the import to the selected local client.

Key behavior:

Discovery captures the bookmarks GraphQL response that X already issues for the current page; the extension does not call the API on your behalf

Link preview cards (image + destination URL), quote tweets, X articles, photos, and supported videos are preserved

Discovery and archive can be paused, resumed, retried, or discarded from the popup

The main popup shows a "ready / in progress / paused" banner so you can jump back without re-opening the bookmarks page

If discovery stops with a cursor still present, more bookmarks may be available — finish the current import first, then run Discovery again

The X user handle is not always extractable in v1, so the UI may show unknown rather than an account name

For single-post capture, optional signed-in sessions, subscriptions, privacy, and troubleshooting, see the [X (Twitter) guide](https://docs.social-archive.org/en/guide/x).

Archive Quota for Imports

Imports count against your monthly successful archive quota only when you choose an account destination, including Instagram's Web destination and Upload to my account for Reddit or X. Archive to Obsidian vault and Desktop app are local destinations and do not use account quota.

Duplicates and skipped items do not create new archives and do not consume archive quota. Premium monthly, annual, and lifetime plans remove monthly archive limits while the entitlement is active.

Browser Session Privacy

Instagram, Reddit, and X saved-post / bookmarks imports use the browser session that already exists in your local Chrome profile. Instagram My Posts import also uses that same local Instagram session. The extension reads the relevant saved-post listing, profile grid links, or bookmarks response and (for Instagram and Reddit) downloads media from the platform in the browser, using the cookies and session state that Chrome already has for instagram.com, reddit.com, or x.com.

Social Archiver servers do not receive your Instagram, Reddit, or X password, cookies, session tokens, CSRF tokens, or captured platform request headers. For direct account uploads, the server receives the archive payload, selected media files, import job metadata, and your Social Archiver authentication token so it can create archives in your account. For an X bookmarks account upload, only the response body of X's own Bookmarks GraphQL request is forwarded; X media is downloaded server-side from URLs in that response. Local Obsidian and desktop destinations do not send the import payload through Social Archiver account sync.

Settings

The extension options page includes:

Desktop notifications

In-page toast messages

Auto-create share link when archiving

Default clip destination (Obsidian plugin, desktop app, or account)

Obsidian vault folder for clip media handoff (required for TikTok and Instagram story clips)

Show or hide Instagram import features

Immich upload and Local Media Helper pairing

Export debug log for support

For merging split audio/video streams (TikTok and Facebook reel clips, high-quality Immich uploads), see [Local Media Helper](https://docs.social-archive.org/en/guide/local-media-helper).

Sync With Obsidian and Mobile

When you choose an account destination, archives created from Chrome can appear in:

The web app immediately after processing

The mobile app through Auto Sync

Your Obsidian vault when the plugin is connected and Obsidian is open, or after you run Sync Existing Archives

Local Obsidian and desktop destinations bypass account sync and are delivered directly to that client. Keep the selected client open and connected during the handoff.

Troubleshooting

This page cannot be archived

Browser-internal pages such as chrome://, chrome-extension://, about:, and similar URLs cannot be archived or clipped. Open a normal http or https page.

Generic page opens Clip mode

This is expected. Platform-specific URLs use Archive; ordinary web pages use Clip so you can review and edit the extracted Markdown before saving.

Facebook or Instagram post cannot be read from the page

Clipping needs the single-post page, not the feed. Click the post's timestamp to open its permalink, reload the page if it was reused from a previous post, then clip again.

TikTok clip asks for the Local Media Helper

That video delivers audio and video as separate streams, which the extension cannot merge on its own. Install and enable the [Local Media Helper](https://docs.social-archive.org/en/guide/local-media-helper), then retry. Also make sure a vault folder is selected in extension Settings — TikTok clips write the video file directly into your vault.

LinkedIn post does not clip from the feed

Use ⋯ → Copy link to post on the post, open the copied URL in a new tab, and clip from there. Pulse articles and lnkd.in short links are not supported by the post clipper.

Instagram import is unavailable

Open an Instagram tab first, make sure you are logged into Instagram in the browser, and confirm the import feature is enabled in the extension options.

Instagram My Posts finds no posts

Open the Instagram profile grid you want to import from before starting the import. If the profile page has not loaded enough items yet, scroll the page once, reopen the extension popup, and try again. For large ranges, keep the Instagram tab open while discovery is running.

If a 5,000-post discovery run stops, keep the profile tab open and retry with 1,000-2,000 posts at a time.

Instagram import says "session expired" but you are still logged in

After a large import (for example a few thousand posts), Instagram may temporarily limit its internal API for your account while normal browsing keeps working. That is why you can still scroll Instagram even though the import stops. Extension 1.6.0 and later detect this and show an "Instagram is temporarily limiting requests" message; older versions reported it as a session expiry.

What to do:

Wait. The limit usually clears within several hours to a day. Normal Instagram browsing during that time is fine.

Do not sign out and back in, and do not restart the browser — the limit is applied on Instagram's side to your account, so neither helps. Re-logging in right after heavy use can even trigger Instagram's account verification challenge.

When you try again, import in smaller batches and leave a few hours between sessions.

Reddit import is unavailable

Open your Reddit saved page first, for example <https://www.reddit.com/user/yourname/saved/>, and make sure you are logged into Reddit in the browser.

X Bookmarks import is unavailable or captures nothing

Open <https://x.com/i/bookmarks> first and make sure you are logged into X in the browser. If discovery completes with zero captures, X's service worker may have served a cached response — retrying after a moment or reloading the bookmarks tab usually resolves it. Accounts that recently performed many bookmark mutations may also see paginated results temporarily throttled; a naturally accumulated account works best.

Next Steps

[Web App](https://docs.social-archive.org/en/guide/web-app)

[Mobile App](https://docs.social-archive.org/en/guide/mobile-app)

[Sharing](https://docs.social-archive.org/en/guide/sharing)

[Local Media Helper](https://docs.social-archive.org/en/guide/local-media-helper)

#### People also search for

#### links

| Title | URL |
|---|---|
|  | <https://huggingface.co/nilc-nlp/glove-50d/resolve/main/vocab.txt> |
|  | <https://github.com/domchristie/to-markdown> |
|  | <https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/raft-large-directories.txt> |
|  | <https://github.com/databaaz/url-industry-classifier/blob/master/EDA.ipynb> |
|  | <http://www.cs.cmu.edu/~hyunahs/tol/DATA/NellData/nell_terms.txt> |

An excellent, lightweight user agent string for a custom browser profile or scraping script is a clean, modern Chrome on Windows identifier. It provides the highest compatibility across almost all websites.

```text
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36
```

##### Specialized Alternatives

Depending on your specific goals for the custom setting, you can use one of these targeted options:

- Safari on macOS (Great for a native Mac profile):

```text
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15
```

- Mobile Chrome (Forces websites to serve lightweight mobile layouts):

```text
Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36
```

- Googlebot (Occasionally helps bypass restrictive soft paywalls or heavy anti-bot walls, though some sites cross-verify IP addresses):

```text
Mozilla/5.0 (compatible; Googlebot/2.1; +http://google.com)
```

\[1, 2, 3, 4, 5\]

##### Configuration Tips

- Avoid Typos: Ensure there are no accidental trailing spaces or missing characters when pasting the string into your website settings. A malformed user agent can completely break page rendering. \[6\]
- User Agent Client Hints (UA-CH): Modern browsers often send secondary headers (`Sec-CH-UA`). If the extension or software tool you are using lets you customize those as well, make sure the version numbers match the primary string used above. \[7, 8\]

\[1\] [https://github.com](https://github.com/tauri-apps/tauri/issues/4284)

\[2\] [https://www.howtogeek.com](https://www.howtogeek.com/211961/how-to-change-safaris-user-agent-in-os-x/)

\[3\] [https://www.testmuai.com](https://www.testmuai.com/latest-version/safari-user-agents/)

\[4\] [https://soax.com](https://soax.com/glossary/user-agent)

\[5\] [https://iproyal.com](https://iproyal.com/blog/user-agents-for-scraping/)

\[6\] [https://customgpt.ai](https://customgpt.ai/connect-wix-to-chatbot/)

\[7\] [https://roundproxies.com](https://roundproxies.com/blog/fingerprint-suite/)

\[8\] [https://http.dev](https://http.dev/client-hints)

## 6. OpenDesktop and Opencode

### 6.1 From: Libre Cloud Services - OpenDesktop.org.md

- Admin message: Repositories are limited in size now to 1GB. If your repository exceeds this size, it will be automatically deleted.

- Admin message: If you'd like access to our CI/CD builders, please create an issue [here](https://www.opencode.net/gitlab/issues/-/issues/new).

###### Opencode FAQ

- Opencode.net is a 100% libre git webservice, which uses Gitlab as base.
- It offers integrated CI, online editior, and many more and can be accessed with the same openID of opendesktop.org.

Any project on Opencode.net can also be connected to any product on Opendesktop.org, so that product can use readme.md, the ticket system etc. This saves from duplication work, like keeping the description updated in the code repository and product description.

There are also many free git clients for developers available, for a list look here:

[https://forum.opendesktop.org/t/git-client-list/7104](https://forum.opendesktop.org/t/git-client-list/7104)

```html
<!-- Copy the meta tag below and paste it into your site home page.  
It should go in the <head> section, before the first <body> section.
!-->

<meta name="ocs-site-verification" content="579c2fd1c6fb677d8be7a98c02a500ae" />
```

#### links

| Title | URL |
|---|---|
|  | <https://my.opendesktop.org/apps/files/> |
|  | <https://my.opendesktop.org/apps/calendar/> |
|  | <https://my.opendesktop.org/apps/contacts/> |
|  | <https://forum.opendesktop.org/u/jubilancy/messages> |
|  | <https://my.opendesktop.org/apps/music/> |
|  | <https://my.opendesktop.org/apps/maps/> |
|  | <https://social.opendesktop.org/> |
|  | <https://www.opendesktop.org/> |
|  | <https://www.opendesktop.org/community> |
|  | <https://forum.opendesktop.org/> |
|  | <https://blog.opendesktop.org/> |
|  | <https://www.opendesktop.org/about> |
|  | <https://chat.opendesktop.org/> |
|  | <https://www.opendesktop.org/u/jubilancy/products> |
|  | <https://www.opencode.net/dashboard/projects> |
|  | <https://www.opendesktop.org/u/jubilancy/issues> |
|  | <https://www.opendesktop.org/product/add> |
|  | <https://www.opendesktop.org/my-favourites> |
|  | <https://www.opendesktop.org/settings/> |
|  | <https://www.opendesktop.org/settings/profile> |
|  | <https://www.opendesktop.org/logout/redirect/NlI3.MBlTLC7TzcHqcKqaUtETUM3ZGhjbkhDZO8XgAQIFV43CBHFjeJgzDA~/> |
|  | <https://www.opencode.net/jubilancy> |
|  | <https://forum.opendesktop.org/u/jubilancy> |
|  | <https://www.pling.com/community> |
|  | <https://www.opendesktop.org/terms> |
|  | <https://www.opendesktop.org/privacy> |
|  | <https://www.opendesktop.org/contact> |
|  | <https://www.opendesktop.org/imprint> |
|  | <https://www.opendesktop.org/u/jubilancy/#> |
|  | <https://chat.opendesktop.org/#/room/#opendesktop:chat.opendesktop.org> |
|  | <https://www.opendesktop.org/logout/redirect/lrfy8y0.77PmFO02xhvQ4ktETUM3ZGhjbkhDZO8XgAQIFV43CBHFjeITvVzxShDWggecRVfHUKgKRFVG/> |
|  | <https://www.opendesktop.org/u/jubilancy/> |
|  | <https://opencode.net/jubilancy> |
|  | <https://www.opendesktop.org/u/jubilancy/downloadhistory> |
|  | <https://www.opendesktop.org/u/jubilancy/likes> |
|  | <https://www.opendesktop.org/u/jubilancy/activities> |
|  | <https://www.opendesktop.org/u/jubilancy/collections> |
|  | <https://www.opendesktop.org/collection/add> |
|  | <https://www.opendesktop.org/u/jubilancy/products#> |
|  | <https://addons.videolan.org/u/jubilancy> |
|  | <https://forum.opendesktop.org/t/cant-login-or-push-code-to-opencode-net/21328/3> |

## 7. Spotify third-party licenses

### 7.1 From: Third-party Licenses.md

- tags:
  - explore

#### spotify

Several fantastic pieces of free and open-source software have really helped get Spotify to where it is today. A few require that we include their license agreements within our product. Consider it done. As we enjoy giving credit where it's due, we included the entire list below. This means you can not only see which software we've been using, but the terms of the licenses too. A big thanks from all of us at Spotify to the smart people behind the fantastic programs listed. Rock on!

You can download the source code to the Chromium Embedded Framework used by Spotify here: [https://www.spotify.com/opensource/](https://www.spotify.com/opensource/)

Third-party software that is part of the Desktop client:

| Title | URL |
|---|---|
| any_invocable | <https://xpui.app.spotify.com/licenses-loader.html#dfee2> |
| asio | <https://xpui.app.spotify.com/licenses-loader.html#81734> |
| boost | <https://xpui.app.spotify.com/licenses-loader.html#f7d80> |
| double-conversion | <https://xpui.app.spotify.com/licenses-loader.html#50e05> |
| expected | <https://xpui.app.spotify.com/licenses-loader.html#5dcbd> |
| flac | <https://xpui.app.spotify.com/licenses-loader.html#b7b7d> |
| hacl-star | <https://xpui.app.spotify.com/licenses-loader.html#6322c> |
| hde64 | <https://xpui.app.spotify.com/licenses-loader.html#cccd1> |
| leveldb | <https://xpui.app.spotify.com/licenses-loader.html#07314> |
| libexpat | <https://xpui.app.spotify.com/licenses-loader.html#ea434> |
| libogg | <https://xpui.app.spotify.com/licenses-loader.html#4946f> |
| libsamplerate | <https://xpui.app.spotify.com/licenses-loader.html#35a6d> |
| libvorbis | <https://xpui.app.spotify.com/licenses-loader.html#4359f> |
| lmdb | <https://xpui.app.spotify.com/licenses-loader.html#c9469> |
| minimp3 | <https://xpui.app.spotify.com/licenses-loader.html#54886> |
| OpenSSL | <https://xpui.app.spotify.com/licenses-loader.html#c898f> |
| OpenSSL | <https://xpui.app.spotify.com/licenses-loader.html#c898f> |
| pffft | <https://xpui.app.spotify.com/licenses-loader.html#63cd3> |
| protobuf | <https://xpui.app.spotify.com/licenses-loader.html#9d3fd> |
| snappy | <https://xpui.app.spotify.com/licenses-loader.html#a0b11> |

## 8. See also

- [Indieweb and Personal Websites](01-indieweb-and-personal-websites.md#1-handles-and-profile-urls): shares source Dec.6.25.md
- [AI Prompts and Chat Exports](03-ai-prompts-and-chat-exports.md#1-research-index-prompts): shares source new!!.md, summarizer.md
- [Books and Reading](04-books-and-reading.md#1-rfantasy-book-recommendations): shares source Dec.6.25.md, summarizer.md
