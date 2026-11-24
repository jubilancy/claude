---
layout: page
title: Archive
permalink: /archive/
---
{% assign by_year = site.posts | group_by_exp: "p", "p.date | date: '%Y'" %}
{% for y in by_year %}
## {{ y.name }} <small>({{ y.items.size }})</small>

<ul class="archive">
{%- for p in y.items %}
  <li><time>{{ p.date | date: "%b %-d" }}</time> <a href="{{ p.url | relative_url }}">{{ p.title | default: p.summary | default: p.id | strip_html | truncate: 90 }}</a> <span class="type">{{ p.type }}</span></li>
{%- endfor %}
</ul>
{% endfor %}
