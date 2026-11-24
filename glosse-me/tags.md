---
layout: page
title: Tags
permalink: /tags/
---
{% assign tags = site.tags | sort %}
<p class="tag-cloud">
{%- for t in tags %}<a href="#{{ t[0] | slugify: 'latin' }}">{{ t[0] }} <small>{{ t[1].size }}</small></a> {% endfor -%}
</p>
{% for t in tags %}
<h2 id="{{ t[0] | slugify: 'latin' }}">#{{ t[0] }} <small>({{ t[1].size }})</small></h2>
<ul class="archive">
{%- for p in t[1] %}
  <li><time>{{ p.date | date: "%Y-%m-%d" }}</time> <a href="{{ p.url | relative_url }}">{{ p.title | default: p.summary | default: p.id | strip_html | truncate: 90 }}</a></li>
{%- endfor %}
</ul>
{% endfor %}
