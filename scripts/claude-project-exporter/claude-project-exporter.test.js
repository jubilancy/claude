/**
 * claude-project-exporter.test.js - Node tests for the userscript's pure functions and a mock end-to-end export.
 *
 * Read-only helper: it prints test results to the screen and writes no results
 * log. The end-to-end tests run the real export pipeline against an in-memory
 * fake of the claude.ai endpoints (no network), then unzip and check the output.
 *
 * Usage:
 *     node --test scripts/claude-project-exporter/claude-project-exporter.test.js
 */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const X = require('./claude-project-exporter.user.js');

const ORG = '11111111-1111-4111-8111-111111111111';
const PROJ = '22222222-2222-4222-8222-222222222222';
const ORIGIN = 'https://claude.ai';
const cid = (n) => `${String(n).padStart(8, '0')}-aaaa-4aaa-8aaa-aaaaaaaaaaaa`;

// ---------------------------------------------------------------- slugs / names
test('slugify: accents, punctuation, unicode, empty, length', () => {
  assert.equal(X.slugify('Héllo, Wörld!  (v2)'), 'hello-world-v2');
  assert.equal(X.slugify('日本語 タイトル'), '日本語-タイトル');
  assert.equal(X.slugify('  ///  '), 'untitled');
  assert.equal(X.slugify(null), 'untitled');
  assert.equal(X.slugify('a'.repeat(100)).length, 60);
  assert.equal(X.slugify('word '.repeat(30), 20), 'word-word-word-word');
});

test('safeName: illegal characters, reserved names, trailing dots, extension kept', () => {
  assert.equal(X.safeName('a/b\\c:d*e?f"g<h>i|j.txt'), 'a_b_c_d_e_f_g_h_i_j.txt');
  assert.equal(X.safeName('CON.txt'), '_CON.txt');
  assert.equal(X.safeName('report. . '), 'report');
  assert.equal(X.safeName('..hidden'), 'hidden');
  assert.equal(X.safeName(''), 'unnamed');
  const long = X.safeName('x'.repeat(300) + '.pdf');
  assert.equal(long.length, 120);
  assert.ok(long.endsWith('.pdf'));
  assert.equal(X.safePath('/mnt/user-data/../outputs/a:b.csv'), 'mnt/user-data/outputs/a_b.csv');
});

test('chatBaseName: date-slug-id8, duplicate titles stay distinct', () => {
  const used = new Set();
  const a = X.chatBaseName({ uuid: cid(1), name: 'Same Title', created_at: '2026-03-04T05:06:07Z' }, used);
  const b = X.chatBaseName({ uuid: cid(2), name: 'Same Title', created_at: '2026-03-04T09:00:00Z' }, used);
  const c = X.chatBaseName({ uuid: cid(1), name: 'Same Title', created_at: '2026-03-04T05:06:07Z' }, used);
  assert.equal(a, '2026-03-04-same-title-00000001');
  assert.equal(b, '2026-03-04-same-title-00000002');
  assert.equal(c, '2026-03-04-same-title-00000001-2');
  assert.equal(X.chatBaseName({ uuid: cid(3), name: '', created_at: null }, used), 'undated-untitled-00000003');
});

test('uniqueName: case-insensitive, suffix goes before the extension', () => {
  const used = new Set();
  assert.equal(X.uniqueName('k/Notes.md', used), 'k/Notes.md');
  assert.equal(X.uniqueName('k/notes.md', used), 'k/notes-2.md');
  assert.equal(X.uniqueName('k/NOTES.md', used), 'k/NOTES-3.md');
});

// ---------------------------------------------------------------- markdown
test('fence: never closed early by backticks inside', () => {
  assert.equal(X.fence('x', 'js'), '```js\nx\n```');
  const inner = 'before\n```python\nprint(1)\n```\nafter ````';
  const out = X.fence(inner, 'text');
  assert.ok(out.startsWith('`````text\n'));
  assert.ok(out.endsWith('\n`````'));
  assert.ok(out.includes(inner));
});

const CODE = 'Here:\n\n```python\ndef f(x):\n    return x  # tabs\tand `ticks`\n```\n';
function sampleConv() {
  return {
    uuid: cid(7), name: 'Tree: "quoted" title', created_at: '2026-01-02T03:04:05Z', updated_at: '2026-01-03T00:00:00Z', model: 'm',
    current_leaf_message_uuid: 'm4',
    chat_messages: [
      { uuid: 'm1', parent_message_uuid: 'root', sender: 'human', created_at: '2026-01-02T03:04:05Z', content: [{ type: 'text', text: 'first prompt' }],
        attachments: [{ file_name: 'notes.txt', file_type: 'txt', file_size: 5, extracted_content: 'hello' }],
        files_v2: [{ file_kind: 'image', file_uuid: 'f-img', file_name: 'pic.png', preview_url: `/api/${ORG}/files/f-img/preview` }],
        files: [{ file_kind: 'image', file_uuid: 'f-img', file_name: 'pic.png' }] },
      { uuid: 'm2', parent_message_uuid: 'm1', sender: 'assistant', content: [{ type: 'text', text: 'abandoned answer' },
        { type: 'tool_use', name: 'artifacts', id: 't0', input: { id: 'doc', type: 'text/markdown', title: 'Doc', command: 'create', content: 'OLD BRANCH' } }] },
      { uuid: 'm3', parent_message_uuid: 'm1', sender: 'assistant', content: [
        { type: 'thinking', thinking: 'hmm ``` inside' },
        { type: 'text', text: CODE },
        { type: 'tool_use', name: 'artifacts', id: 't1', input: { id: 'doc', type: 'application/vnd.ant.code', language: 'python', title: 'Doc', command: 'create', content: 'a = 1\nb = 2\n' } },
        { type: 'tool_result', name: 'artifacts', tool_use_id: 't1', content: [{ type: 'text', text: 'OK' }] },
        { type: 'tool_use', name: 'web_search', id: 't2', input: { query: 'x "y"' } },
        { type: 'tool_result', name: 'present_files', content: [{ type: 'local_resource', file_path: '/mnt/user-data/outputs/out.csv', name: 'out.csv' }] },
        { type: 'mystery', payload: [1, 2] },
      ] },
      { uuid: 'm4', parent_message_uuid: 'm3', sender: 'assistant', content: [
        { type: 'tool_use', name: 'artifacts', id: 't3', input: { id: 'doc', command: 'update', old_str: 'b = 2', new_str: 'b = $& 3' } },
        { type: 'tool_use', name: 'artifacts', id: 't4', input: { id: 'doc', command: 'update', old_str: 'NOT THERE', new_str: 'z' } },
      ] },
    ],
  };
}

test('activeBranch follows current_leaf; falls back to all messages', () => {
  const conv = sampleConv();
  assert.deepEqual(X.activeBranch(conv).map(m => m.uuid), ['m1', 'm3', 'm4']);
  assert.equal(X.activeBranch({ chat_messages: conv.chat_messages }).length, 4);
  assert.equal(X.activeBranch({ chat_messages: conv.chat_messages, current_leaf_message_uuid: 'gone' }).length, 4);
});

test('planChatFiles: uploads de-duplicated, artifact versions replayed per branch', () => {
  const plan = X.planChatFiles(sampleConv(), 'base');
  assert.deepEqual(plan.uploads.map(u => [u.kind, u.path]), [
    ['attachment', 'files/base/attachments/1-notes.txt.extracted.txt'],
    ['file', 'files/base/attachments/1-pic.png'],
  ]);
  assert.deepEqual(plan.artifacts.map(a => [a.version, a.path, a.text]), [
    [1, 'files/base/artifacts/doc-v1.md', 'OLD BRANCH'],
    [2, 'files/base/artifacts/doc-v2.py', 'a = 1\nb = 2\n'],
    [3, 'files/base/artifacts/doc-v3.py', 'a = 1\nb = $& 3\n'], // literal replacement, no $& expansion; not built on OLD BRANCH
    [4, 'files/base/artifacts/doc-v4.json', JSON.stringify({ id: 'doc', command: 'update', old_str: 'NOT THERE', new_str: 'z' }, null, 2)],
  ]);
  assert.match(plan.artifacts[3].problem, /could not be applied/);
  assert.deepEqual(plan.presented.map(p => p.path), ['/mnt/user-data/outputs/out.csv']);
});

test('renderChat: frontmatter, roles, exact code blocks, tool calls, every message rendered', () => {
  const conv = sampleConv();
  const { markdown, rendered } = X.renderChat(conv, { url: `${ORIGIN}/chat/${conv.uuid}`, projectName: 'My: Project', projectId: PROJ });
  assert.equal(rendered, 4);
  const fm = markdown.split('---')[1];
  assert.match(fm, /^title: "Tree: \\"quoted\\" title"$/m);
  assert.match(fm, new RegExp(`^url: "${ORIGIN}/chat/${conv.uuid}"$`, 'm'));
  assert.match(fm, /^created: "2026-01-02T03:04:05Z"$/m);
  assert.match(fm, /^updated: "2026-01-03T00:00:00Z"$/m);
  assert.match(fm, /^project: "My: Project"$/m);
  assert.match(fm, /^message_count: 4$/m);
  assert.match(fm, /^active_branch_message_count: 3$/m);
  assert.ok(markdown.includes('## 1. Human — 2026-01-02T03:04:05Z'));
  assert.ok(markdown.includes('## 2. Assistant'));
  assert.ok(markdown.includes(CODE), 'assistant text with its code block is byte-for-byte intact');
  assert.ok(markdown.includes('````text\nhmm ``` inside\n````'), 'thinking fenced safely');
  assert.ok(markdown.includes('**Tool call:** `web_search` (id `t2`)\n\n```json\n{\n  "query": "x \\"y\\""\n}\n```'));
  assert.ok(markdown.includes('**Tool result:** `artifacts` (for `t1`)\n\n```text\nOK\n```'));
  assert.ok(markdown.includes('"file_path": "/mnt/user-data/outputs/out.csv"'), 'file reference kept exactly');
  assert.ok(markdown.includes('**Block:** `mystery`'), 'unknown block types are kept, not dropped');
  assert.ok(markdown.indexOf('# Other branches') < markdown.indexOf('abandoned answer'), 'off-branch message is still in the transcript');
});

// ---------------------------------------------------------------- count check
const fullCounts = () => ({ chats: { found: 3, exported: 3 }, knowledge: { found: 2, saved: 2 }, uploads: { found: 1, saved: 1 }, artifacts: { found: 4, saved: 4 }, container_files: { found: 0, saved: 0 } });
const okFlags = () => ({ project: true, instructions: true, memory: 'pasted', chatListing: true, knowledgeListing: true });

test('checkCounts: complete only when everything matches', () => {
  const ok = X.checkCounts(fullCounts(), okFlags(), 0, 0);
  assert.deepEqual([ok.complete, ok.verdict, ok.chats, ok.files], [true, 'COMPLETE', { found: 3, exported: 3 }, { found: 7, saved: 7 }]);
  assert.equal(X.checkCounts(fullCounts(), okFlags(), 0, 2).verdict, 'COMPLETE WITH WARNINGS');
});

test('checkCounts: every kind of gap refuses "complete"', () => {
  const cases = [
    [c => { c.chats.exported = 2; }, f => f, /chats: found 3, exported 2/],
    [c => { c.knowledge.saved = 1; }, f => f, /knowledge: found 2, saved 1/],
    [c => { c.uploads.saved = 0; }, f => f, /uploads: found 1, saved 0/],
    [c => { c.container_files.found = 1; }, f => f, /container files: found 1, saved 0/],
    [c => c, f => { f.cancelled = true; }, /cancelled/],
    [c => c, f => { f.memory = 'missing'; }, /memory/],
    [c => c, f => { f.instructions = false; }, /instructions/],
    [c => c, f => { f.chatListing = false; }, /chat list/],
    [c => c, f => { f.knowledgeListing = false; }, /knowledge file list/],
    [c => c, f => { f.fatal = 'boom'; }, /boom/],
  ];
  for (const [mc, mf, re] of cases) {
    const c = fullCounts(); const f = okFlags(); mc(c); mf(f);
    const r = X.checkCounts(c, f, 0, 0);
    assert.equal(r.complete, false);
    assert.equal(r.verdict, 'INCOMPLETE');
    assert.match(r.reasons.join('\n'), re);
  }
  assert.equal(X.checkCounts(fullCounts(), okFlags(), 1, 0).complete, false, 'a logged error alone blocks "complete"');
  assert.equal(X.checkCounts(fullCounts(), { ...okFlags(), memory: 'declared_none' }, 0, 0).complete, true);
});

// ---------------------------------------------------------------- misc pure
test('asArray: unexpected shapes throw instead of reading as empty', () => {
  assert.deepEqual(X.asArray([1]), [1]);
  assert.deepEqual(X.asArray({ data: [2] }), [2]);
  assert.throws(() => X.asArray({ error: 'nope' }, 'docs'), /unexpected shape for docs/);
  assert.throws(() => X.asArray(null), /unexpected shape/);
});

test('shapeOf and redactUrl: no values, no ids', () => {
  const shape = X.shapeOf({ uuid: cid(1), name: 'secret', n: 3, list: [{ type: 'tool_use', text: 'private' }], [cid(2)]: true });
  assert.deepEqual(shape, { uuid: 'string', name: 'string', n: 'number', list: ['len=1', { type: 'string:"tool_use"', text: 'string' }], '{uuid}': 'boolean' });
  assert.ok(!JSON.stringify(shape).includes('secret') && !JSON.stringify(shape).includes('private'));
  assert.equal(X.redactUrl(`${ORIGIN}/api/organizations/${ORG}/projects/${PROJ}/docs?limit=5`), '/api/organizations/{uuid}/projects/{uuid}/docs?limit=5');
});

test('fileCandidates: originals first, previews flagged, thumbnails last', () => {
  const c = X.fileCandidates(ORG, { file_uuid: 'u1', file_name: 'a.pdf', file_kind: 'document', document_asset: { url: '/doc' }, preview_url: '/prev', thumbnail_url: '/thumb' });
  assert.deepEqual(c.map(x => x.quality), ['original', 'original', 'preview', 'thumbnail']);
  assert.equal(c[1].url, `/api/${ORG}/files/u1/document_pdf`);
  assert.deepEqual(X.fileCandidates(ORG, { file_uuid: 'u2', file_kind: 'blob', file_name: 'x.bin' }), [{ url: `/api/organizations/${ORG}/files/u2/contents`, quality: 'original' }]);
});

test('findMemoryFields: finds non-empty memory-ish fields only', () => {
  assert.deepEqual(X.findMemoryFields({ name: 'p', memory: '', settings: { project_memory: 'remember this', enabled_memory: true } }), { 'settings.project_memory': 'remember this' });
});

test('crc32 known value', () => {
  assert.equal(X.crc32(new TextEncoder().encode('123456789')), 0xcbf43926);
});

// ---------------------------------------------------------------- zip
function unzipTo(parts) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cpe-'));
  const file = path.join(dir, 'out.zip');
  fs.writeFileSync(file, Buffer.concat(parts.map(p => Buffer.from(p))));
  execFileSync('unzip', ['-tq', file]); // integrity test: throws on any CRC or structure error
  const out = path.join(dir, 'x');
  execFileSync('unzip', ['-q', file, '-d', out]);
  const read = (p) => fs.readFileSync(path.join(out, p));
  const list = [];
  (function walk(d, rel) { for (const e of fs.readdirSync(d, { withFileTypes: true })) e.isDirectory() ? walk(path.join(d, e.name), `${rel}${e.name}/`) : list.push(rel + e.name); })(out, '');
  return { read, text: (p) => read(p).toString('utf8'), json: (p) => JSON.parse(read(p).toString('utf8')), list: list.sort() };
}

test('createZip: round-trips text, binary, unicode names and duplicates through unzip', async () => {
  const zip = X.createZip(new Date(2026, 0, 2, 3, 4, 6));
  const bin = new Uint8Array(70000).map((_, i) => (i * 7919) % 256);
  const big = 'compress me '.repeat(5000);
  assert.equal(await zip.add('a/héllo 日本.txt', 'unicode ✓'), 'a/héllo 日本.txt');
  assert.equal(await zip.add('a/bin.dat', bin), 'a/bin.dat');
  assert.equal(await zip.add('big.txt', big), 'big.txt');
  assert.equal(await zip.add('BIG.txt', 'second'), 'BIG-2.txt');
  assert.equal(await zip.add('bad:name?.txt', ''), 'bad_name_.txt');
  const parts = zip.finish();
  assert.ok(parts.reduce((n, p) => n + p.length, 0) < big.length, 'deflate was used');
  const z = unzipTo(parts);
  assert.equal(z.text('a/héllo 日本.txt'), 'unicode ✓');
  assert.deepEqual(new Uint8Array(z.read('a/bin.dat')), bin);
  assert.equal(z.text('big.txt'), big);
  assert.equal(z.text('BIG-2.txt'), 'second');
  assert.equal(z.list.length, 5);
});

// ---------------------------------------------------------------- mock end-to-end
function mockApi(overrides = {}) {
  const convs = new Map();
  const mk = (n, title, extra = {}) => {
    const c = { uuid: cid(n), name: title, created_at: `2026-02-0${n}T10:00:00Z`, updated_at: `2026-02-0${n}T11:00:00Z`, project_uuid: PROJ, current_leaf_message_uuid: 'b',
      chat_messages: [
        { uuid: 'a', parent_message_uuid: 'r', sender: 'human', created_at: `2026-02-0${n}T10:00:00Z`, content: [{ type: 'text', text: `question ${n}` }] },
        { uuid: 'b', parent_message_uuid: 'a', sender: 'assistant', content: [{ type: 'text', text: `answer ${n}` }] },
      ], ...extra };
    convs.set(c.uuid, c);
  };
  mk(1, 'Same Title');
  mk(2, 'Same Title');
  const rich = sampleConv(); rich.uuid = cid(3); rich.project_uuid = PROJ; rich.settings = { enabled_monkeys_in_a_barrel: true }; convs.set(rich.uuid, rich);
  mk(4, 'Broken chat');
  mk(5, 'Only in the full list');
  const other = Array.from({ length: 7 }, (_, i) => ({ uuid: cid(100 + i), name: `other ${i}`, project_uuid: null }));
  const summary = (c) => ({ uuid: c.uuid, name: c.name, created_at: c.created_at, updated_at: c.updated_at, project_uuid: c.project_uuid });
  const all = [...other.slice(0, 4), ...[...convs.values()].map(summary), ...other.slice(4)];
  const hits = new Map();
  const log = [];
  const routes = {
    '/api/organizations': () => [{ uuid: 'ffffffff-ffff-4fff-8fff-ffffffffffff' }, { uuid: ORG }],
    [`/api/organizations/ffffffff-ffff-4fff-8fff-ffffffffffff/projects/${PROJ}`]: () => 404,
    [`/api/organizations/${ORG}/projects/${PROJ}`]: () => ({ uuid: PROJ, name: 'Démo Project', prompt_template: 'Always answer in haiku.', created_at: '2026-01-01T00:00:00Z' }),
    [`/api/organizations/${ORG}/projects/${PROJ}/docs`]: () => [
      { uuid: 'd1', file_name: 'notes.md', content: '# notes', created_at: '2026-01-05T00:00:00Z' },
      { uuid: 'd2', file_name: 'notes.md', content: '# second notes' },
      { uuid: 'd3', file_name: 'paper.pdf', content: 'extracted paper text' },
    ],
    [`/api/organizations/${ORG}/projects/${PROJ}/files`]: () => [
      { file_uuid: 'k1', file_name: 'paper.pdf', file_kind: 'document' },
      { file_uuid: 'k2', file_name: 'logo.png', file_kind: 'image', preview_url: `/api/${ORG}/files/k2/preview` },
      { file_uuid: 'k3', file_name: 'gone.bin', file_kind: 'blob' },
    ],
    [`/api/${ORG}/files/k1/document_pdf`]: () => 404,
    [`/api/${ORG}/files/k2/preview`]: () => new Uint8Array([137, 80, 78, 71, 1, 2, 3]),
    [`/api/organizations/${ORG}/files/k3/contents`]: () => 404,
    [`/api/${ORG}/files/f-img/preview`]: () => new Uint8Array([9, 8, 7]),
    [`/api/organizations/${ORG}/projects/${PROJ}/conversations`]: () => [1, 2, 3, 4].map(n => summary(convs.get(cid(n)))),
    [`/api/organizations/${ORG}/conversations/${cid(3)}/wiggle/list-files`]: () => ({ success: true, files: ['x'], files_metadata: [{ path: '/mnt/user-data/outputs/out.csv', content_type: 'text/csv' }, { path: '/mnt/user-data/outputs/lost.txt' }] }),
    ...overrides,
  };
  const fetchImpl = async (href) => {
    const u = new URL(href);
    const key = u.pathname;
    hits.set(key, (hits.get(key) || 0) + 1);
    log.push(u.pathname + u.search);
    const reply = (body, status = 200, type = 'application/json', headers = {}) =>
      new Response(body instanceof Uint8Array ? body : (typeof body === 'string' ? body : JSON.stringify(body)), { status, headers: { 'content-type': type, ...headers } });
    if (key === `/api/organizations/${ORG}/chat_conversations`) {
      if (routes.fullList) return routes.fullList(u, reply, hits.get(key));
      if (hits.get(key) === 2) return reply('slow down', 429, 'text/plain', { 'retry-after': '1' }); // one 429, then fine
      const limit = Math.min(Number(u.searchParams.get('limit')), 5); // server caps the page size below what was asked
      const offset = Number(u.searchParams.get('offset'));
      return reply(all.slice(offset, offset + limit));
    }
    const m = new RegExp(`^/api/organizations/${ORG}/chat_conversations/([0-9a-f-]+)$`).exec(key);
    if (m) {
      if (m[1] === cid(4)) return reply('{"error":"boom"}', 500);
      assert.equal(u.search, '?tree=True&rendering_mode=messages&render_all_tools=true');
      return convs.has(m[1]) ? reply(convs.get(m[1])) : reply('{}', 404);
    }
    if (key === `/api/organizations/${ORG}/conversations/${cid(3)}/wiggle/download-file`) {
      return u.searchParams.get('path') === '/mnt/user-data/outputs/out.csv' ? reply('a,b\n1,2\n', 200, 'text/csv') : reply('gone', 404, 'text/plain');
    }
    const r = routes[key] ? routes[key](u) : 404;
    if (typeof r === 'number') return reply('{"error":"x"}', r);
    return r instanceof Uint8Array ? reply(r, 200, 'application/octet-stream') : reply(r);
  };
  return { fetchImpl, hits, log, convs };
}

const run = (api, extra = {}) => X.runExport({ fetchImpl: api.fetchImpl, origin: ORIGIN, projectId: PROJ, minIntervalMs: 0, sleep: async () => {}, ...extra });

test('end to end: paginates, retries a 429, survives a failing chat, and refuses "complete"', async () => {
  const api = mockApi();
  const out = await run(api, { memoryText: 'User prefers metric units.' });
  const z = unzipTo(out.parts);

  // chats: 4 in the project list + 1 found only by the paginated cross-check; chat 4 always fails with 500
  assert.deepEqual(out.check.chats, { found: 5, exported: 4 });
  assert.equal(out.check.complete, false);
  assert.equal(out.check.verdict, 'INCOMPLETE');
  assert.match(out.zipName, /^demo-project-\d{4}-\d\d-\d\d_\d{6}-INCOMPLETE\.zip$/);
  assert.match(out.check.reasons.join('\n'), /chats: found 5, exported 4/);
  assert.equal(api.hits.get(`/api/organizations/${ORG}/chat_conversations/${cid(4)}`), 6, 'the 500 was retried 5 times with backoff, then given up');
  assert.ok(api.log.filter(l => l.includes('chat_conversations?limit=100&offset=')).length >= 3, 'kept paging past a short page');
  assert.ok(z.list.includes('chats/2026-02-05-only-in-the-full-list-00000005.md'), 'chat after the failing one was still exported');

  // duplicate titles get distinct files; raw JSON saved per chat and identical to the API response
  assert.ok(z.list.includes('chats/2026-02-01-same-title-00000001.md'));
  assert.ok(z.list.includes('chats/2026-02-02-same-title-00000002.md'));
  assert.deepEqual(z.json('raw/2026-02-01-same-title-00000001.json'), api.convs.get(cid(1)));

  // project texts
  assert.equal(z.text('project/instructions.md'), 'Always answer in haiku.');
  assert.equal(z.text('project/memory.md'), 'User prefers metric units.');

  // knowledge: 3 docs + 3 files found; gone.bin has neither original nor text
  assert.deepEqual(out.counts.knowledge, { found: 6, saved: 5 });
  assert.equal(z.text('knowledge/notes.md'), '# notes');
  assert.equal(z.text('knowledge/notes-2.md'), '# second notes');
  assert.equal(z.text('knowledge/paper.pdf.extracted.txt'), 'extracted paper text');
  assert.deepEqual([...z.read('knowledge/logo.png')], [137, 80, 78, 71, 1, 2, 3]);
  const kIndex = z.json('knowledge/_index.json');
  assert.deepEqual(kIndex.map(k => [k.file_name, k.source, k.saved_as, k.status]), [
    ['notes.md', 'docs', 'text_content', 'saved'], ['notes.md', 'docs', 'text_content', 'saved'], ['paper.pdf', 'docs', 'extracted_text', 'saved'],
    ['paper.pdf', 'files', 'extracted_text', 'saved'], ['logo.png', 'files', 'preview', 'saved'], ['gone.bin', 'files', null, 'failed'],
  ]);

  // rich chat: uploads, artifacts, container files
  const base = '2026-01-02-tree-quoted-title-00000003';
  assert.equal(z.text(`files/${base}/attachments/1-notes.txt.extracted.txt`), 'hello');
  assert.deepEqual([...z.read(`files/${base}/attachments/1-pic.png`)], [9, 8, 7]);
  assert.equal(z.text(`files/${base}/artifacts/doc-v3.py`), 'a = 1\nb = $& 3\n');
  assert.equal(z.text(`files/${base}/container/mnt/user-data/outputs/out.csv`), 'a,b\n1,2\n');
  assert.deepEqual(out.counts.uploads, { found: 2, saved: 2 });
  assert.deepEqual(out.counts.artifacts, { found: 4, saved: 4 });
  assert.deepEqual(out.counts.container_files, { found: 2, saved: 1 });
  const md = z.text(`chats/${base}.md`);
  assert.ok(md.includes(CODE));
  assert.ok(md.includes(`[files/${base}/attachments/1-pic.png](../files/${base}/attachments/1-pic.png)`));
  assert.ok(md.includes('`/mnt/user-data/outputs/lost.txt` — NOT SAVED: HTTP 404'));

  // manifest and databases
  const manifest = z.json('_manifest.json');
  assert.equal(manifest.complete, false);
  assert.deepEqual(manifest.counts.chats, { found: 5, exported: 4 });
  assert.deepEqual(manifest.counts.files, { found: 14, saved: 12 });
  const chatDb = z.json('chat_db.json');
  assert.equal(chatDb.length, 5);
  for (const row of chatDb) for (const k of ['id', 'title', 'url', 'created', 'updated', 'message_count', 'attachment_count']) assert.ok(k in row, `chat_db has ${k}`);
  assert.deepEqual(chatDb.map(r => [r.title, r.status, r.message_count]), [
    ['Same Title', 'exported', 2], ['Same Title', 'exported', 2], ['Tree: "quoted" title', 'exported', 4], ['Broken chat', 'failed', null], ['Only in the full list', 'exported', 2],
  ]);
  assert.equal(chatDb[0].url, `${ORIGIN}/chat/${cid(1)}`);
  assert.deepEqual(chatDb[4].found_in, ['conversation_list']);
  assert.deepEqual(manifest.chats, chatDb);
  const attDb = z.json('attachment_db.json');
  assert.equal(attDb.length, 14);
  assert.ok(attDb.every(a => a.total_attachment_count === 14));
  assert.equal(attDb.filter(a => a.status === 'failed').length, 2);
  for (const k of ['attachment_id', 'chat_id', 'title', 'url', 'created', 'updated', 'message_count', 'total_attachment_count', 'zip_path']) assert.ok(k in attDb[0], `attachment_db has ${k}`);

  // every failure is written down
  const errs = z.text('_errors.md');
  for (const needle of ['Broken chat', 'HTTP 500', 'gone.bin', 'lost.txt', 'Verdict: **INCOMPLETE**', 'the two lists disagree']) assert.ok(errs.includes(needle), `_errors.md mentions ${needle}`);
  const logName = z.list.find(n => /^results-log-\d{4}-\d\d-\d\d_\d{6}\.txt$/.test(n));
  assert.ok(logName);
  assert.match(z.text(logName), /SUMMARY[\s\S]*ERRORS \(3\)[\s\S]*WARNINGS \(/);

  // nothing left the origin, everything was a GET to claude.ai
  assert.ok(api.log.every(l => l.startsWith('/api/')));
});

test('end to end: a clean project is COMPLETE WITH WARNINGS (extracted text), and COMPLETE when nothing is degraded', async () => {
  const noBroken = { fullList: null };
  const api = mockApi(noBroken);
  // make chat 4 healthy and remove the unretrievable files
  const origFetch = api.fetchImpl;
  api.fetchImpl = async (href) => {
    const u = new URL(href);
    const json = (b) => new Response(JSON.stringify(b), { status: 200, headers: { 'content-type': 'application/json' } });
    if (u.pathname.endsWith(`/chat_conversations/${cid(4)}`)) return json(api.convs.get(cid(4)));
    if (u.pathname.endsWith('/files')) return json([]);
    if (u.pathname.endsWith('/docs')) return json([{ uuid: 'd1', file_name: 'notes.md', content: '# notes' }]);
    if (u.pathname.endsWith('/conversations') ) return json([1, 2, 4, 5].map(n => { const c = api.convs.get(cid(n)); return { uuid: c.uuid, name: c.name, created_at: c.created_at, updated_at: c.updated_at }; }));
    if (u.pathname.endsWith('/chat_conversations')) { const off = Number(u.searchParams.get('offset')); return json(off ? [] : [1, 2, 4, 5].map(n => ({ uuid: cid(n), project_uuid: PROJ }))); }
    return origFetch(href);
  };
  const out = await run(api, { memoryNone: true });
  assert.deepEqual(out.errors, []);
  assert.deepEqual(out.warnings, []);
  assert.deepEqual(out.check.chats, { found: 4, exported: 4 });
  assert.deepEqual(out.check.files, { found: 1, saved: 1 });
  assert.equal(out.check.verdict, 'COMPLETE');
  assert.ok(!out.zipName.includes('INCOMPLETE'));
  assert.equal(unzipTo(out.parts).json('_manifest.json').complete, true);
});

test('end to end: missing memory alone blocks "complete"', async () => {
  const out = await run(mockApi());
  assert.match(out.check.reasons.join('\n'), /project memory was not exported/);
  assert.ok(unzipTo(out.parts).text('_errors.md').includes('no verified endpoint for project memory'));
});

test('end to end: cancel still yields a ZIP that says INCOMPLETE', async () => {
  const api = mockApi();
  const controller = new AbortController();
  let calls = 0;
  const fetchImpl = async (href, init) => { if (++calls === 12) controller.abort(); if (init.signal.aborted) throw new DOMException('aborted', 'AbortError'); return api.fetchImpl(href); };
  const out = await X.runExport({ fetchImpl, origin: ORIGIN, projectId: PROJ, minIntervalMs: 0, sleep: async () => {}, signal: controller.signal, memoryNone: true });
  assert.equal(out.flags.cancelled, true);
  assert.equal(out.check.complete, false);
  const z = unzipTo(out.parts);
  assert.match(z.text('_errors.md'), /export was cancelled/);
  assert.equal(z.json('_manifest.json').verdict, 'INCOMPLETE');
});

test('end to end: unreadable project fails loudly, with a ZIP that explains why', async () => {
  const api = mockApi({ [`/api/organizations/${ORG}/projects/${PROJ}`]: () => 403 });
  const out = await run(api);
  assert.equal(out.check.complete, false);
  assert.match(out.check.reasons.join('\n'), /was not readable in any of your 2 organization/);
  assert.deepEqual(out.check.chats, { found: 0, exported: 0 });
});

test('end to end: an error object where a list is expected is an error, not "0 files"', async () => {
  const api = mockApi({ [`/api/organizations/${ORG}/projects/${PROJ}/docs`]: () => ({ error: { message: 'changed' } }) });
  const out = await run(api, { memoryNone: true });
  assert.equal(out.flags.knowledgeListing, false);
  assert.match(out.check.reasons.join('\n'), /knowledge file list could not be read completely/);
});

test('client: refuses any URL that is not on the page origin', async () => {
  const client = X.createClient({ fetchImpl: async () => { throw new Error('must not be called'); }, origin: ORIGIN, minIntervalMs: 0 });
  await assert.rejects(client.getBytes('https://evil.example/x'), /different origin/);
});
