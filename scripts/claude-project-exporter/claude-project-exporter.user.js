// ==UserScript==
// @name         Claude Project ZIP Exporter
// @namespace    claude-project-exporter
// @version      0.2.0
// @description  Export a whole claude.ai Project (instructions, knowledge files, every chat, attachments, artifacts) as one ZIP, with a count check that refuses to say "complete" when anything is missing.
// @match        https://claude.ai/*
// @grant        none
// @run-at       document-start
// @noframes
// @license      MIT
// ==/UserScript==

/**
 * claude-project-exporter.user.js - userscript that exports one claude.ai Project as a single ZIP.
 *
 * Runs in the browser from a userscript manager (Violentmonkey or Tampermonkey).
 * It only makes same-origin GET requests to claude.ai with the page's own session
 * and builds the ZIP in the page. Nothing is sent anywhere else. No dependencies.
 *
 * Every run writes a results log into the ZIP (results-log-{YYYY-MM-DD_HHMMSS}.txt)
 * next to _manifest.json, chat_db.json, attachment_db.json and _errors.md, and the
 * panel shows the same counts at the end of the run.
 *
 * Usage:
 *     node --test scripts/claude-project-exporter/claude-project-exporter.test.js
 *
 * In the browser: install the file in a userscript manager, open
 * https://claude.ai/project/<id>, click "Export project ZIP". See README.md.
 */

(function () {
  'use strict';

  const VERSION = '0.3.0';
  const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  const UUID_RE_G = new RegExp(UUID_RE.source, 'gi');
  const enc = new TextEncoder();

  // ===========================================================================
  // ENDPOINTS
  // Every path below was copied from the published source of an existing
  // exporter (see README "Where the endpoints come from"). None of them could be
  // called from the build environment, so the response shapes are as those
  // scripts read them, not as observed live. Nothing here is from memory.
  // ===========================================================================
  const EP = {
    orgs: () => '/api/organizations',
    project: (o, p) => `/api/organizations/${o}/projects/${p}`,
    projectDocs: (o, p) => `/api/organizations/${o}/projects/${p}/docs`,
    projectFiles: (o, p) => `/api/organizations/${o}/projects/${p}/files`,
    projectChats: (o, p) => `/api/organizations/${o}/projects/${p}/conversations`,
    // Seen live (capture 2026-11-16, the project page's own calls): paged list with pagination.total, memory text, synced sources.
    projectChatsV2: (o, p, limit, offset) => `/api/organizations/${o}/projects/${p}/conversations_v2?limit=${limit}&offset=${offset}`,
    projectMemory: (o, p) => `/api/organizations/${o}/memory?project_uuid=${p}&include_project_import=true`,
    projectSyncs: (o, p) => `/api/organizations/${o}/projects/${p}/syncs?calculate_size=false`,
    allChats: (o, limit, offset) => `/api/organizations/${o}/chat_conversations?limit=${limit}&offset=${offset}`,
    chat: (o, c) => `/api/organizations/${o}/chat_conversations/${c}?tree=True&rendering_mode=messages&render_all_tools=true`,
    fileContents: (o, f) => `/api/organizations/${o}/files/${f}/contents`,
    filePdf: (o, f) => `/api/${o}/files/${f}/document_pdf`,
    containerList: (o, c, prefix) => `/api/organizations/${o}/conversations/${c}/wiggle/list-files?prefix=${encodeURIComponent(prefix || '')}`,
    containerFile: (o, c, path) => `/api/organizations/${o}/conversations/${c}/wiggle/download-file?path=${encodeURIComponent(path)}`,
  };

  // ===========================================================================
  // PURE HELPERS (unit-tested in Node)
  // ===========================================================================

  /** Lowercase URL/file-safe slug. Keeps letters and digits of any script. */
  function slugify(input, max = 60) {
    let s = String(input == null ? '' : input).normalize('NFKD').replace(/[̀-ͯ]/g, '');
    s = s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '');
    if (s.length > max) s = s.slice(0, max).replace(/-+$/g, '');
    return s || 'untitled';
  }

  const WIN_RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i;

  /** Make one path segment safe on Windows, macOS and Linux. Keeps the extension. */
  function safeName(input, max = 120) {
    let s = String(input == null ? '' : input).normalize('NFC');
    s = s.replace(/[\\/:*?"<>|\u0000-\u001f\u007f]/g, '_').replace(/\s+/g, ' ').trim();
    s = s.replace(/^\.+/, '').replace(/[. ]+$/g, '');
    if (!s) s = 'unnamed';
    if (WIN_RESERVED.test(s)) s = '_' + s;
    if (s.length > max) {
      const dot = s.lastIndexOf('.');
      const ext = dot > 0 && s.length - dot <= 12 ? s.slice(dot) : '';
      s = s.slice(0, max - ext.length).replace(/[. ]+$/g, '') + ext;
    }
    return s;
  }

  /** Safe relative path from a possibly absolute, possibly hostile path. */
  function safePath(p) {
    return String(p || '').split(/[\\/]+/).filter(seg => seg && seg !== '.' && seg !== '..').map(s => safeName(s)).join('/') || 'unnamed';
  }

  /** Return `name`, or `name-2`, `name-3`... so it is unique (case-insensitive) in `used`. */
  function uniqueName(name, used) {
    const dot = name.lastIndexOf('.');
    const slash = name.lastIndexOf('/');
    const hasExt = dot > slash + 1;
    const stem = hasExt ? name.slice(0, dot) : name;
    const ext = hasExt ? name.slice(dot) : '';
    let candidate = name;
    for (let n = 2; used.has(candidate.toLowerCase()); n++) candidate = `${stem}-${n}${ext}`;
    used.add(candidate.toLowerCase());
    return candidate;
  }

  function dateOf(iso) {
    const m = /^(\d{4}-\d{2}-\d{2})/.exec(String(iso || ''));
    return m ? m[1] : 'undated';
  }

  /** chats/<date>-<slug>-<id8> base name, unique within `used`. */
  function chatBaseName(chat, used) {
    const id8 = String(chat.uuid || 'noid').replace(/-/g, '').slice(0, 8) || 'noid';
    return uniqueName(`${dateOf(chat.created_at)}-${slugify(chat.name)}-${id8}`, used);
  }

  /** Fence text so that no backtick run inside it can close the fence. */
  function fence(text, lang = '') {
    const s = String(text == null ? '' : text);
    let longest = 0;
    for (const run of s.match(/`+/g) || []) longest = Math.max(longest, run.length);
    const ticks = '`'.repeat(Math.max(3, longest + 1));
    return `${ticks}${lang}\n${s}${s.endsWith('\n') ? '' : '\n'}${ticks}`;
  }

  function yamlFrontmatter(obj) {
    const lines = ['---'];
    for (const [k, v] of Object.entries(obj)) {
      if (v === undefined) continue;
      lines.push(`${k}: ${typeof v === 'number' || typeof v === 'boolean' || v === null ? String(v) : JSON.stringify(String(v))}`);
    }
    lines.push('---');
    return lines.join('\n');
  }

  /**
   * Unwrap a list response. Accepts an array, or an object holding one array
   * under a known key. Anything else throws: an unexpected shape must surface as
   * an error, never as "zero items".
   */
  function asArray(data, what = 'response') {
    if (Array.isArray(data)) return data;
    if (data && typeof data === 'object') {
      for (const key of ['data', 'items', 'results', 'conversations', 'files', 'docs']) {
        if (Array.isArray(data[key])) return data[key];
      }
    }
    throw new Error(`unexpected shape for ${what}: expected a list, got ${describe(data)}`);
  }

  function describe(v) {
    if (v === null) return 'null';
    if (Array.isArray(v)) return `array(${v.length})`;
    if (typeof v === 'object') return `object{${Object.keys(v).slice(0, 12).join(',')}}`;
    return typeof v;
  }

  const SHAPE_ENUM_KEYS = new Set(['type', 'kind', 'file_kind', 'command', 'sender', 'role', 'rendering_mode']);

  /** Structure of a JSON value with the values removed (capture mode). */
  function shapeOf(v, depth = 0, key = '') {
    if (v === null) return 'null';
    if (Array.isArray(v)) return v.length ? [`len=${v.length}`, depth >= 6 ? '…' : shapeOf(v[0], depth + 1)] : [];
    if (typeof v === 'object') {
      if (depth >= 6) return '{…}';
      const out = {};
      for (const k of Object.keys(v).slice(0, 80)) out[UUID_RE.test(k) ? '{uuid}' : k] = shapeOf(v[k], depth + 1, k);
      return out;
    }
    if (typeof v === 'string' && SHAPE_ENUM_KEYS.has(key) && v.length <= 40) return `string:"${v}"`;
    return typeof v;
  }

  /** Path + query with ids replaced, so a capture log can be pasted publicly. */
  function redactUrl(u) {
    let s = String(u);
    try { const x = new URL(s, 'https://claude.ai'); s = x.pathname + x.search; } catch (e) { /* keep as is */ }
    return s.replace(UUID_RE_G, '{uuid}').replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '{email}').replace(/=([^&]{48,})/g, '={long}');
  }

  /** Any field of the project JSON whose key mentions memory and holds something. */
  function findMemoryFields(obj, path = '', out = {}, depth = 0) {
    if (!obj || typeof obj !== 'object' || depth > 6) return out;
    for (const [k, v] of Object.entries(obj)) {
      const p = path ? `${path}.${k}` : k;
      if (/memor/i.test(k) && v !== null && v !== '' && typeof v !== 'boolean' && !(Array.isArray(v) && !v.length)) out[p] = v;
      else if (v && typeof v === 'object') findMemoryFields(v, p, out, depth + 1);
    }
    return out;
  }

  // ---- conversation tree -----------------------------------------------------

  /** Messages on the path from the root to current_leaf_message_uuid, in order. */
  function activeBranch(conv) {
    const msgs = Array.isArray(conv.chat_messages) ? conv.chat_messages : [];
    if (!conv.current_leaf_message_uuid) return msgs.slice();
    const byId = new Map(msgs.map(m => [m.uuid, m]));
    const branch = [];
    const seen = new Set();
    let id = conv.current_leaf_message_uuid;
    while (id && byId.has(id) && !seen.has(id)) {
      seen.add(id);
      branch.unshift(byId.get(id));
      id = byId.get(id).parent_message_uuid;
    }
    return branch.length ? branch : msgs.slice();
  }

  function roleLabel(sender) {
    if (sender === 'human') return 'Human';
    if (sender === 'assistant') return 'Assistant';
    return sender ? String(sender) : 'Unknown';
  }

  const ARTIFACT_EXT = {
    'text/html': 'html', 'text/markdown': 'md', 'image/svg+xml': 'svg',
    'application/vnd.ant.mermaid': 'mmd', 'application/vnd.ant.react': 'jsx',
  };
  const LANG_EXT = {
    python: 'py', javascript: 'js', typescript: 'ts', jsx: 'jsx', tsx: 'tsx', bash: 'sh', shell: 'sh', sh: 'sh',
    json: 'json', css: 'css', html: 'html', sql: 'sql', java: 'java', c: 'c', cpp: 'cpp', csharp: 'cs', go: 'go',
    rust: 'rs', ruby: 'rb', php: 'php', swift: 'swift', kotlin: 'kt', yaml: 'yaml', toml: 'toml', xml: 'xml',
    markdown: 'md', r: 'r', lua: 'lua', perl: 'pl',
  };
  function artifactExt(type, language) {
    if (ARTIFACT_EXT[type]) return ARTIFACT_EXT[type];
    return LANG_EXT[String(language || '').toLowerCase()] || 'txt';
  }

  /**
   * Everything a chat carries besides its text: uploads, artifacts, and files the
   * transcript says were produced in the code-execution container.
   * Paths are final and unique inside files/<base>/.
   */
  function planChatFiles(conv, base) {
    const msgs = Array.isArray(conv.chat_messages) ? conv.chat_messages : [];
    const used = new Set();
    const dir = `files/${base}`;
    const uploads = [];
    const artifacts = [];
    const presented = [];
    const seenPresented = new Set();

    msgs.forEach((m, mi) => {
      const n = mi + 1;
      (Array.isArray(m.attachments) ? m.attachments : []).forEach((a, i) => {
        const hasText = typeof a.extracted_content === 'string';
        const name = safeName(a.file_name || `attachment-${i + 1}`);
        uploads.push({
          kind: 'attachment', id: a.id || a.uuid || `${m.uuid}:attachment:${i}`, message_uuid: m.uuid, message_index: n,
          title: a.file_name || '(unnamed)', file_type: a.file_type || null, file_size: a.file_size ?? null,
          created: a.created_at || m.created_at || null, updated: m.updated_at || m.created_at || null,
          text: hasText ? a.extracted_content : null, file: null,
          path: uniqueName(`${dir}/attachments/${n}-${name}${hasText ? '.extracted.txt' : ''}`, used),
        });
      });
      const seenFiles = new Set();
      for (const f of [].concat(Array.isArray(m.files_v2) ? m.files_v2 : [], Array.isArray(m.files) ? m.files : [])) {
        if (!f || typeof f !== 'object') continue;
        const fid = f.file_uuid || f.uuid || `${m.uuid}:file:${seenFiles.size}`;
        if (seenFiles.has(fid)) continue;
        seenFiles.add(fid);
        uploads.push({
          kind: 'file', id: fid, message_uuid: m.uuid, message_index: n,
          title: f.file_name || '(unnamed)', file_type: f.file_kind || null, file_size: f.file_size ?? null,
          created: f.created_at || m.created_at || null, updated: m.updated_at || m.created_at || null,
          text: null, file: f,
          path: uniqueName(`${dir}/attachments/${n}-${safeName(f.file_name || `file-${String(fid).slice(0, 8)}`)}`, used),
        });
      }
    });

    // Artifacts: replay create / rewrite / update along each message's own ancestry
    // so that versions on an abandoned branch do not leak into the active one.
    const byId = new Map(msgs.map(m => [m.uuid, m]));
    const stateOf = new Map();
    const versionCount = new Map();
    const resolve = (m) => {
      const chain = [];
      let cur = m;
      const guard = new Set();
      while (cur && !stateOf.has(cur.uuid) && !guard.has(cur.uuid)) { guard.add(cur.uuid); chain.unshift(cur); cur = byId.get(cur.parent_message_uuid); }
      let state = cur && stateOf.has(cur.uuid) ? stateOf.get(cur.uuid) : new Map();
      for (const msg of chain) {
        state = new Map(state);
        (Array.isArray(msg.content) ? msg.content : []).forEach((b, bi) => {
          if (!b || b.type !== 'tool_use' || b.name !== 'artifacts' || !b.input || typeof b.input !== 'object') return;
          const inp = b.input;
          const aid = String(inp.id || `artifact-${msg.uuid}-${bi}`);
          const prev = state.get(aid) || {};
          const type = inp.type || prev.type || null;
          const language = inp.language || prev.language || null;
          const title = inp.title || prev.title || aid;
          let content = null;
          let problem = null;
          if (typeof inp.content === 'string' && inp.command !== 'update') content = inp.content;
          else if (inp.command === 'update' && typeof inp.old_str === 'string' && typeof inp.new_str === 'string') {
            if (typeof prev.content === 'string' && prev.content.includes(inp.old_str)) content = prev.content.replace(inp.old_str, () => inp.new_str);
            else problem = 'update could not be applied (old_str not found in the previous version); the raw update is saved instead';
          } else problem = `artifact command "${inp.command}" has no content; the raw tool input is saved instead`;
          const v = (versionCount.get(aid) || 0) + 1;
          versionCount.set(aid, v);
          if (content !== null) state.set(aid, { content, type, language, title });
          const ext = content !== null ? artifactExt(type, language) : 'json';
          artifacts.push({
            kind: 'artifact', id: aid, version: v, message_uuid: msg.uuid, message_index: msgs.indexOf(msg) + 1, block_index: bi,
            title, file_type: type, command: inp.command || null, created: b.stop_timestamp || msg.created_at || null,
            updated: msg.updated_at || msg.created_at || null, problem,
            text: content !== null ? content : JSON.stringify(inp, null, 2),
            path: uniqueName(`${dir}/artifacts/${safeName(slugify(aid, 50))}-v${v}.${ext}`, used),
          });
        });
        stateOf.set(msg.uuid, state);
      }
    };
    msgs.forEach(resolve);

    for (const m of msgs) {
      for (const b of Array.isArray(m.content) ? m.content : []) {
        if (!b || b.type !== 'tool_result' || !Array.isArray(b.content)) continue;
        for (const item of b.content) {
          if (item && item.type === 'local_resource' && typeof item.file_path === 'string' && !seenPresented.has(item.file_path)) {
            seenPresented.add(item.file_path);
            presented.push({ path: item.file_path, name: item.name || null, mime_type: item.mime_type || null, message_uuid: m.uuid });
          }
        }
      }
    }
    return { dir, uploads, artifacts, presented, used };
  }

  /** Same-origin URLs to try for one uploaded file, best first, with what each one yields. */
  function fileCandidates(orgId, f) {
    const out = [];
    const add = (url, quality) => { if (typeof url === 'string' && url && !out.some(c => c.url === url)) out.push({ url, quality }); };
    const uuid = f.file_uuid || f.uuid;
    if (f.document_asset) add(f.document_asset.url, 'original');
    if (uuid && f.file_kind === 'blob') add(EP.fileContents(orgId, uuid), 'original');
    if (uuid && /\.pdf$/i.test(f.file_name || '')) add(EP.filePdf(orgId, uuid), 'original');
    if (f.preview_asset) add(f.preview_asset.url, 'preview');
    add(f.preview_url, 'preview');
    if (f.thumbnail_asset) add(f.thumbnail_asset.url, 'thumbnail');
    add(f.thumbnail_url, 'thumbnail');
    return out;
  }

  function renderBlock(b, ctx) {
    if (b == null) return '';
    if (typeof b === 'string') return b;
    if (b.type === 'text' && typeof b.text === 'string') return b.text;
    if (b.type === 'thinking') return `**Thinking**\n\n${fence(b.thinking != null ? b.thinking : (b.text || ''), 'text')}`;
    if (b.type === 'tool_use') {
      const lines = [`**Tool call:** \`${b.name || 'unknown'}\`${b.id ? ` (id \`${b.id}\`)` : ''}`];
      const art = ctx.artifactByBlock && ctx.artifactByBlock.get(b);
      if (art) {
        lines.push('', `Artifact \`${art.id}\` v${art.version} — ${art.title} — ${art.saved ? `saved as [${art.path}](../${encodeURI(art.path)})` : `NOT SAVED: ${art.error || 'unknown'}`}${art.problem ? ` — note: ${art.problem}` : ''}`);
      }
      lines.push('', fence(JSON.stringify(b.input === undefined ? null : b.input, null, 2), 'json'));
      return lines.join('\n');
    }
    if (b.type === 'tool_result') {
      const lines = [`**Tool result:** \`${b.name || 'unknown'}\`${b.tool_use_id ? ` (for \`${b.tool_use_id}\`)` : ''}${b.is_error ? ' — ERROR' : ''}`];
      const items = Array.isArray(b.content) ? b.content : (b.content == null ? [] : [b.content]);
      for (const item of items) {
        lines.push('');
        if (typeof item === 'string') lines.push(fence(item, 'text'));
        else if (item && item.type === 'text' && typeof item.text === 'string') lines.push(fence(item.text, 'text'));
        else lines.push(fence(JSON.stringify(item, null, 2), 'json'));
      }
      return lines.join('\n');
    }
    return `**Block:** \`${b.type || 'unknown'}\`\n\n${fence(JSON.stringify(b, null, 2), 'json')}`;
  }

  function renderMessage(m, index, ctx) {
    const lines = [`## ${index}. ${roleLabel(m.sender)}${m.created_at ? ` — ${m.created_at}` : ''}`, '', `<!-- message ${m.uuid || '?'} parent ${m.parent_message_uuid || '-'} -->`, ''];
    const ups = (ctx.uploadsByMessage && ctx.uploadsByMessage.get(m.uuid)) || [];
    if (ups.length) {
      lines.push('**Attachments**', '');
      for (const u of ups) {
        const how = u.saved ? `${u.saved_as} — [${u.path}](../${encodeURI(u.path)})` : `NOT SAVED: ${u.error || 'unknown'}`;
        lines.push(`- \`${u.title}\`${u.file_type ? ` (${u.file_type})` : ''} — ${how}`);
      }
      lines.push('');
    }
    const blocks = Array.isArray(m.content) && m.content.length ? m.content : null;
    if (blocks) for (const b of blocks) lines.push(renderBlock(b, ctx), '');
    else if (typeof m.text === 'string') lines.push(m.text, '');
    return lines.join('\n');
  }

  /**
   * Full transcript. The active branch comes first; every other message in the
   * tree (edits, regenerations) follows, so the Markdown never drops a message.
   * Returns { markdown, rendered } where rendered must equal chat_messages.length.
   */
  function renderChat(conv, ctx = {}) {
    const all = Array.isArray(conv.chat_messages) ? conv.chat_messages : [];
    const branch = activeBranch(conv);
    const onBranch = new Set(branch);
    const others = all.filter(m => !onBranch.has(m));
    const fm = yamlFrontmatter({
      title: conv.name || 'Untitled',
      url: ctx.url || '',
      created: conv.created_at || '',
      updated: conv.updated_at || '',
      project: ctx.projectName || '',
      message_count: all.length,
      id: conv.uuid || '',
      project_id: ctx.projectId || '',
      active_branch_message_count: branch.length,
      other_branch_message_count: others.length,
      attachment_count: ctx.attachmentCount || 0,
      model: conv.model || '',
      exported: ctx.exportedAt || '',
    });
    const parts = [fm, '', `# ${conv.name || 'Untitled'}`, ''];
    let rendered = 0;
    branch.forEach((m, i) => { parts.push(renderMessage(m, i + 1, ctx)); rendered++; });
    if (others.length) {
      parts.push('---', '', '# Other branches', '', 'Messages that are not on the active path (edited prompts and regenerated answers). Each one names its parent message.', '');
      others.forEach((m, i) => { parts.push(renderMessage(m, branch.length + i + 1, ctx)); rendered++; });
    }
    if (ctx.containerFiles && ctx.containerFiles.length) {
      parts.push('---', '', '# Files from the code-execution container', '');
      for (const c of ctx.containerFiles) parts.push(`- \`${c.source_path}\` — ${c.saved ? `[${c.path}](../${encodeURI(c.path)})` : `NOT SAVED: ${c.error || 'unknown'}`}`);
      parts.push('');
    }
    return { markdown: parts.join('\n'), rendered };
  }

  // ---- count check -----------------------------------------------------------

  /**
   * Decide what the UI may claim. "COMPLETE" needs every found item saved, both
   * project texts accounted for, and no cancellation or fatal error.
   */
  function checkCounts(counts, flags = {}, errorCount = 0, warningCount = 0) {
    const reasons = [];
    const pair = (label, c, doneKey) => { if (c.found !== c[doneKey]) reasons.push(`${label}: found ${c.found}, ${doneKey} ${c[doneKey]}`); };
    pair('chats', counts.chats, 'exported');
    for (const k of ['knowledge', 'uploads', 'artifacts', 'container_files']) pair(k.replace('_', ' '), counts[k], 'saved');
    if (flags.cancelled) reasons.push('export was cancelled');
    if (flags.fatal) reasons.push(`export stopped early: ${flags.fatal}`);
    if (!flags.project) reasons.push('project details were not read');
    if (!flags.instructions) reasons.push('custom instructions were not exported');
    if (!flags.memory || flags.memory === 'missing') reasons.push('project memory was not exported (the memory endpoint failed; paste it into the panel or tick "no memory")');
    if (!flags.chatListing) reasons.push('the chat list could not be read completely');
    if (!flags.knowledgeListing) reasons.push('the knowledge file list could not be read completely');
    const filesFound = counts.knowledge.found + counts.uploads.found + counts.artifacts.found + counts.container_files.found;
    const filesSaved = counts.knowledge.saved + counts.uploads.saved + counts.artifacts.saved + counts.container_files.saved;
    if (!reasons.length && errorCount > 0) reasons.push(`${errorCount} error(s) logged in _errors.md`);
    const complete = reasons.length === 0;
    return {
      complete,
      verdict: complete ? (warningCount ? 'COMPLETE WITH WARNINGS' : 'COMPLETE') : 'INCOMPLETE',
      reasons,
      chats: { found: counts.chats.found, exported: counts.chats.exported },
      files: { found: filesFound, saved: filesSaved },
    };
  }

  // ---- ZIP writer (no dependency) ---------------------------------------------

  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
    return t;
  })();
  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  async function deflateRaw(bytes) {
    if (typeof CompressionStream === 'undefined' || typeof Response === 'undefined' || typeof Blob === 'undefined') return null;
    try {
      const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    } catch (e) { return null; }
  }

  /** Minimal ZIP (store or deflate, UTF-8 names, no ZIP64). add() returns the final unique path. */
  function createZip(date = new Date()) {
    const parts = [];
    const entries = [];
    const used = new Set();
    let offset = 0;
    const dosTime = ((date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1)) & 0xffff;
    const dosDate = ((Math.max(0, date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate()) & 0xffff;
    const LIMIT = 0xffffffff;
    return {
      get count() { return entries.length; },
      has: (p) => used.has(String(p).toLowerCase()),
      async add(path, data) {
        const bytes = typeof data === 'string' ? enc.encode(data) : (data instanceof Uint8Array ? data : new Uint8Array(data));
        if (entries.length >= 65534) throw new Error('ZIP limit reached: more than 65534 entries (ZIP64 is not supported)');
        const name = uniqueName(String(path).split('/').map(s => safeName(s)).join('/'), used);
        const nameBytes = enc.encode(name);
        let body = bytes;
        let method = 0;
        if (bytes.length > 64) {
          const z = await deflateRaw(bytes);
          if (z && z.length < bytes.length) { body = z; method = 8; }
        }
        if (offset + 30 + nameBytes.length + body.length > LIMIT - 0x1000000) {
          used.delete(name.toLowerCase());
          throw new Error('ZIP limit reached: archive would exceed 4 GB (ZIP64 is not supported)');
        }
        const crc = crc32(bytes);
        const h = new DataView(new ArrayBuffer(30));
        h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, method, true);
        h.setUint16(10, dosTime, true); h.setUint16(12, dosDate, true); h.setUint32(14, crc, true);
        h.setUint32(18, body.length, true); h.setUint32(22, bytes.length, true); h.setUint16(26, nameBytes.length, true); h.setUint16(28, 0, true);
        parts.push(new Uint8Array(h.buffer), nameBytes, body);
        entries.push({ nameBytes, crc, method, comp: body.length, size: bytes.length, offset });
        offset += 30 + nameBytes.length + body.length;
        return name;
      },
      finish() {
        const out = parts.slice();
        let cdSize = 0;
        for (const e of entries) {
          const c = new DataView(new ArrayBuffer(46));
          c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint16(10, e.method, true);
          c.setUint16(12, dosTime, true); c.setUint16(14, dosDate, true); c.setUint32(16, e.crc, true); c.setUint32(20, e.comp, true); c.setUint32(24, e.size, true);
          c.setUint16(28, e.nameBytes.length, true); c.setUint32(42, e.offset, true);
          out.push(new Uint8Array(c.buffer), e.nameBytes);
          cdSize += 46 + e.nameBytes.length;
        }
        const end = new DataView(new ArrayBuffer(22));
        end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
        end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
        out.push(new Uint8Array(end.buffer));
        return out;
      },
    };
  }

  // ---- reports ------------------------------------------------------------------

  function stamp(d) {
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  }

  function buildErrorsMd(r) {
    const L = [`# Export problems`, '', `Project: ${r.projectName} (${r.projectUrl})`, `Exported: ${r.finishedAt}`, `Verdict: **${r.check.verdict}**`, ''];
    if (r.check.reasons.length) { L.push('## Why this export is not complete', ''); for (const x of r.check.reasons) L.push(`- ${x}`); L.push(''); }
    L.push(`## Errors (${r.errors.length})`, '', 'Something that was found but is NOT in the ZIP, or could not be read.', '');
    if (!r.errors.length) L.push('(none)', '');
    for (const e of r.errors) L.push(`- **${e.scope}** — ${e.item}`, `  - ${e.reason}`);
    L.push('', `## Warnings (${r.warnings.length})`, '', 'Saved, but not as the original, or something could not be cross-checked.', '');
    if (!r.warnings.length) L.push('(none)', '');
    for (const e of r.warnings) L.push(`- **${e.scope}** — ${e.item}`, `  - ${e.reason}`);
    L.push('', '## Not covered by this exporter', '', '- Project memory is read from the memory endpoint; compare project/memory.md with the project page once. Synced sources (GitHub, Drive) are listed but not downloaded.', '- Files in a code-execution container are only retrievable while claude.ai still keeps that container.', '- Chats shared with you, or project members\' chats you cannot open, are only listed if the list endpoints return them.', '');
    return L.join('\n');
  }

  function buildResultsLog(r) {
    const section = (title, items, fmt) => {
      const out = ['', `${title} (${items.length})`, '-'.repeat(60)];
      if (!items.length) out.push('(none)');
      for (const it of items) { const [a, b] = fmt(it); out.push(a, `    ${b}`); }
      return out;
    };
    const okChats = r.chats.filter(c => c.status === 'exported');
    const L = [
      'Claude Project ZIP Exporter - results log', '='.repeat(60),
      `Run started : ${r.startedAt}`, `Run finished: ${r.finishedAt} (${r.durationSec}s)`,
      `Input       : ${r.projectUrl}`, `Output      : ${r.zipName}`, `Verdict     : ${r.check.verdict}`, '',
      'SUMMARY', '-'.repeat(60),
      `Total items found        : ${r.check.chats.found + r.check.files.found} (${r.check.chats.found} chats, ${r.check.files.found} files)`,
      `Done this run            : ${r.check.chats.exported + r.check.files.saved} (${r.check.chats.exported} chats, ${r.check.files.saved} files)`,
      `Already done (skipped)   : 0`,
      `Skipped on purpose       : 0`,
      `Errors                   : ${r.errors.length}`,
      `Warnings                 : ${r.warnings.length}`,
      `Knowledge files          : found ${r.counts.knowledge.found}, saved ${r.counts.knowledge.saved}`,
      `Chat uploads             : found ${r.counts.uploads.found}, saved ${r.counts.uploads.saved}`,
      `Artifact versions        : found ${r.counts.artifacts.found}, saved ${r.counts.artifacts.saved}`,
      `Container files          : found ${r.counts.container_files.found}, saved ${r.counts.container_files.saved}`,
      `Requests / retries       : ${r.http.requests} / ${r.http.retries}`,
    ];
    L.push(...section('SUCCESSFUL: WRITTEN', okChats, c => [c.url, `${c.files.markdown} (${c.message_count} messages, ${c.attachment_count} attachments)`]));
    L.push(...section('SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT', [], () => ['', '']));
    L.push(...section('SKIPPED ON PURPOSE', [], () => ['', '']));
    L.push(...section('ERRORS', r.errors, e => [`${e.scope}: ${e.item}`, e.reason]));
    L.push(...section('WARNINGS', r.warnings, e => [`${e.scope}: ${e.item}`, e.reason]));
    return L.join('\n') + '\n';
  }

  // ===========================================================================
  // HTTP CLIENT: sequential, rate-limited, retry with backoff on 429 / 5xx
  // ===========================================================================

  class CancelError extends Error { constructor() { super('cancelled'); this.name = 'CancelError'; } }
  class HttpError extends Error {
    constructor(status, path, detail) { super(`HTTP ${status || 'network error'} for ${path}${detail ? ` (${detail})` : ''}`); this.name = 'HttpError'; this.status = status; }
  }

  function defaultSleep(ms, signal) {
    return new Promise((resolve, reject) => {
      if (signal && signal.aborted) return reject(new CancelError());
      const t = setTimeout(() => { if (signal) signal.removeEventListener('abort', onAbort); resolve(); }, ms);
      const onAbort = () => { clearTimeout(t); reject(new CancelError()); };
      if (signal) signal.addEventListener('abort', onAbort, { once: true });
    });
  }

  function createClient(o) {
    const sleep = o.sleep || defaultSleep;
    const minInterval = o.minIntervalMs == null ? 400 : o.minIntervalMs;
    const maxRetries = o.maxRetries == null ? 5 : o.maxRetries;
    const stats = { requests: 0, retries: 0 };
    let last = 0;
    async function request(path, as) {
      const url = new URL(path, o.origin);
      if (url.origin !== o.origin) throw new Error(`not fetched: ${url.origin} is a different origin (this script only talks to ${o.origin})`);
      for (let attempt = 0; ; attempt++) {
        if (o.signal && o.signal.aborted) throw new CancelError();
        const wait = last + minInterval - Date.now();
        if (wait > 0) await sleep(wait, o.signal);
        last = Date.now();
        stats.requests++;
        let res = null;
        let netErr = null;
        try {
          res = await o.fetchImpl(url.href, { method: 'GET', credentials: 'same-origin', headers: { Accept: as === 'json' ? 'application/json' : '*/*' }, signal: o.signal });
        } catch (e) {
          if (o.signal && o.signal.aborted) throw new CancelError();
          netErr = e;
        }
        if (res && res.ok) {
          if (as === 'json') {
            const text = await res.text();
            try { return JSON.parse(text); } catch (e) { throw new Error(`response for ${url.pathname} is not JSON (starts: ${JSON.stringify(text.slice(0, 60))})`); }
          }
          return { bytes: new Uint8Array(await res.arrayBuffer()), type: (res.headers.get('content-type') || '').toLowerCase() };
        }
        const status = res ? res.status : 0;
        const retryable = !res || status === 429 || status >= 500;
        if (!retryable || attempt >= maxRetries) throw new HttpError(status, url.pathname + url.search, netErr ? netErr.message : (attempt ? `after ${attempt} retries` : ''));
        stats.retries++;
        const ra = res ? Number(res.headers.get('retry-after')) : 0;
        const delay = ra > 0 ? Math.min(ra * 1000, 120000) : Math.min(1000 * 2 ** (attempt + 1), 60000);
        if (o.onRetry) o.onRetry({ status, path: url.pathname, attempt: attempt + 1, delay });
        await sleep(delay, o.signal);
      }
    }
    return { stats, getJSON: (p) => request(p, 'json'), getBytes: (p) => request(p, 'bytes') };
  }

  // ===========================================================================
  // EXPORT PIPELINE (no DOM; tested end to end in Node against a mock API)
  // ===========================================================================

  /**
   * @param {object} o  { fetchImpl, origin, projectId, signal?, memoryText?, memoryNone?,
   *                      onProgress?, sleep?, minIntervalMs?, maxRetries?, pageSize? }
   * @returns {Promise<{parts: Uint8Array[], zipName, counts, check, errors, warnings, manifest}>}
   */
  async function runExport(o) {
    const started = new Date();
    const origin = o.origin;
    const projectId = o.projectId;
    const projectUrl = `${origin}/project/${projectId}`;
    const errors = [];
    const warnings = [];
    const err = (scope, item, reason) => errors.push({ scope, item: String(item), reason: String(reason) });
    const warn = (scope, item, reason) => warnings.push({ scope, item: String(item), reason: String(reason) });
    const progress = (done, total, label) => { if (o.onProgress) o.onProgress({ done, total, label }); };
    const zip = createZip(started);
    const client = createClient({
      fetchImpl: o.fetchImpl, origin, signal: o.signal, sleep: o.sleep, minIntervalMs: o.minIntervalMs, maxRetries: o.maxRetries,
      onRetry: (r) => progress(null, null, `HTTP ${r.status || 'network error'} — retry ${r.attempt} in ${Math.round(r.delay / 1000)}s`),
    });
    const counts = {
      chats: { found: 0, exported: 0 }, knowledge: { found: 0, saved: 0 }, uploads: { found: 0, saved: 0 },
      artifacts: { found: 0, saved: 0 }, container_files: { found: 0, saved: 0 },
    };
    const flags = { cancelled: false, fatal: null, project: false, instructions: false, memory: 'missing', chatListing: false, knowledgeListing: false };
    const chatRows = [];
    const attachmentRows = [];
    const knowledgeRows = [];
    let project = null;
    let orgId = null;
    let projectName = projectId;
    const reCancel = (e) => { if (e instanceof CancelError) throw e; };
    const jsonText = (v) => JSON.stringify(v, null, 2);

    /** Try candidate URLs in order; first one that returns a real file wins. */
    async function fetchFirst(candidates, name) {
      const tried = [];
      for (const c of candidates) {
        try {
          const r = await client.getBytes(c.url);
          if (!r.bytes.length) { tried.push(`${redactUrl(c.url)}: empty response`); continue; }
          if (r.type.includes('text/html') && !/\.html?$/i.test(name || '')) { tried.push(`${redactUrl(c.url)}: got an HTML page instead of the file`); continue; }
          return { ...r, url: c.url, quality: c.quality, tried };
        } catch (e) { reCancel(e); tried.push(`${redactUrl(c.url)}: ${e.message}`); }
      }
      return { bytes: null, tried };
    }

    try {
      // ---- 1. organization + project ---------------------------------------
      progress(0, 1, 'Finding the project…');
      const orgs = asArray(await client.getJSON(EP.orgs()), 'organization list');
      const orgFailures = [];
      for (const org of orgs) {
        if (!org || !org.uuid) continue;
        try { project = await client.getJSON(EP.project(org.uuid, projectId)); orgId = org.uuid; break; }
        catch (e) { reCancel(e); orgFailures.push(e.message); }
      }
      if (!orgId || !project || typeof project !== 'object') throw new Error(`project ${projectId} was not readable in any of your ${orgs.length} organization(s): ${orgFailures.join('; ') || 'no organizations returned'}`);
      flags.project = true;
      projectName = typeof project.name === 'string' && project.name ? project.name : projectId;
      await zip.add('project/project.json', jsonText(project));

      if (typeof project.prompt_template === 'string') {
        flags.instructions = true;
        await zip.add('project/instructions.md', project.prompt_template);
        if (!project.prompt_template.trim()) warn('project', 'custom instructions', 'the prompt_template field is empty; confirm in the project that there really are no custom instructions');
      } else {
        err('project', 'custom instructions', `the project response has no text field "prompt_template" (fields: ${Object.keys(project).join(', ')}); instructions were NOT exported. Use capture mode and send the log.`);
      }

      // Project memory: GET memory?project_uuid=<id> returned { memory: string, project_memory_mode, ... } live.
      const memFields = findMemoryFields(project);
      let memErr = null;
      try {
        const m = await client.getJSON(EP.projectMemory(orgId, projectId));
        if (!m || typeof m !== 'object' || typeof m.memory !== 'string') throw new Error(`unexpected shape for project memory: ${describe(m)}`);
        await zip.add('project/memory.json', jsonText(m));
        if (m.memory.trim()) {
          flags.memory = 'fetched';
          await zip.add('project/memory.md', m.memory);
        } else {
          flags.memory = 'fetched_empty';
          warn('project', 'memory', `the memory endpoint answered with empty text (project_memory_mode: ${m.project_memory_mode}); confirm on the project page that it really has no memory`);
        }
        if (typeof o.memoryText === 'string' && o.memoryText.trim() && o.memoryText.trim() !== m.memory.trim()) {
          await zip.add('project/memory.pasted.md', o.memoryText);
          warn('project', 'memory', 'the memory you pasted differs from the memory the endpoint returned; both are in the ZIP (memory.md = endpoint, memory.pasted.md = pasted)');
        }
      } catch (e) { reCancel(e); memErr = e.message; }
      if (flags.memory === 'missing' && typeof o.memoryText === 'string' && o.memoryText.trim()) {
        flags.memory = 'pasted';
        await zip.add('project/memory.md', o.memoryText);
        warn('project', 'memory', `the memory endpoint failed (${memErr}); used the memory you pasted`);
      }
      if (flags.memory === 'missing' && Object.keys(memFields).length) {
        await zip.add('project/memory.unverified-fields.json', jsonText(memFields));
        if (flags.memory === 'missing') flags.memory = 'unverified_field';
        warn('project', 'memory', `saved the project fields whose name mentions memory (${Object.keys(memFields).join(', ')}) to project/memory.unverified-fields.json; whether this is the full project memory is unverified — compare with the project page`);
      }
      if (flags.memory === 'missing' && o.memoryNone) flags.memory = 'declared_none';
      if (flags.memory === 'missing') err('project', 'memory', `the memory endpoint failed (${memErr}). Copy the memory from the project page into the panel box and export again, or tick "this project has no memory".`);

      // ---- 2. knowledge files -------------------------------------------------
      progress(0, 1, 'Listing knowledge files…');
      let docs = [];
      let files = [];
      let listOk = true;
      try { const raw = await client.getJSON(EP.projectDocs(orgId, projectId)); await zip.add('raw/_project_docs.json', jsonText(raw)); docs = asArray(raw, 'project docs'); }
      catch (e) { reCancel(e); listOk = false; err('knowledge', 'docs list', e.message); }
      try { const raw = await client.getJSON(EP.projectFiles(orgId, projectId)); await zip.add('raw/_project_files.json', jsonText(raw)); files = asArray(raw, 'project files'); }
      catch (e) { reCancel(e); listOk = false; err('knowledge', 'files list', e.message); }
      // The project itself reports how many docs and files it has: an independent
      // check that neither list was cut short (seen live: docs_count, files_count).
      for (const [label, list, key] of [['docs', docs, 'docs_count'], ['files', files, 'files_count']]) {
        if (typeof project[key] !== 'number') { warn('knowledge', `${label} list`, `the project has no numeric ${key}, so the length of the ${label} list (${list.length}) could not be cross-checked`); continue; }
        if (listOk && list.length !== project[key]) { listOk = false; err('knowledge', `${label} list`, `the project says it has ${project[key]} ${label} but the list returned ${list.length}; some were NOT exported`); }
      }
      // Synced knowledge (GitHub, Drive...) is listed at projects/<id>/syncs. This exporter does not download it,
      // so a non-empty list must block "complete" instead of being silently left out.
      try {
        const raw = await client.getJSON(EP.projectSyncs(orgId, projectId));
        const syncs = asArray(raw, 'project syncs');
        await zip.add('raw/_project_syncs.json', jsonText(raw));
        if (syncs.length) { listOk = false; err('knowledge', 'synced sources', `the project has ${syncs.length} synced source(s) (e.g. GitHub or Drive); their files are NOT exported by this script. The list is in raw/_project_syncs.json.`); }
      } catch (e) { reCancel(e); listOk = false; err('knowledge', 'synced sources list', `could not check for synced sources: ${e.message}`); }
      flags.knowledgeListing = listOk;
      counts.knowledge.found = docs.length + files.length;
      const docByName = new Map();
      const BINARY_EXT = /\.(pdf|docx?|xlsx?|pptx?|odt|ods|odp|rtf|epub|png|jpe?g|gif|webp|bmp|tiff?|heic|zip|mp3|mp4|wav|mov)$/i;
      let kDone = 0;
      for (const d of docs) {
        progress(kDone++, counts.knowledge.found, `Knowledge: ${d && d.file_name ? d.file_name : 'document'}`);
        const name = (d && d.file_name) || `document-${String((d && d.uuid) || kDone).slice(0, 8)}`;
        const row = { scope: 'project_knowledge', source: 'docs', id: (d && d.uuid) || null, file_name: name, created: (d && d.created_at) || null, url: null, saved_as: null, zip_path: null, status: 'failed' };
        knowledgeRows.push(row);
        try {
          if (!d || typeof d.content !== 'string') throw new Error(`no text "content" field in the docs entry (fields: ${d ? Object.keys(d).join(', ') : 'none'})`);
          const extracted = BINARY_EXT.test(name);
          row.zip_path = await zip.add(`knowledge/${safeName(name)}${extracted ? '.extracted.txt' : ''}`, d.content);
          row.saved_as = extracted ? 'extracted_text' : 'text_content';
          row.status = 'saved';
          counts.knowledge.saved++;
          docByName.set(name.toLowerCase(), row);
          if (extracted) warn('knowledge', name, 'saved as extracted text only (the docs list holds text, not the original file)');
        } catch (e) { err('knowledge', name, e.message); }
      }
      for (const f of files) {
        const name = (f && f.file_name) || `file-${String((f && (f.file_uuid || f.uuid)) || kDone).slice(0, 8)}`;
        progress(kDone++, counts.knowledge.found, `Knowledge: ${name}`);
        const row = { scope: 'project_knowledge', source: 'files', id: (f && (f.file_uuid || f.uuid)) || null, file_name: name, created: (f && f.created_at) || null, url: null, saved_as: null, zip_path: null, status: 'failed' };
        knowledgeRows.push(row);
        try {
          const got = await fetchFirst(fileCandidates(orgId, f || {}), name);
          const twin = docByName.get(name.toLowerCase());
          if (got.bytes && got.quality !== 'thumbnail') {
            row.zip_path = await zip.add(`knowledge/${safeName(name)}`, got.bytes);
            row.saved_as = got.quality; row.url = got.url; row.status = 'saved';
            counts.knowledge.saved++;
            if (got.quality !== 'original') warn('knowledge', name, `saved from the ${got.quality} URL, which may not be the original bytes`);
          } else if (twin) {
            row.saved_as = 'extracted_text'; row.zip_path = twin.zip_path; row.status = 'saved';
            counts.knowledge.saved++;
            warn('knowledge', name, `original not retrievable (${got.tried.join(' | ') || 'no download URL in the files entry'}); the extracted text is in ${twin.zip_path}`);
          } else {
            throw new Error(`no downloadable original and no extracted text: ${got.tried.join(' | ') || `no download URL in the files entry (fields: ${f ? Object.keys(f).join(', ') : 'none'})`}`);
          }
        } catch (e) { reCancel(e); err('knowledge', name, e.message); }
      }
      await zip.add('knowledge/_index.json', jsonText(knowledgeRows));

      // ---- 3. list the project's chats from two independent sources ------------
      progress(0, 1, 'Listing chats…');
      const found = new Map();
      const note = (c, source) => {
        if (!c || !c.uuid) return false;
        const cur = found.get(c.uuid);
        if (cur) { cur.sources.add(source); return false; }
        found.set(c.uuid, { item: c, sources: new Set([source]) });
        return true;
      };
      let aOk = false;
      let bOk = false;
      let aCount = 0;
      let aPaged = false;
      const addA = (list) => { for (const c of list) { if (c && c.uuid) { if (note(c, 'project_conversations')) aCount++; } else err('chat list', 'project conversations', `an entry has no uuid: ${describe(c)}`); } };
      // Preferred: conversations_v2, the project page's own call. It pages and reports pagination.total.
      try {
        const limit = o.v2PageSize || 30;
        let total = null;
        for (let offset = 0, page = 0; ; page++) {
          if (page > 2000) throw new Error('gave up after 2000 pages');
          const raw = await client.getJSON(EP.projectChatsV2(orgId, projectId, limit, offset));
          const list = asArray(raw, 'project conversations (v2)');
          if (raw && raw.pagination && typeof raw.pagination.total === 'number') total = raw.pagination.total;
          addA(list);
          offset += list.length;
          const more = raw && raw.pagination ? raw.pagination.has_more === true : false;
          if (!list.length || !more) break;
        }
        if (total !== null && aCount !== total) throw new Error(`conversations_v2 says total ${total} but ${aCount} distinct chats came back`);
        aOk = true; aPaged = true;
      } catch (e) {
        reCancel(e);
        warn('chat list', 'project conversations_v2 endpoint', `${e.message}; falling back to the older unpaged endpoint`);
        try {
          addA(asArray(await client.getJSON(EP.projectChats(orgId, projectId)), 'project conversations'));
          aOk = true;
        } catch (e2) { reCancel(e2); warn('chat list', 'project conversations endpoint', e2.message); }
      }

      const pageSize = o.pageSize || 100;
      const seenAll = new Set();
      let bWithProject = 0;
      let bMatches = 0;
      try {
        for (let offset = 0, page = 0; ; page++) {
          if (page > 2000) throw new Error('gave up after 2000 pages');
          progress(null, null, `Listing all chats to cross-check… ${seenAll.size}`);
          const list = asArray(await client.getJSON(EP.allChats(orgId, pageSize, offset)), 'conversation list');
          let fresh = 0;
          for (const c of list) {
            if (!c || !c.uuid || seenAll.has(c.uuid)) continue;
            seenAll.add(c.uuid); fresh++;
            const pid = c.project_uuid || (c.project && c.project.uuid) || null;
            if (pid) bWithProject++;
            if (pid === projectId) { bMatches++; note(c, 'conversation_list'); }
          }
          if (!list.length || !fresh) break; // an empty page, or the server ignored the offset
          offset += list.length; // advance by what came back: the server may cap the page size
        }
        bOk = true;
      } catch (e) { reCancel(e); warn('chat list', 'full conversation list (cross-check)', e.message); }

      const bUsable = bOk && (bWithProject > 0 || seenAll.size === 0);
      if (bOk && !bUsable) warn('chat list', 'cross-check', `none of the ${seenAll.size} entries in the full conversation list carries a project id, so it could not confirm the project list`);
      flags.chatListing = aOk || bUsable;
      if (!flags.chatListing) err('chat list', projectUrl, 'neither the project conversation list nor the full conversation list could be used; no chats were exported');
      if (aOk && !aPaged && !bUsable) warn('chat list', 'pagination', `the project conversations endpoint returned ${aCount} chats in one response; whether it pages is unverified and the cross-check was not available. Compare this number with the project page.`);
      if (aOk && bUsable) {
        const onlyA = [...found.values()].filter(x => !x.sources.has('conversation_list')).length;
        const onlyB = [...found.values()].filter(x => !x.sources.has('project_conversations')).length;
        if (onlyA || onlyB) warn('chat list', 'the two lists disagree', `${onlyA} chat(s) only in the project list, ${onlyB} only in the full list; all of them were exported`);
      }
      counts.chats.found = found.size;
      await zip.add('raw/_conversation_list.json', jsonText([...found.values()].map(x => ({ ...x.item, _found_in: [...x.sources] }))));

      // ---- 4. each chat; one failure never stops the rest ------------------------
      const usedBases = new Set();
      let n = 0;
      for (const [uuid, entry] of found) {
        n++;
        const listItem = entry.item;
        const url = `${origin}/chat/${uuid}`;
        progress(n - 1, found.size, `Chat ${n}/${found.size}: ${listItem.name || 'Untitled'}`);
        const row = {
          id: uuid, title: listItem.name || 'Untitled', url, created: listItem.created_at || null, updated: listItem.updated_at || null,
          message_count: null, attachment_count: 0, artifact_count: 0, container_file_count: 0, found_in: [...entry.sources], status: 'failed', files: { markdown: null, raw: null },
        };
        chatRows.push(row);
        try {
          const conv = await client.getJSON(EP.chat(orgId, uuid));
          if (!conv || typeof conv !== 'object' || !Array.isArray(conv.chat_messages)) throw new Error(`conversation response has no chat_messages list: ${describe(conv)}`);
          if (!conv.uuid) conv.uuid = uuid;
          row.title = conv.name || row.title; row.created = conv.created_at || row.created; row.updated = conv.updated_at || row.updated;
          row.message_count = conv.chat_messages.length;
          const pid = conv.project_uuid || (conv.project && conv.project.uuid);
          if (pid && pid !== projectId) warn('chat', url, `the conversation says it belongs to project ${pid}, not this one; exported anyway`);
          const base = chatBaseName({ uuid, name: row.title, created_at: row.created }, usedBases);
          row.files.raw = await zip.add(`raw/${base}.json`, jsonText(conv));
          const plan = planChatFiles(conv, base);
          row.attachment_count = plan.uploads.length;
          row.artifact_count = plan.artifacts.length;
          counts.uploads.found += plan.uploads.length;
          counts.artifacts.found += plan.artifacts.length;
          const rowBase = { chat_id: uuid, chat_title: row.title, chat_url: url, message_count: row.message_count };

          for (const u of plan.uploads) {
            u.saved = false;
            try {
              if (u.text !== null) { u.path = await zip.add(u.path, u.text); u.saved_as = 'extracted_text'; u.saved = true; }
              else if (u.file) {
                const got = await fetchFirst(fileCandidates(orgId, u.file), u.title);
                if (got.bytes && got.quality !== 'thumbnail') {
                  u.path = await zip.add(u.path, got.bytes); u.saved_as = got.quality; u.source_url = got.url; u.saved = true;
                  if (got.quality !== 'original') warn('attachment', `${url} — ${u.title}`, `saved from the ${got.quality} URL, which may not be the original bytes`);
                } else throw new Error(got.bytes ? 'only a thumbnail was available' : (got.tried.join(' | ') || `no download URL in the file entry (fields: ${Object.keys(u.file).join(', ')})`));
              } else throw new Error('the attachment entry has no extracted_content and no file reference');
            } catch (e) { reCancel(e); u.error = e.message; err('attachment', `${url} — ${u.title}`, e.message); }
            if (u.saved) counts.uploads.saved++;
          }
          for (const a of plan.artifacts) {
            a.saved = false;
            try { a.path = await zip.add(a.path, a.text); a.saved = true; counts.artifacts.saved++; if (a.problem) warn('artifact', `${url} — ${a.title} v${a.version}`, a.problem); }
            catch (e) { a.error = e.message; err('artifact', `${url} — ${a.title} v${a.version}`, e.message); }
          }

          // Files in the chat's code-execution container (where the site still exposes them).
          const container = [];
          const wantContainer = (conv.settings && conv.settings.enabled_monkeys_in_a_barrel) || conv.is_wiggle_enabled === true || plan.presented.length > 0;
          if (wantContainer) {
            const paths = new Map(plan.presented.map(p => [p.path, p.mime_type]));
            // An empty prefix was seen live to return nothing while files existed,
            // so the two user-data folders are listed as well.
            const listFailures = [];
            for (const prefix of ['', '/mnt/user-data/outputs', '/mnt/user-data/uploads']) {
              try {
                const listed = await client.getJSON(EP.containerList(orgId, uuid, prefix));
                const meta = listed && Array.isArray(listed.files_metadata) ? listed.files_metadata : null;
                if (!meta) throw new Error(`unexpected list-files response: ${describe(listed)}`);
                for (const f of meta) if (f && typeof f.path === 'string' && !paths.has(f.path)) paths.set(f.path, f.content_type || null);
              } catch (e) { reCancel(e); listFailures.push(`prefix "${prefix}": ${e.message}`); }
            }
            if (listFailures.length) warn('container', url, `could not fully list the code-execution container (${listFailures.join(' | ')}); files named in the transcript were still attempted`);
            for (const [p, mime] of paths) {
              const c = { kind: 'container_file', source_path: p, mime_type: mime, saved: false, path: uniqueName(`${plan.dir}/container/${safePath(p)}`, plan.used) };
              container.push(c);
              counts.container_files.found++;
              try {
                const r = await client.getBytes(EP.containerFile(orgId, uuid, p));
                c.path = await zip.add(c.path, r.bytes); c.saved = true; counts.container_files.saved++;
              } catch (e) { reCancel(e); c.error = e.message; err('container file', `${url} — ${p}`, e.message); }
            }
          }
          row.container_file_count = container.length;

          const uploadsByMessage = new Map();
          for (const u of plan.uploads) { if (!uploadsByMessage.has(u.message_uuid)) uploadsByMessage.set(u.message_uuid, []); uploadsByMessage.get(u.message_uuid).push(u); }
          const artifactByBlock = new Map();
          const msgByUuid = new Map(conv.chat_messages.map(m => [m.uuid, m]));
          for (const a of plan.artifacts) { const m = msgByUuid.get(a.message_uuid); if (m && Array.isArray(m.content)) artifactByBlock.set(m.content[a.block_index], a); }
          const out = renderChat(conv, { url, projectName, projectId, attachmentCount: plan.uploads.length, uploadsByMessage, artifactByBlock, containerFiles: container, exportedAt: started.toISOString() });
          if (out.rendered !== conv.chat_messages.length) throw new Error(`transcript has ${out.rendered} messages but the conversation has ${conv.chat_messages.length}`);
          row.files.markdown = await zip.add(`chats/${base}.md`, out.markdown);
          row.status = 'exported';
          counts.chats.exported++;

          for (const x of [...plan.uploads, ...plan.artifacts, ...container]) {
            attachmentRows.push({
              ...rowBase, scope: 'chat', attachment_id: x.id || x.source_path, kind: x.kind, title: x.title || x.source_path,
              version: x.version || null, message_id: x.message_uuid || null, url: x.source_url ? new URL(x.source_url, origin).href : null,
              created: x.created || row.created, updated: x.updated || row.updated, file_type: x.file_type || x.mime_type || null,
              saved_as: x.saved ? (x.saved_as || (x.kind === 'artifact' ? 'artifact_text' : 'original')) : null, zip_path: x.saved ? x.path : null,
              status: x.saved ? 'saved' : 'failed', error: x.error || null,
              chat_attachment_count: plan.uploads.length + plan.artifacts.length + container.length,
            });
          }
        } catch (e) {
          reCancel(e);
          row.error = e.message;
          err('chat', `${url} — ${row.title}`, e.message);
        }
      }
      progress(found.size, found.size, 'Writing the ZIP…');
    } catch (e) {
      if (e instanceof CancelError) flags.cancelled = true;
      else { flags.fatal = e.message; err('export', projectUrl, e.message); }
    }

    // ---- 5. reports: always written, even after a cancel or a fatal error ---------
    for (const k of knowledgeRows) {
      attachmentRows.push({
        chat_id: null, chat_title: null, chat_url: null, message_count: null, scope: 'project_knowledge', attachment_id: k.id, kind: `knowledge_${k.source}`,
        title: k.file_name, version: null, message_id: null, url: k.url ? new URL(k.url, origin).href : projectUrl, created: k.created, updated: k.created,
        file_type: null, saved_as: k.saved_as, zip_path: k.zip_path, status: k.status, error: null, chat_attachment_count: null,
      });
    }
    for (const a of attachmentRows) a.total_attachment_count = attachmentRows.length;
    const check = checkCounts(counts, flags, errors.length, warnings.length);
    const finished = new Date();
    const zipName = `${safeName(slugify(projectName))}-${stamp(started)}${check.complete ? '' : '-INCOMPLETE'}.zip`;
    const report = {
      projectName, projectUrl, startedAt: started.toISOString(), finishedAt: finished.toISOString(),
      durationSec: Math.round((finished - started) / 1000), zipName, check, counts, errors, warnings, chats: chatRows, http: client.stats,
    };
    const manifest = {
      exporter: { name: 'Claude Project ZIP Exporter', version: VERSION },
      exported_at: finished.toISOString(),
      project: { id: projectId, name: projectName, url: projectUrl, organization_id: orgId, created: project && project.created_at || null, updated: project && project.updated_at || null },
      verdict: check.verdict, complete: check.complete, incomplete_reasons: check.reasons,
      counts: { chats: check.chats, files: check.files, detail: counts, errors: errors.length, warnings: warnings.length },
      project_texts: { instructions: flags.instructions ? 'project/instructions.md' : null, memory: flags.memory },
      knowledge: knowledgeRows,
      chats: chatRows,
    };
    const tail = [
      ['_manifest.json', jsonText(manifest)], ['chat_db.json', jsonText(chatRows)], ['attachment_db.json', jsonText(attachmentRows)],
      ['_errors.md', buildErrorsMd(report)], [`results-log-${stamp(started)}.txt`, buildResultsLog(report)],
    ];
    for (const [name, text] of tail) {
      try { await zip.add(name, text); } catch (e) { errors.push({ scope: 'zip', item: name, reason: e.message }); }
    }
    return { parts: zip.finish(), zipName, counts, check: checkCounts(counts, flags, errors.length, warnings.length), errors, warnings, manifest, flags };
  }

  const api = {
    VERSION, EP, slugify, safeName, safePath, uniqueName, dateOf, chatBaseName, fence, yamlFrontmatter, asArray, shapeOf, redactUrl,
    findMemoryFields, isRelevantApi, activeBranch, planChatFiles, fileCandidates, renderBlock, renderChat, checkCounts, crc32, createZip,
    buildErrorsMd, buildResultsLog, createClient, runExport, CancelError, HttpError,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  // ===========================================================================
  // BROWSER: capture mode
  // Logs which /api/ requests the page itself makes and the SHAPE of each JSON
  // response (keys and types, no values), so unverified endpoints can be found.
  // ===========================================================================
  const CAPTURE_KEY = 'cpe.capture';
  const CAPTURE_ALL_KEY = 'cpe.capture.all';
  /** Capture only what an export could use: the org list, projects, chats, files, memory, containers. Billing, usage, account and ads are noise. */
  function isRelevantApi(pathname) {
    return /^\/api\/organizations$/.test(pathname)
      || /\/(projects|projects_v2|chat_conversations|chat_conversations_v2|conversations|memory|melange|files|docs|syncs|kb|wiggle|artifacts|user_artifacts)(\/|$)/.test(pathname);
  }
  const capture = { on: false, entries: new Map(), rawUrls: new Map(), listeners: new Set() };
  const lsGet = (k) => { try { return window.localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { v == null ? window.localStorage.removeItem(k) : window.localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } };

  function captureRecord(method, url, status, contentType, shape, via) {
    let abs;
    try { abs = new URL(url, location.origin); } catch (e) { return; }
    if (abs.origin !== location.origin || !abs.pathname.startsWith('/api/') || /^\/api\/(v2\/rum|event_logging)\b/.test(abs.pathname)) return; // telemetry is noise
    if (!isRelevantApi(abs.pathname) && lsGet(CAPTURE_ALL_KEY) !== '1') return;
    const key = `${method} ${redactUrl(abs.href)}`;
    const prev = capture.entries.get(key);
    if (prev && (prev.shape !== undefined || shape === undefined)) { prev.count++; return; }
    if (capture.entries.size >= 400 && !prev) return;
    capture.entries.set(key, { method, url: redactUrl(abs.href), status, content_type: contentType, via, count: (prev ? prev.count : 0) + 1, shape });
    capture.rawUrls.set(key, abs.pathname + abs.search);
    capture.listeners.forEach(fn => fn());
  }

  function installCapture() {
    if (capture.on) return;
    capture.on = true;
    const origFetch = window.fetch;
    if (typeof origFetch === 'function') {
      window.fetch = function (input, init) {
        const p = origFetch.apply(this, arguments);
        try {
          const url = typeof input === 'string' ? input : (input && input.url) || String(input);
          const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
          p.then((res) => {
            const ct = (res.headers.get('content-type') || '').split(';')[0];
            if (ct === 'application/json') res.clone().json().then(j => captureRecord(method, url, res.status, ct, shapeOf(j), 'fetch'), () => captureRecord(method, url, res.status, ct, undefined, 'fetch'));
            else captureRecord(method, url, res.status, ct, undefined, 'fetch');
          }, () => {});
        } catch (e) { /* never break the page */ }
        return p;
      };
    }
    const XO = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      try {
        this.addEventListener('load', () => {
          try {
            const ct = (this.getResponseHeader('content-type') || '').split(';')[0];
            let shape;
            if (ct === 'application/json' && (this.responseType === '' || this.responseType === 'text')) shape = shapeOf(JSON.parse(this.responseText));
            captureRecord(String(method).toUpperCase(), String(url), this.status, ct, shape, 'xhr');
          } catch (e) { /* ignore */ }
        });
      } catch (e) { /* ignore */ }
      return XO.apply(this, arguments);
    };
    // Works even when the manager runs this script outside the page context
    // (then the hooks above see nothing): URLs only, method unknown.
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) if (e.name.includes('/api/')) captureRecord('?', e.name, e.responseStatus || null, null, undefined, 'performance');
      }).observe({ type: 'resource', buffered: true });
    } catch (e) { /* not supported */ }
  }

  /** For URLs seen without a body: GET them once ourselves to learn the shape. User-triggered only. */
  async function captureProbe(setStatus) {
    const client = createClient({ fetchImpl: window.fetch.bind(window), origin: location.origin, maxRetries: 1 });
    const todo = [...capture.entries].filter(([k, v]) => v.shape === undefined && (v.method === '?' || v.method === 'GET') && !/completion|event|stream/i.test(v.url));
    let i = 0;
    for (const [key, v] of todo) {
      setStatus(`Probing ${++i}/${todo.length}…`);
      try { v.shape = shapeOf(await client.getJSON(capture.rawUrls.get(key))); v.via += '+probe'; }
      catch (e) { v.probe_error = e.message.replace(UUID_RE_G, '{uuid}'); }
    }
    setStatus(`Probed ${todo.length} URL(s).`);
    capture.listeners.forEach(fn => fn());
  }

  if (lsGet(CAPTURE_KEY) === '1') installCapture();

  // ===========================================================================
  // BROWSER: floating button and panel (shadow DOM, no innerHTML)
  // ===========================================================================
  const projectIdFromLocation = () => { const m = /^\/project\/([0-9a-f-]{36})(?:\/|$)/i.exec(location.pathname); return m ? m[1].toLowerCase() : null; };

  function el(tag, props, children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === 'style') n.style.cssText = v; else if (k === 'text') n.textContent = v; else if (k.startsWith('on')) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
    }
    for (const c of children || []) n.append(c);
    return n;
  }

  function buildUi() {
    const host = el('div', { id: 'cpe-host', style: 'position:fixed;right:16px;bottom:16px;z-index:2147483647;font:13px/1.4 system-ui,sans-serif;' });
    const root = host.attachShadow({ mode: 'open' });
    root.append(el('style', { text: `
      *{box-sizing:border-box} button{font:inherit;cursor:pointer;border-radius:8px;border:1px solid #8886;padding:6px 10px;background:#fff;color:#111}
      button.primary{background:#c2410c;color:#fff;border-color:#c2410c;font-weight:600;padding:10px 14px;box-shadow:0 2px 8px #0004}
      button:disabled{opacity:.5;cursor:default}
      .panel{width:min(420px,calc(100vw - 32px));max-height:calc(100vh - 90px);overflow:auto;background:#fff;color:#111;border:1px solid #8886;border-radius:12px;padding:12px;margin-bottom:8px;box-shadow:0 6px 24px #0005}
      .row{display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap} .right{display:flex;justify-content:flex-end}
      progress{width:100%;height:14px} textarea{width:100%;font:12px/1.3 ui-monospace,monospace;border:1px solid #8886;border-radius:6px;padding:6px;background:#fff;color:#111}
      table{border-collapse:collapse;width:100%;margin:6px 0} td,th{border:1px solid #8884;padding:3px 6px;text-align:left} td.bad{background:#fee2e2;font-weight:600}
      .verdict{font-weight:700;padding:6px 8px;border-radius:6px;margin:6px 0} .ok{background:#dcfce7;color:#14532d} .warn{background:#fef9c3;color:#713f12} .bad{background:#fee2e2;color:#7f1d1d}
      .muted{color:#555;font-size:12px} h3{margin:0 0 6px;font-size:14px} label{display:flex;gap:6px;align-items:flex-start}
    ` }));
    const status = el('div', { class: 'muted', text: 'Ready.' });
    const bar = el('progress', { max: '1', value: '0' });
    const memory = el('textarea', { rows: '4', placeholder: 'Project memory is read automatically. Paste the memory text from the project page here only as a fallback if that fails (optional).' });
    const noMemory = el('input', { type: 'checkbox' });
    const result = el('div');
    const startBtn = el('button', { class: 'primary', text: 'Start export' });
    const cancelBtn = el('button', { text: 'Cancel', disabled: '' });
    const capAll = el('input', { type: 'checkbox' });
    const capToggle = el('input', { type: 'checkbox' });
    capToggle.checked = lsGet(CAPTURE_KEY) === '1';
    const capOut = el('textarea', { rows: '6', readonly: '', style: 'display:none' });
    const capStatus = el('span', { class: 'muted' });
    const capBtns = el('div', { class: 'row', style: 'display:none' });
    const panel = el('div', { class: 'panel', style: 'display:none' }, [
      el('h3', { text: `Export project ZIP (v${VERSION})` }),
      el('div', { class: 'muted', text: 'Reads this project with your open session, same-origin only. Keep this tab open until the download starts.' }),
      el('div', { class: 'row' }, [memory]),
      el('label', { class: 'muted' }, [noMemory, el('span', { text: 'This project has no memory (I checked the project page).' })]),
      el('div', { class: 'row' }, [startBtn, cancelBtn]),
      bar, status, result,
      el('hr'),
      el('label', { class: 'muted' }, [capToggle, el('span', { text: 'Capture mode: log the /api/ requests this page makes and the shape of each response (keys and types only, ids removed). Reload the page after switching it on.' })]),
      el('label', { class: 'muted' }, [capAll, el('span', { text: 'Also log unrelated requests (billing, usage, account). Off by default; reload after changing.' })]),
      capBtns, capOut,
    ]);
    capAll.checked = lsGet(CAPTURE_ALL_KEY) === '1';
    capAll.addEventListener('change', () => lsSet(CAPTURE_ALL_KEY, capAll.checked ? '1' : null));
    const refreshCapture = () => {
      capOut.value = JSON.stringify({ exporter: VERSION, page: redactUrl(location.href), captured: [...capture.entries.values()] }, null, 2);
      capStatus.textContent = `${capture.entries.size} request(s) captured`;
    };
    capBtns.append(
      el('button', { text: 'Copy capture log', onclick: async () => { refreshCapture(); try { await navigator.clipboard.writeText(capOut.value); capStatus.textContent = 'Copied.'; } catch (e) { capOut.select(); capStatus.textContent = 'Select all in the box and copy.'; } } }),
      el('button', { text: 'Probe URLs without a body', onclick: () => captureProbe((t) => { capStatus.textContent = t; }) }),
      el('button', { text: 'Clear', onclick: () => { capture.entries.clear(); capture.rawUrls.clear(); refreshCapture(); } }),
      capStatus,
    );
    const showCapture = () => { const on = capToggle.checked; capOut.style.display = on ? '' : 'none'; capBtns.style.display = on ? '' : 'none'; if (on) refreshCapture(); };
    capToggle.addEventListener('change', () => { lsSet(CAPTURE_KEY, capToggle.checked ? '1' : null); if (capToggle.checked) installCapture(); showCapture(); });
    capture.listeners.add(() => { if (capToggle.checked) refreshCapture(); });
    showCapture();

    const openBtn = el('button', { class: 'primary', text: 'Export project ZIP', onclick: () => { panel.style.display = panel.style.display === 'none' ? '' : 'none'; } });
    root.append(panel, el('div', { class: 'right' }, [openBtn]));

    let controller = null;
    const setBusy = (busy) => { startBtn.disabled = busy; cancelBtn.disabled = !busy; memory.disabled = busy; noMemory.disabled = busy; };
    cancelBtn.addEventListener('click', () => { if (controller) { controller.abort(); status.textContent = 'Cancelling… the partial ZIP will still download.'; } });
    startBtn.addEventListener('click', async () => {
      const projectId = projectIdFromLocation();
      if (!projectId) { status.textContent = 'Open a project page (claude.ai/project/…) first.'; return; }
      controller = new AbortController();
      setBusy(true);
      result.replaceChildren();
      bar.removeAttribute('value');
      try {
        const out = await runExport({
          fetchImpl: window.fetch.bind(window), origin: location.origin, projectId, signal: controller.signal,
          memoryText: memory.value, memoryNone: noMemory.checked,
          onProgress: (p) => { if (p.total) { bar.max = p.total; bar.value = p.done; } if (p.label) status.textContent = p.label; },
        });
        const blob = new Blob(out.parts, { type: 'application/zip' });
        const url = URL.createObjectURL(blob);
        const a = el('a', { href: url, download: out.zipName, style: 'display:none' });
        document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 120000);
        bar.max = 1; bar.value = 1;
        status.textContent = `Downloaded ${out.zipName} (${(blob.size / 1048576).toFixed(1)} MB).`;
        showResult(out);
      } catch (e) {
        status.textContent = `Export failed before a ZIP could be written: ${e.message}`;
        result.replaceChildren(el('div', { class: 'verdict bad', text: 'FAILED — nothing was downloaded. Do not delete the project.' }));
      } finally { setBusy(false); controller = null; }
    });

    function showResult(out) {
      const c = out.counts;
      const rows = [
        ['Chats', c.chats.found, c.chats.exported], ['Files (all kinds)', out.check.files.found, out.check.files.saved],
        ['— knowledge files', c.knowledge.found, c.knowledge.saved], ['— chat uploads', c.uploads.found, c.uploads.saved],
        ['— artifact versions', c.artifacts.found, c.artifacts.saved], ['— container files', c.container_files.found, c.container_files.saved],
      ];
      const table = el('table', {}, [el('tr', {}, [el('th', { text: '' }), el('th', { text: 'Found' }), el('th', { text: 'In ZIP' })])]);
      for (const [label, f, s] of rows) table.append(el('tr', {}, [el('td', { text: label }), el('td', { text: String(f) }), el('td', { text: String(s), class: f === s ? '' : 'bad' })]));
      const cls = out.check.verdict === 'COMPLETE' ? 'ok' : out.check.complete ? 'warn' : 'bad';
      const text = out.check.complete
        ? `${out.check.verdict}: every chat and file that was found is in the ZIP.${out.warnings.length ? ` Read the ${out.warnings.length} warning(s) in _errors.md before deleting anything.` : ''}`
        : 'INCOMPLETE — do not delete the project. The ZIP is missing something:';
      const kids = [el('div', { class: `verdict ${cls}`, text }), table];
      if (!out.check.complete) { const ul = el('ul'); for (const r of out.check.reasons) ul.append(el('li', { text: r })); kids.push(ul); }
      kids.push(el('div', { class: 'muted', text: `${out.errors.length} error(s), ${out.warnings.length} warning(s). Details are in _errors.md inside the ZIP.` }));
      result.replaceChildren(...kids);
    }
    return host;
  }

  let ui = null;
  function sync() {
    if (!document.body) return;
    const onProject = !!projectIdFromLocation();
    if (onProject && !ui) ui = buildUi();
    if (ui) {
      if (onProject && !ui.isConnected) document.body.append(ui);
      ui.style.display = onProject ? '' : 'none';
    }
  }
  // claude.ai is a single-page app: the script loads once, so watch the URL.
  const boot = () => { sync(); setInterval(sync, 1000); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
})();
