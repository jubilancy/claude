# Ideas

Saved for later. Nothing here is started unless it says so.

## One blog post per Raindrop sub-collection, with a "More links" archive

**Idea:** For a sub-collection of the `scrape` collection (Raindrop ID 76376784), write a blog post titled after the sub-collection. Use the media and cited information from the bookmarked pages (Raindrop Pro keeps archived copies of the bookmarks). End each post with a "More links" section that lists every link in the collection, so nothing is lost when the collection is deleted later.

### What was checked (2026-11-17)

- Raindrop's archived text works. `fetch_bookmark_content` returned full article text, excerpts and credit lines for the pages tested (Greek Reporter plague article, World History Encyclopedia Procopius page, the Ortelius atlas article, Medievalists.net eyeglasses article).
- Some archived pages are nearly empty (for example the Britannica and EdTech Books pages returned only a title), so each post needs sources checked page by page.
- The archived text does not include image files or image URLs. Images have to come from the live pages or from open sources.
- Hotlinking works for open sources. Wikimedia Commons thumbnails returned HTTP 200. Facebook, Threads, Pinterest, Etsy, eBay and Amazon images often block hotlinks, so link to those pages instead of embedding.
- Wikimedia Commons rate-limits the shared proxy address. Use a descriptive User-Agent and retry with backoff.

### Sub-collections that looked suitable

Sampled and judged a good fit:

| Sub-collection | Raindrop ID | Bookmarks (at the time) |
|---|---|---|
| Justinian & Byzantium | 77244382 | 63 |
| Theatrum Orbis Terrarum (maps) | 77244387 | 100 |
| Psychology & medical history | 77244544 | 20 |

Not sampled, likely media-heavy: De Bry, Adam & Eve prints (77244386, 175 bookmarks).

Thin or mixed, would need splitting or more work: Insel-Bücherei & butterflies (77244541), Wales, UK & Ireland travel (77244510), Black ops patches (77244384), Scholarly books & Federici (77244543), Schizo-Culture & art presses (77244542), Book lists & occult sources (77244390), Rare books & public-domain art (77244480).

Not worth a post (shop listings, tools or raw search links): Sitemaps, Icons & SVG, Framer marketplace, Exported Twitter replies, Pinterest & social profiles, Rare book searches, Amphetamine Manifesto & ThriftBooks, Wordlists & suffix searches, Vintage book covers boards, Cutecore pixel stars, scrape-index, drafts, topic-classification-project.

### Plan

1. Pull every bookmark in the sub-collection (`find_bookmarks`, 150 per page).
2. Read the archived text of the content-rich ones (`fetch_bookmark_content`) and write the post from what the pages say, citing each source.
3. Hotlink images only from sources that allow it (Wikimedia Commons, Internet Archive, museum open-access pages). Put a credit and licence line under each image. Verify every image URL loads before it goes in the post.
4. Finish with a "More links" section listing every bookmark in the collection (title and URL), including the ones not used in the text.
5. Save as a draft only. Do not publish without asking.

### Where it stopped

Justinian & Byzantium was started and then paused. Nothing was created in WordPress.

- Draft target considered: `fromdaysoff.wordpress.com` (site ID 150245892, private). Not confirmed with the owner.
- All 63 bookmark titles and links in the collection had been fetched.
- Hotlinkable Wikimedia Commons images found and checked (HTTP 200):
  - Justinian and his retinue, San Vitale (CC BY-SA 3.0, Volodymyr Vlasenko): https://commons.wikimedia.org/wiki/File:Emperor_Justinian_and_his_retinue._Detail_of_the_mosaic_in_the_Basilica_of_San_Vitale._Ravena,_Italy.jpg
  - Empress Theodora and her retinue, San Vitale (CC BY-SA 2.0, Following Hadrian): https://commons.wikimedia.org/wiki/File:The_Empress_Theodora_and_her_retinue,_Basilica_of_San_Vitale,_Ravenna,_Italy_-_24346221276.jpg
  - Josse Lieferinxe, Saint Sebastian Interceding for the Plague Stricken (public domain): https://commons.wikimedia.org/wiki/File:Josse_Lieferinxe_-_Saint_Sebastian_Interceding_for_the_Plague_Stricken_-_Walters_371995.jpg
  - Gaspare Fossati and Louis Haghe, view of the Hagia Sophia nave (public domain): https://commons.wikimedia.org/wiki/File:Gaspare_Fossati_-_Louis_Haghe_-_Vue_g%C3%A9n%C3%A9rale_de_la_grande_nef,_en_regardant_l%27occident_(Hagia_Sophia_-_Ayasofya_Mosque_nave).jpg
- Source pages read for the text: World History Encyclopedia (Procopius on the plague), Greek Reporter (the Justinian plague), HistoryMedieval (Justinian the Great), Alberti's Window (San Vitale mosaic alterations), Rechtsgeschiedenis (Byzantine law), Rome on Rome (Ravenna), Medievalists.net (Procopius' Vandal War), the Met (the mosaic reproduction record) and PICRYL (NYPL, CC0).
