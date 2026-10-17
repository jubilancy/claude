/*
 * Cosmos.so collections scraper — paste into the DevTools Console.
 *
 * Run it on an element page (https://www.cosmos.so/e/<id>). It reads the collections that
 * element was saved to (the "/<user>/<collection>" links in the element dialog), opens each
 * collection in a hidden same-origin iframe, scrolls it to the end, and pulls every element
 * out of the React fibers (same technique as cosmos-scraper.js, which this file does not need).
 *
 * Other ways to feed it:
 *   window.__cosmosCollectionUrls = ['https://www.cosmos.so/user/collection', ...]  // before pasting
 * or paste it on any page that already links to collections (a profile page, for instance).
 *
 * Output: window.__cosmos (all unique elements, each with a `collections` list),
 * window.__cosmosSummary (per-collection counts), plus JSON + CSV downloads.
 * Call window.__cosmosStop() to stop early; whatever was collected is still saved.
 */
(async () => {
  const CFG = {
    stepFraction: 0.7,
    settleMs: 600,
    idleRounds: 25,       // per collection: stop after this many steps with nothing new
    maxSteps: 4000,
    maxElementsPerCollection: 5000,
    maxFiberHops: 40,
    loadTimeoutMs: 25000, // wait this long for a collection's first tiles
    pauseBetweenMs: 800,
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let stop = false;
  window.__cosmosStop = () => { stop = true; };

  // ---- 1. which collections? -------------------------------------------------------------
  const RESERVED = new Set(['', 'e', 'explore', 'search', 'brand', 'login', 'start', 'sequence',
    'careers', 'legal', 'shop', 'settings', 'notifications', 'api', '_next']);
  const collectionLinks = (doc) => {
    const out = new Set();
    doc.querySelectorAll('a[href^="/"]').forEach((a) => {
      const parts = a.getAttribute('href').split('?')[0].split('#')[0].split('/').filter(Boolean);
      if (parts.length === 2 && !RESERVED.has(parts[0]) && !RESERVED.has(parts[1])) {
        out.add(`${location.origin}/${parts.join('/')}`);
      }
    });
    return [...out];
  };

  const dialog = document.querySelector('[data-testid="element-view-dialog"]');
  let urls = Array.isArray(window.__cosmosCollectionUrls) && window.__cosmosCollectionUrls.length
    ? window.__cosmosCollectionUrls
    : collectionLinks(dialog || document);
  urls = [...new Set(urls)];
  if (!urls.length) {
    console.warn('[cosmos] no collection links found. Open an /e/<id> page at desktop width (turn off DevTools ' +
      'device emulation: the mobile layout hides them), or set window.__cosmosCollectionUrls.');
    return [];
  }
  console.log(`[cosmos] ${urls.length} collections:\n  ${urls.join('\n  ')}`);

  // ---- 2. scrape one document (collection page inside an iframe) -------------------------
  const elementFromTile = (tile) => {
    const k = Object.keys(tile).find((x) => x.startsWith('__reactFiber$'));
    let f = k ? tile[k] : null;
    for (let i = 0; f && i < CFG.maxFiberHops; i++, f = f.return) {
      const v = f.memoizedProps && f.memoizedProps.value;
      if (v && v.element && v.element.id != null) return v.element;
    }
    return null;
  };

  const toRow = (e) => ({
    id: e.id,
    url: e.shareUrl || `https://www.cosmos.so/e/${e.id}`,
    mediaUrl: (e.media && e.media.url) || null,
    mediaType: (e.media && e.media.__typename) || null,
    width: (e.media && e.media.width) || null,
    height: (e.media && e.media.height) || null,
    sourceUrl: (e.source && e.source.url) || null,
    sourceAuthor: (e.source && e.source.author && e.source.author.username) || null,
    owner: (e.owner && e.owner.username) || null,
    caption: e.generatedCaption && e.generatedCaption.text
      ? e.generatedCaption.text.replace(/<\/?n>/g, '') : null,
    createdAt: e.createdAt || null,
  });

  const scrollerOf = (doc, win) => {
    const tile = doc.querySelector('[data-testid="element-tile"]');
    for (let n = tile && tile.parentElement; n && n !== doc.body; n = n.parentElement) {
      if (n.scrollHeight > n.clientHeight + 50 && /(auto|scroll)/.test(win.getComputedStyle(n).overflowY)) return n;
    }
    return null;
  };

  const scrapeFrame = async (frame, onTiles) => {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    const local = new Map();
    const collect = () => {
      let added = 0;
      doc.querySelectorAll('[data-testid="element-tile"]').forEach((t) => {
        const e = elementFromTile(t);
        if (e && !local.has(e.id)) { local.set(e.id, toRow(e)); added++; }
      });
      return added;
    };
    // wait for first tiles
    const t0 = Date.now();
    while (!doc.querySelector('[data-testid="element-tile"]') && Date.now() - t0 < CFG.loadTimeoutMs && !stop) {
      await sleep(300);
    }
    await sleep(CFG.settleMs);
    collect();
    let idle = 0;
    for (let step = 0; step < CFG.maxSteps && !stop; step++) {
      const el = scrollerOf(doc, win);
      if (el) el.scrollBy(0, Math.round(el.clientHeight * CFG.stepFraction));
      else win.scrollBy(0, Math.round(win.innerHeight * CFG.stepFraction));
      await sleep(CFG.settleMs);
      idle = collect() ? 0 : idle + 1;
      if (step % 10 === 0) onTiles(local.size);
      if (idle >= CFG.idleRounds || local.size >= CFG.maxElementsPerCollection) break;
    }
    return [...local.values()];
  };

  // ---- 3. loop over collections ----------------------------------------------------------
  const all = new Map();
  const summary = [];
  const frame = document.createElement('iframe');
  // Real size + opacity 0 (not display:none) so the virtualized grid still lays out and loads.
  frame.style.cssText = 'position:fixed;left:0;top:0;width:1400px;height:900px;opacity:0;pointer-events:none;border:0;z-index:-1';
  document.body.appendChild(frame);

  for (let i = 0; i < urls.length && !stop; i++) {
    const url = urls[i];
    console.log(`[cosmos] (${i + 1}/${urls.length}) ${url}`);
    try {
      await new Promise((resolve, reject) => {
        const t = setTimeout(() => reject(new Error('load timeout')), CFG.loadTimeoutMs);
        frame.onload = () => { clearTimeout(t); resolve(); };
        frame.onerror = () => { clearTimeout(t); reject(new Error('frame error')); };
        frame.src = url;
      });
      const rows = await scrapeFrame(frame, (n) => console.log(`[cosmos]   ${n} so far`));
      let fresh = 0;
      rows.forEach((r) => {
        const prev = all.get(r.id);
        if (prev) prev.collections.push(url);
        else { all.set(r.id, { ...r, collections: [url] }); fresh++; }
      });
      summary.push({ collection: url, elements: rows.length, newUnique: fresh });
      console.log(`[cosmos]   ${rows.length} elements (${fresh} new). Running total: ${all.size}`);
    } catch (err) {
      summary.push({ collection: url, elements: 0, newUnique: 0, error: String(err.message || err) });
      console.warn(`[cosmos]   failed: ${err.message || err}`);
    }
    await sleep(CFG.pauseBetweenMs);
  }
  frame.remove();

  // ---- 4. output -------------------------------------------------------------------------
  const rows = [...all.values()].map((r) => ({ ...r, collections: r.collections.join(' | ') }));
  window.__cosmos = rows;
  window.__cosmosSummary = summary;
  console.table(summary);
  console.log(`[cosmos] done: ${rows.length} unique elements across ${summary.length} collections. Data in window.__cosmos`);

  const download = (name, text, type) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
  const slug = location.pathname.replace(/^\/|\/$/g, '').replace(/\//g, '_') || 'cosmos';
  const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const cols = Object.keys(rows[0] || { url: 1 });
  download(`${slug}-collections.json`, JSON.stringify({ summary, elements: rows }, null, 2), 'application/json');
  download(`${slug}-collections.csv`,
    [cols.join(','), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(','))].join('\n'), 'text/csv');

  try {
    await Promise.race([navigator.clipboard.writeText(rows.map((r) => r.url).join('\n')),
      sleep(1500).then(() => { throw 0; })]);
    console.log('[cosmos] page URLs copied to clipboard');
  } catch {
    console.log('[cosmos] clipboard blocked; run copy(__cosmos.map(r => r.url).join("\\n"))');
  }
  return rows;
})();
