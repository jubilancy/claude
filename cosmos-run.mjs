#!/usr/bin/env node
/*
 * Checklist runner for the Cosmos scrapers. Reads a markdown checklist of links, runs the
 * right scraper in headless Chromium for every unchecked link, writes the results to
 * cosmos-output/, and ticks the box. Links already ticked (or whose output file exists) are skipped.
 *
 *   node cosmos-run.mjs [checklist.md] [--force] [--only <substring>]
 *
 * Checklist format (one link per line; anything else is left untouched):
 *   - [ ] https://www.cosmos.so/e/556978292                  -> collections mode (every collection the element is in)
 *   - [ ] https://www.cosmos.so/design/the-best-band-posters -> grid mode (the page's own elements)
 *   - [ ] https://www.cosmos.so/e/853905883 | grid           -> force a mode with "| grid" or "| collections"
 *
 * Done lines become:  - [x] <url> -> cosmos-output/<slug>.json (482 elements)
 * Failed lines stay unchecked with " (failed: reason)" so the next run retries them.
 * Needs Playwright + Chromium (preinstalled in Claude Code cloud sessions).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const only = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;
const checklist = path.resolve(args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--only') || path.join(here, 'cosmos-links.md'));
const outDir = path.join(path.dirname(checklist), 'cosmos-output');

async function loadPlaywright() {
  const candidates = ['playwright', '/opt/node-tools/node_modules/playwright/index.mjs'];
  for (const c of candidates) {
    try { return await import(c.startsWith('/') ? pathToFileURL(c).href : c); } catch { /* try next */ }
  }
  throw new Error('Playwright not found. Install it (npm i playwright) or run inside a Claude Code cloud session.');
}

const slugOf = (url) => new URL(url).pathname.replace(/^\/|\/$/g, '').replace(/[^a-z0-9._-]+/gi, '_') || 'cosmos';
const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
const toCsv = (rows) => {
  const cols = Object.keys(rows[0] || { url: 1 });
  return [cols.join(','), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(','))].join('\n');
};

const LINE = /^(\s*[-*]\s*)\[( |x|X)\]\s+(https?:\/\/\S+)(?:\s*\|\s*(grid|collections))?(.*)$/;

const { chromium } = await loadPlaywright();
const lines = fs.readFileSync(checklist, 'utf8').split('\n');
fs.mkdirSync(outDir, { recursive: true });

const executablePath = fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined;
const browser = await chromium.launch({ executablePath, args: ['--no-sandbox'] });
const scripts = {
  grid: fs.readFileSync(path.join(here, 'cosmos-scraper.js'), 'utf8'),
  collections: fs.readFileSync(path.join(here, 'cosmos-collections.js'), 'utf8'),
};

let done = 0, skipped = 0, failed = 0;
for (let i = 0; i < lines.length; i++) {
  const m = lines[i].match(LINE);
  if (!m) continue;
  const [, bullet, box, url, modeHint] = m;
  if (only && !url.includes(only)) continue;
  const slug = slugOf(url);
  const jsonPath = path.join(outDir, `${slug}.json`);
  if (!flag('--force') && (box.toLowerCase() === 'x' || fs.existsSync(jsonPath))) {
    skipped++;
    if (box === ' ') lines[i] = `${bullet}[x] ${url}${modeHint ? ` | ${modeHint}` : ''} -> ${path.relative(path.dirname(checklist), jsonPath)} (already scraped)`;
    console.log(`skip  ${url}`);
    continue;
  }
  const mode = modeHint || (new URL(url).pathname.startsWith('/e/') ? 'collections' : 'grid');
  console.log(`run   ${url}  [${mode}]`);
  const t0 = Date.now();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(2500);
    const result = await page.evaluate(async (src) => {
      const rows = await (0, eval)(src);
      return { rows, summary: window.__cosmosSummary || null };
    }, scripts[mode]);
    if (!result.rows.length) throw new Error('0 elements found');
    fs.writeFileSync(jsonPath, JSON.stringify({ source: url, mode, scrapedAt: new Date().toISOString(), summary: result.summary, elements: result.rows }, null, 2));
    fs.writeFileSync(path.join(outDir, `${slug}.csv`), toCsv(result.rows));
    lines[i] = `${bullet}[x] ${url}${modeHint ? ` | ${modeHint}` : ''} -> ${path.relative(path.dirname(checklist), jsonPath)} (${result.rows.length} elements)`;
    done++;
    console.log(`done  ${result.rows.length} elements in ${Math.round((Date.now() - t0) / 1000)}s`);
  } catch (err) {
    failed++;
    lines[i] = `${bullet}[ ] ${url}${modeHint ? ` | ${modeHint}` : ''} (failed: ${String(err.message || err).split('\n')[0].slice(0, 120)})`;
    console.log(`fail  ${url}: ${err.message}`);
  } finally {
    await ctx.close();
    fs.writeFileSync(checklist, lines.join('\n')); // tick/untick after every link so progress survives a crash
  }
}
await browser.close();
fs.writeFileSync(checklist, lines.join('\n'));
console.log(`\n${done} scraped, ${skipped} skipped, ${failed} failed. Output in ${path.relative(process.cwd(), outDir) || outDir}`);
