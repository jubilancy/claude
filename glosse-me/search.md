---
layout: page
title: Search
permalink: /search/
---
<input id="q" type="search" placeholder="Search posts and tags…" autofocus>
<p id="count"></p>
<ul id="results" class="archive"></ul>
<script>
(function () {
  var q = document.getElementById('q'), out = document.getElementById('results'), count = document.getElementById('count'), data = [];
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function run() {
    var terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { out.innerHTML = ''; count.textContent = ''; return; }
    var hits = data.filter(function (p) {
      var hay = (p.title + ' ' + p.tags.join(' ') + ' ' + p.text).toLowerCase();
      return terms.every(function (t) { return hay.indexOf(t) !== -1; });
    });
    count.textContent = hits.length + ' result' + (hits.length === 1 ? '' : 's');
    out.innerHTML = hits.slice(0, 100).map(function (p) {
      return '<li><time>' + esc(p.date) + '</time> <a href="' + esc(p.url) + '">' + esc(p.title || p.text.slice(0, 80) || p.url) + '</a> ' +
        p.tags.slice(0, 5).map(function (t) { return '<span class="type">#' + esc(t) + '</span>'; }).join(' ') + '</li>';
    }).join('');
  }
  fetch('{{ "/search.json" | relative_url }}').then(function (r) { return r.json(); }).then(function (d) {
    data = d; var p = new URLSearchParams(location.search).get('q'); if (p) q.value = p; run();
  });
  q.addEventListener('input', run);
})();
</script>
