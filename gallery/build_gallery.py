# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Scan this folder (and subfolders) for images/videos and write index.html.

Usage:  uv run build_gallery.py [folder]
Default folder is the one containing this script. Double-click index.html to view.
"""
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".svg"}
VIDEO = {".mp4", ".webm", ".mov", ".m4v", ".ogv"}


def scan(root: Path):
    items = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or not p.is_file():
            continue
        ext = p.suffix.lower()
        kind = "image" if ext in IMAGE else "video" if ext in VIDEO else None
        if not kind:
            continue
        st = p.stat()
        items.append({
            "src": "/".join(quote(part) for part in rel.parts),
            "name": p.name,
            "folder": "/".join(rel.parts[:-1]) or "(root)",
            "kind": kind,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
        })
    return items


PAGE = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--card:#f4f4f5;--mute:#666;--on:#1a1a1a;--onfg:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--card:#1c1c1e;--mute:#999;--on:#eee;--onfg:#111}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
h1{font-size:18px;margin:0 0 12px}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;align-items:center}
button,input{font:inherit;color:inherit;background:var(--card);border:1px solid transparent;border-radius:999px;padding:5px 12px;cursor:pointer}
button.on{background:var(--on);color:var(--onfg)}
input{cursor:text;min-width:180px}
.count{color:var(--mute);margin:4px 0 12px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
article{background:var(--card);border-radius:8px;overflow:hidden}
img,video{display:block;width:100%;max-height:420px;object-fit:contain;background:#000}
img{cursor:zoom-in}
.meta{padding:10px 12px}
.meta b{overflow-wrap:anywhere}
small{display:block;color:var(--mute);overflow-wrap:anywhere}
#lb{position:fixed;inset:0;background:#000d;display:none;align-items:center;justify-content:center;cursor:zoom-out}
#lb img{max-width:96vw;max-height:96vh;width:auto;cursor:zoom-out}
</style>
<h1>__TITLE__</h1>
<div class="bar" id="types"></div>
<div class="bar" id="folders"></div>
<div class="bar" id="sorts"><input id="q" placeholder="Search filename…"></div>
<div class="count" id="count"></div>
<main id="grid"></main>
<div id="lb"><img alt=""></div>
<script>
const ITEMS = __DATA__;
const st = {type:"all", folder:"all", sort:"newest", q:""};
const $ = id => document.getElementById(id);
const fmt = n => n>1e9 ? (n/1e9).toFixed(1)+" GB" : n>1e6 ? (n/1e6).toFixed(1)+" MB" : Math.max(1,Math.round(n/1e3))+" KB";
const folders = [...new Set(ITEMS.map(i => i.folder))].sort();
const sorts = {newest:(a,b)=>b.mtime-a.mtime, oldest:(a,b)=>a.mtime-b.mtime, name:(a,b)=>a.name.localeCompare(b.name), size:(a,b)=>b.size-a.size};

function buttons(el, key, opts){
  el.querySelectorAll("button").forEach(b=>b.remove());
  opts.forEach(([val,label])=>{
    const b = document.createElement("button");
    b.textContent = label; if(st[key]===val) b.className="on";
    b.onclick = ()=>{st[key]=val; render();};
    el.insertBefore(b, el.querySelector("input"));
  });
}
function render(){
  buttons($("types"), "type", [["all","All"],["image","Images"],["video","Videos"]]);
  buttons($("folders"), "folder", [["all","All folders"],...folders.map(f=>[f,f])]);
  buttons($("sorts"), "sort", [["newest","Newest"],["oldest","Oldest"],["name","Name"],["size","Size"]]);
  const q = st.q.toLowerCase();
  const list = ITEMS.filter(i => (st.type==="all"||i.kind===st.type) && (st.folder==="all"||i.folder===st.folder) && i.name.toLowerCase().includes(q)).sort(sorts[st.sort]);
  $("count").textContent = list.length + " of " + ITEMS.length + " items";
  const g = $("grid"); g.textContent = "";
  for(const i of list){
    const a = document.createElement("article");
    const m = document.createElement(i.kind==="video"?"video":"img");
    m.src = i.src;
    if(i.kind==="video"){m.controls=true; m.preload="metadata";}
    else {m.loading="lazy"; m.alt=i.name; m.onclick=()=>{$("lb").firstChild.src=i.src; $("lb").style.display="flex";};}
    const d = document.createElement("div"); d.className="meta";
    const t = new Date(i.mtime*1000).toISOString().slice(0,16).replace("T"," ");
    d.innerHTML = "<b></b><small></small><small></small>";
    d.children[0].textContent = i.name;
    d.children[1].textContent = i.folder;
    d.children[2].textContent = t + " · " + fmt(i.size);
    a.append(m,d); g.append(a);
  }
}
$("q").oninput = e => {st.q = e.target.value; const s=e.target.selectionStart; render(); const q=$("q"); q.focus(); q.setSelectionRange(s,s);};
$("lb").onclick = () => $("lb").style.display = "none";
document.onkeydown = e => {if(e.key==="Escape") $("lb").style.display="none";};
render();
</script>
"""


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    items = scan(root)
    title = f"Gallery · {root.name} · {datetime.now():%Y-%m-%d %H:%M}"
    data = json.dumps(items).replace("</", "<\\/")
    out = PAGE.replace("__TITLE__", html.escape(title)).replace("__DATA__", data)
    (root / "index.html").write_text(out, encoding="utf-8")
    print(f"Wrote {root / 'index.html'} ({len(items)} items)")


if __name__ == "__main__":
    main()
