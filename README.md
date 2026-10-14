# Awesome RSS Tools [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

> A curated list of tools for reading, generating, converting, and publishing RSS, Atom, and JSON feeds.

RSS is alive and well. This list focuses on **tools** (readers, servers, generators, converters, libraries), not lists of feeds to subscribe to.

## Contents

- [Self-Hosted Feed Readers and Servers](#self-hosted-feed-readers-and-servers)
- [Desktop and Mobile Readers](#desktop-and-mobile-readers)
- [Terminal Readers](#terminal-readers)
- [Hosted Services](#hosted-services)
- [Browser Extensions](#browser-extensions)
- [Feed Generators (Sites Without Feeds)](#feed-generators-sites-without-feeds)
- [Feed Processing and Filtering](#feed-processing-and-filtering)
- [Podcast and Newsletter Tools](#podcast-and-newsletter-tools)
- [Static Site and Blog Feed Generation](#static-site-and-blog-feed-generation)
- [Libraries and Parsers](#libraries-and-parsers)
- [Validators and Debugging](#validators-and-debugging)
- [Specs and Formats](#specs-and-formats)
- [Related Lists](#related-lists)
- [Contributing](#contributing)

## Self-Hosted Feed Readers and Servers

- [Miniflux](https://github.com/miniflux/v2) - Minimalist, opinionated feed reader written in Go.
- [FreshRSS](https://github.com/FreshRSS/FreshRSS) - Free, self-hostable aggregator with multi-user support and a Google Reader-compatible API.
- [Tiny Tiny RSS](https://github.com/tt-rss/tt-rss) - Long-running web-based news reader and aggregator.
- [Yarr](https://github.com/nkanaev/yarr) - Single-binary web feed reader with a minimal footprint.
- [Stringer](https://github.com/stringer-rss/stringer) - Self-hosted, anti-social RSS reader.
- [Commafeed](https://github.com/Athou/commafeed) - Google Reader inspired self-hosted reader.
- [NewsBlur](https://github.com/samuelclay/NewsBlur) - Personal news reader with intelligence filters (open source and hosted).
- [Feedbin](https://github.com/feedbin/feedbin) - Open source code behind the hosted Feedbin service.
- [Fusion](https://github.com/0x2E/fusion) - Lightweight self-hosted RSS reader and aggregator.
- [Selfoss](https://github.com/fossar/selfoss) - Multipurpose RSS reader and feed aggregator.
- [Nextcloud News](https://github.com/nextcloud/news) - RSS/Atom reader app for Nextcloud.
- [Wallabag](https://github.com/wallabag/wallabag) - Read-it-later app that also ingests feeds.

## Desktop and Mobile Readers

- [NetNewsWire](https://github.com/Ranchero-Software/NetNewsWire) - Free and open source reader for macOS and iOS.
- [Fluent Reader](https://github.com/yang991178/fluent-reader) - Modern desktop reader (Windows, Linux, macOS).
- [Liferea](https://github.com/lwindolf/liferea) - Linux desktop news aggregator.
- [Thunderbird](https://www.thunderbird.net/) - Email client with built-in feed support.
- [Akregator](https://apps.kde.org/akregator/) - KDE feed reader.
- [Read You](https://github.com/Ashinch/ReadYou) - Android reader with Material You design.
- [FeedFlow](https://github.com/prof18/feed-flow) - Cross-platform (Android, iOS, desktop) reader.
- [Feeder](https://gitlab.com/spacecowboy/Feeder) - Android reader.
- [Capy Reader](https://github.com/jocmp/capyreader) - Android reader.
- [Reeder](https://reederapp.com/) - Polished reader for Apple platforms.
- [Vienna RSS](https://github.com/ViennaRSS/vienna-rss) - Open source macOS reader.
- [Unread](https://www.goldenhillsoftware.com/unread/) - Minimal reader for iOS.
- [Lire](https://lireapp.com/) - Reader for iOS and macOS.

## Terminal Readers

- [Newsboat](https://github.com/newsboat/newsboat) - RSS/Atom reader for the text console.
- [Russ](https://github.com/ckampfe/russ) - TUI feed reader written in Rust.
- [eilmeldung](https://github.com/christo-auer/eilmeldung) - TUI reader based on the news-flash library.
- [Canto](https://github.com/themoken/canto-curses) - Curses-based feed reader.
- [Sfeed](https://codemadness.org/sfeed.html) - Minimal RSS/Atom tooling following the UNIX philosophy.
- [Podboat](https://newsboat.org/releases/2.35/docs/podboat.html) - Podcast downloader that ships with Newsboat.

## Hosted Services

- [Feedly](https://feedly.com/) - Popular hosted reader with AI features.
- [Inoreader](https://www.inoreader.com/) - Hosted reader with rules, filters, and automation.
- [Feedbin](https://feedbin.com/) - Hosted reader with newsletter and podcast support.
- [NewsBlur](https://newsblur.com/) - Hosted reader with training and filters.
- [The Old Reader](https://theoldreader.com/) - Social-flavored hosted reader.
- [Readwise Reader](https://readwise.io/read) - Read-it-later and RSS in one app.
- [Feedspot](https://www.feedspot.com/) - Hosted aggregator and feed directory.
- [Folo](https://github.com/RSSNext/Folo) - Open source, AI-assisted reader and feed workspace.

## Browser Extensions

- [Feedbro](https://github.com/nodeedge/feedbro) - Advanced reader and organizer inside the browser.
- [Get RSS Feed URL](https://github.com/shevabam/get-rss-feed-url-extension) - Detects feeds on the current page.

## Feed Generators (Sites Without Feeds)

- [RSSHub](https://github.com/DIYgod/RSSHub) - Everything is RSSible; thousands of community routes.
- [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) - PHP project that creates feeds for sites that lack them.
- [Huginn](https://github.com/huginn/huginn) - Build agents that monitor and act on the web, including feed output.
- [Feedity](https://feedity.com/) - Hosted service that turns web pages into feeds.
- [FiveFilters Feed Creator](https://createfeed.fivefilters.org/) - Build feeds from pages with CSS selectors.
- [changedetection.io](https://github.com/dgtlmoon/changedetection.io) - Website change detection with RSS output.
- [Nitter](https://github.com/zedeus/nitter) - Alternative Twitter front end that exposes RSS (instance availability varies).
- [Invidious](https://github.com/iv-org/invidious) - YouTube front end with RSS support. YouTube also exposes native channel feeds.

## Feed Processing and Filtering

- [FreshRSS Extensions](https://github.com/FreshRSS/Extensions) - Plugin collection for FreshRSS.
- [Feed2toot](https://gitlab.com/chaica/feed2toot) - Post feed items to Mastodon.
- [Feed2imap](https://github.com/feed2imap/feed2imap) - Pull feeds into IMAP folders.
- [rss2email](https://github.com/rss2email/rss2email) - Deliver feed items as emails.
- [Blogtrottr](https://blogtrottr.com/) - Hosted feeds-to-email service.
- [IFTTT](https://ifttt.com/) - Trigger actions from feed updates.
- [Zapier](https://zapier.com/) - Connect feeds to thousands of apps.
- [n8n](https://github.com/n8n-io/n8n) - Self-hostable workflow automation with RSS triggers.

## Podcast and Newsletter Tools

- [Kill the Newsletter!](https://github.com/leafac/kill-the-newsletter) - Turns email newsletters into Atom feeds.
- [Podgrab](https://github.com/akhilrex/podgrab) - Self-hosted podcast manager and downloader.
- [AntennaPod](https://github.com/AntennaPod/AntennaPod) - Android podcast manager built on RSS.
- [Audiobookshelf](https://github.com/advplyr/audiobookshelf) - Self-hosted audiobook and podcast server.
- [Podcast Index](https://podcastindex.org/) - Open podcast directory with API.
- [Castopod](https://github.com/ad-aures/castopod) - Open source podcast hosting platform.

## Static Site and Blog Feed Generation

- [Hugo](https://gohugo.io/templates/rss/) - Built-in RSS templates.
- [Jekyll Feed](https://github.com/jekyll/jekyll-feed) - Atom feed generator plugin for Jekyll.
- [Eleventy RSS Plugin](https://github.com/11ty/eleventy-plugin-rss) - Feed helpers for Eleventy.
- [Feed (Node.js)](https://github.com/jpmonette/feed) - Generate RSS 2.0, Atom 1.0, and JSON Feed.
- [Astro RSS](https://docs.astro.build/en/guides/rss/) - Official RSS support for Astro.
- [Hexo Generator Feed](https://github.com/hexojs/hexo-generator-feed) - Feed generator for Hexo.
- [MkDocs RSS Plugin](https://github.com/guts/mkdocs-rss-plugin) - Feed generation for MkDocs sites.

## Libraries and Parsers

- [feedparser (Python)](https://github.com/kurtmckee/feedparser) - Universal feed parser.
- [rss-parser (Node.js)](https://github.com/rbren/rss-parser) - Lightweight RSS parser.
- [gofeed (Go)](https://github.com/mmcdole/gofeed) - Parses RSS, Atom, and JSON feeds.
- [feed-rs (Rust)](https://github.com/feed-rs/feed-rs) - Parser for RSS, Atom, and JSON Feed.
- [feedjira (Ruby)](https://github.com/feedjira/feedjira) - Fast and flexible feed parser.
- [ROME (Java)](https://github.com/rometools/rome) - Java framework for feeds.
- [SimplePie (PHP)](https://github.com/simplepie/simplepie) - Feed parsing library.
- [FeedKit (Swift)](https://github.com/nmdias/FeedKit) - Swift feed parser.
- [news-flash (Rust)](https://gitlab.com/news-flash/news_flash) - Feed reader backend library.

## Validators and Debugging

- [W3C Feed Validation Service](https://validator.w3.org/feed/) - Validates RSS and Atom.
- [Feed Validator source](https://github.com/w3c/feedvalidator) - Open source code behind the W3C validator.
- [RSS Board Validator](https://www.rssboard.org/rss-validator) - RSS-specific validation.
- [Podbase Podcast Validator](https://podba.se/validate/) - Podcast feed checker.
- [Cast Feed Validator](https://castfeedvalidator.com/) - Podcast feed validation.
- [JSON Feed Validator](https://validator.jsonfeed.org/) - Checks JSON Feed documents.

## Specs and Formats

- [RSS 2.0 Specification](https://www.rssboard.org/rss-specification)
- [Atom Syndication Format (RFC 4287)](https://www.rfc-editor.org/rfc/rfc4287)
- [JSON Feed](https://www.jsonfeed.org/)
- [OPML 2.0](http://opml.org/spec2.opml)
- [WebSub](https://www.w3.org/TR/websub/) - Real-time feed push protocol.
- [Podcast Namespace](https://github.com/Podcastindex-org/podcast-namespace) - Modern podcast RSS extensions.

## Related Lists

- [voidfiles/awesome-rss](https://github.com/voidfiles/awesome-rss) - Links related to RSS, Atom, and syndication formats.
- [plenaryapp/awesome-rss-feeds](https://github.com/plenaryapp/awesome-rss-feeds) - Curated feeds and OPML files to subscribe to.
- [tuan3w/awesome-tech-rss](https://github.com/tuan3w/awesome-tech-rss) - RSS feeds for startups, science, and technology.
- [JackyST0/awesome-rsshub-routes](https://github.com/JackyST0/awesome-rsshub-routes) - Useful RSSHub routes.
- [rumca-js/awesome-database-feeds](https://github.com/rumca-js/awesome-database-feeds) - Structured database of RSS feeds.
- [HenryQW/Awesome-TTRSS](https://github.com/HenryQW/Awesome-TTRSS) - Dockerised all-in-one Tiny Tiny RSS setup.

## Contributing

Contributions are welcome. Please:

- Add one tool per line, alphabetically within its section.
- Use the format `[Name](link) - Short description ending with a period.`
- Make sure the project is maintained and the link works.
- Suggest new categories via a pull request or issue.
