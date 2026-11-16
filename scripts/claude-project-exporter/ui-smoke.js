/**
 * ui-smoke.js - headless-browser smoke test of the userscript's button, panel, download and capture mode.
 *
 * Loads the userscript into Chromium on a faked https://claude.ai/project/<id>
 * page (every request is answered locally by Playwright; nothing reaches
 * claude.ai), clicks through an export, unzips the download and checks it.
 * Read-only helper: prints its checks to the screen, writes no results log.
 * Needs Playwright, which the cloud session image provides.
 *
 * Usage:
 *     node scripts/claude-project-exporter/ui-smoke.js [screenshot.png]
 */
'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');

const ORG = '11111111-1111-4111-8111-111111111111';
const PROJ = '22222222-2222-4222-8222-222222222222';
const CHATS = [1, 2].map(n => ({
  uuid: `0000000${n}-aaaa-4aaa-8aaa-aaaaaaaaaaaa`, name: `Chat ${n}`, created_at: `2026-02-0${n}T10:00:00Z`, updated_at: `2026-02-0${n}T11:00:00Z`, project_uuid: PROJ,
  current_leaf_message_uuid: 'b',
  chat_messages: [
    { uuid: 'a', parent_message_uuid: 'r', sender: 'human', content: [{ type: 'text', text: `q${n}` }] },
    { uuid: 'b', parent_message_uuid: 'a', sender: 'assistant', content: [{ type: 'text', text: `a${n}` }] },
  ],
}));
const brief = (c) => ({ uuid: c.uuid, name: c.name, created_at: c.created_at, updated_at: c.updated_at, project_uuid: c.project_uuid });

function answer(url) {
  const p = url.pathname;
  if (p === '/api/organizations') return [{ uuid: ORG }];
  if (p === `/api/organizations/${ORG}/projects/${PROJ}`) return { uuid: PROJ, name: 'Smoke Project', prompt_template: 'Be brief.', docs_count: 1, files_count: 0 };
  if (p === `/api/organizations/${ORG}/projects/${PROJ}/docs`) return [{ uuid: 'd1', file_name: 'notes.md', content: '# notes' }];
  if (p === `/api/organizations/${ORG}/projects/${PROJ}/files`) return [];
  if (p === `/api/organizations/${ORG}/projects/${PROJ}/conversations`) return CHATS.map(brief);
  if (p === `/api/organizations/${ORG}/chat_conversations`) return Number(url.searchParams.get('offset')) ? [] : CHATS.map(brief);
  if (p === `/api/organizations/${ORG}/projects/${PROJ}/made_up_for_capture`) return { secret_text: 'do not leak', items: [{ type: 'note', body: 'private' }] };
  const chat = CHATS.find(c => p === `/api/organizations/${ORG}/chat_conversations/${c.uuid}`);
  return chat || null;
}

(async () => {
  const userscript = fs.readFileSync(path.join(__dirname, 'claude-project-exporter.user.js'), 'utf8');
  const browser = await chromium.launch();
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1000, height: 800 } });
  const offOrigin = [];
  await context.route('**/*', (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== 'https://claude.ai') { offOrigin.push(url.href); return route.abort(); }
    if (!url.pathname.startsWith('/api/')) return route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>fake claude</title><body><h1>fake page</h1></body>' });
    const body = answer(url);
    return body ? route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) }) : route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });
  await context.addInitScript(userscript); // same timing as @run-at document-start
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  // 1. not a project page: no button
  await page.goto('https://claude.ai/chat/abc');
  await page.waitForTimeout(1300);
  assert.equal(await page.locator('#cpe-host').count(), 0, 'no button outside a project page');
  console.log('ok  no button on a non-project page');

  // 2. SPA navigation into a project: button appears without a reload
  await page.evaluate((p) => history.pushState({}, '', `/project/${p}`), PROJ);
  const open = page.getByRole('button', { name: 'Export project ZIP' });
  await open.waitFor({ timeout: 5000 });
  console.log('ok  button appears after in-app navigation to /project/<id>');

  // 3. export without memory -> INCOMPLETE; with "no memory" ticked -> COMPLETE
  await open.click();
  const start = page.getByRole('button', { name: 'Start export' });
  let [download] = await Promise.all([page.waitForEvent('download'), start.click()]);
  assert.match(download.suggestedFilename(), /-INCOMPLETE\.zip$/);
  await page.getByText('INCOMPLETE — do not delete the project').waitFor();
  console.log('ok  missing memory -> panel says INCOMPLETE, file is', download.suggestedFilename());

  await page.getByText('This project has no memory').click();
  [download] = await Promise.all([page.waitForEvent('download'), start.click()]);
  await page.getByText('COMPLETE: every chat and file that was found is in the ZIP.').waitFor();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cpe-ui-'));
  const zipPath = path.join(dir, download.suggestedFilename());
  await download.saveAs(zipPath);
  execFileSync('unzip', ['-tq', zipPath]);
  const manifest = JSON.parse(execFileSync('unzip', ['-p', zipPath, '_manifest.json']).toString());
  assert.equal(manifest.complete, true);
  assert.deepEqual(manifest.counts.chats, { found: 2, exported: 2 });
  assert.deepEqual(manifest.counts.files, { found: 1, saved: 1 });
  const names = execFileSync('unzip', ['-Z1', zipPath]).toString().trim().split('\n');
  for (const n of ['project/instructions.md', 'knowledge/notes.md', 'chats/2026-02-01-chat-1-00000001.md', 'raw/2026-02-01-chat-1-00000001.json', 'chat_db.json', 'attachment_db.json', '_errors.md']) assert.ok(names.includes(n), `zip has ${n}`);
  const cells = await page.locator('#cpe-host td').allTextContents();
  assert.deepEqual(cells.slice(0, 6), ['Chats', '2', '2', 'Files (all kinds)', '1', '1']);
  console.log('ok  COMPLETE run: real browser download unzips cleanly;', names.length, 'entries; panel shows found 2 / in ZIP 2 chats');
  if (process.argv[2]) { await page.screenshot({ path: process.argv[2] }); console.log('ok  screenshot', process.argv[2]); }

  // 4. capture mode: on after reload, logs shapes without values or ids
  await page.locator('#cpe-host input[type=checkbox]').nth(1).check();
  await page.reload();
  await page.evaluate(([o, p]) => fetch(`/api/organizations/${o}/projects/${p}/made_up_for_capture`).then(r => r.json()), [ORG, PROJ]);
  await page.getByRole('button', { name: 'Export project ZIP' }).click();
  await page.waitForFunction(() => document.querySelector('#cpe-host').shadowRoot.querySelectorAll('textarea')[1].value.includes('made_up_for_capture'));
  const logText = await page.evaluate(() => document.querySelector('#cpe-host').shadowRoot.querySelectorAll('textarea')[1].value);
  const entry = JSON.parse(logText).captured.find(e => e.url.includes('made_up_for_capture') && e.shape);
  assert.equal(entry.url, '/api/organizations/{uuid}/projects/{uuid}/made_up_for_capture');
  assert.deepEqual(entry.shape, { secret_text: 'string', items: ['len=1', { type: 'string:"note"', body: 'string' }] });
  assert.ok(!logText.includes('do not leak') && !logText.includes(ORG) && !logText.includes(PROJ));
  console.log('ok  capture mode logged the request shape with ids and values removed');

  assert.deepEqual(offOrigin, [], 'no request left claude.ai');
  assert.deepEqual(errors, [], 'no page errors');
  console.log('ok  zero requests to any other origin, zero page errors');
  await browser.close();
  console.log('\nALL UI SMOKE CHECKS PASSED');
})().catch((e) => { console.error('FAILED:', e); process.exit(1); });
