/*
 * Cosmos.so collection scraper — paste into the DevTools Console on a collection page
 * (e.g. https://www.cosmos.so/<user>/<collection>).
 *
 * Cosmos virtualizes its grid: only ~30 tiles exist in the DOM at once, and the URLs are
 * not in <a href>s (tiles are <button data-testid="element-tile-link">). So instead of
 * reading the DOM, this walks each tile's React fiber up to the context provider whose
 * value holds the full `element` object (id, shareUrl, media.url, source.url, ...),
 * auto-scrolls to load the rest, and de-dupes by element id.
 *
 * Output: window.__cosmos (array), plus a JSON download, CSV download and a clipboard copy
 * of the page URLs. Re-run safe. Call window.__cosmosStop() to stop early.
 */
(async () => {
  const CFG = {
    stepFraction: 0.7,   // scroll this fraction of the viewport per step
    settleMs: 600,       // wait after each scroll for tiles/fetches to render
    idleRounds: 25,      // stop after this many consecutive steps with no new elements
    maxSteps: 4000,
    maxElements: 2000,   // stop once this many are collected (search/explore feeds can be endless)
    maxFiberHops: 40,
  };

  const seen = new Map();
  let stop = false;
  window.__cosmosStop = () => { stop = true; };

  const fiberOf = (node) => {
    const k = Object.keys(node).find((x) => x.startsWith('__reactFiber$'));
    return k ? node[k] : null;
  };

  // Climb from a tile's DOM node through React fibers until a props.value.element appears.
  const elementFromTile = (tile) => {
    let f = fiberOf(tile);
    for (let i = 0; f && i < CFG.maxFiberHops; i++, f = f.return) {
      const v = f.memoizedProps && f.memoizedProps.value;
      if (v && v.element && v.element.id != null) return v.element;
    }
    return null;
  };

  const collect = () => {
    let added = 0;
    document.querySelectorAll('[data-testid="element-tile"]').forEach((tile) => {
      const e = elementFromTile(tile);
      if (!e || seen.has(e.id)) return;
      seen.set(e.id, {
        id: e.id,
        url: e.shareUrl || `https://www.cosmos.so/e/${e.id}`,
        mediaUrl: e.media && e.media.url || null,
        mediaType: e.media && e.media.__typename || null,
        width: e.media && e.media.width || null,
        height: e.media && e.media.height || null,
        sourceUrl: e.source && e.source.url || null,
        sourceAuthor: e.source && e.source.author && e.source.author.username || null,
        owner: e.owner && e.owner.username || null,
        caption: e.generatedCaption && e.generatedCaption.text
          ? e.generatedCaption.text.replace(/<\/?n>/g, '') : null,
        createdAt: e.createdAt || null,
      });
      added++;
    });
    return added;
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Element pages (/e/<id>) show related tiles inside a scrollable dialog, not the window,
  // so scroll the nearest scrollable ancestor of the tiles, falling back to the window.
  const scroller = () => {
    const tile = document.querySelector('[data-testid="element-tile"]');
    for (let n = tile && tile.parentElement; n && n !== document.body; n = n.parentElement) {
      if (n.scrollHeight > n.clientHeight + 50 && /(auto|scroll)/.test(getComputedStyle(n).overflowY)) return n;
    }
    return null;
  };
  const scrollStep = () => {
    const el = scroller();
    if (el) el.scrollBy(0, Math.round(el.clientHeight * CFG.stepFraction));
    else window.scrollBy(0, Math.round(window.innerHeight * CFG.stepFraction));
  };

  (scroller() || window).scrollTo(0, 0);
  await sleep(CFG.settleMs);
  collect();

  let idle = 0;
  for (let step = 0; step < CFG.maxSteps && !stop; step++) {
    scrollStep();
    await sleep(CFG.settleMs);
    const added = collect();
    idle = added ? 0 : idle + 1;
    if (step % 5 === 0) console.log(`[cosmos] ${seen.size} elements (step ${step}, idle ${idle})`);
    if (idle >= CFG.idleRounds || seen.size >= CFG.maxElements) break;
  }

  const rows = [...seen.values()];
  if (!rows.length) {
    console.warn('[cosmos] found 0 elements. If DevTools device emulation (phone/narrow width) is on, turn it off: ' +
      'the mobile layout does not render the tile grid. Also check you are on a page with a grid of tiles.');
  }
  window.__cosmos = rows;
  console.log(`[cosmos] done: ${rows.length} unique elements. Data in window.__cosmos`);

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
  download(`${slug}.json`, JSON.stringify(rows, null, 2), 'application/json');
  download(`${slug}.csv`,
    [cols.join(','), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(','))].join('\n'),
    'text/csv');

  const urls = rows.map((r) => r.url).join('\n');
  try {
    await Promise.race([navigator.clipboard.writeText(urls), sleep(1500).then(() => { throw 0; })]);
    console.log('[cosmos] page URLs copied to clipboard');
  } catch {
    console.log('[cosmos] clipboard blocked; run copy(__cosmos.map(r => r.url).join("\\n"))');
  }
  return rows;
})();
