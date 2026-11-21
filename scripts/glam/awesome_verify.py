#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""
awesome_verify.py - Verify GitHub repos from a seed list and write an awesome-list Markdown file.

What it does:
- Reads a seeds file: "## Section" lines start a section, every other non-comment line is owner/repo.
- Looks each repo up on GitHub (search API, 5 repos per query, via the `gh` CLI) and takes the
  description, stars, last push date, license and archived flag from the live response.
  The seed is only a search term; nothing in the output comes from memory.
- Keeps repos that exist, are not archived and were pushed within --max-age-days (default 730).
- Writes a Markdown awesome list (sections as in the seeds, each item sorted by stars).
- Writes results-log-{timestamp}.txt in the current folder every run.

Usage:
    uv run scripts/glam/awesome_verify.py                                   # seeds: scripts/glam/glam-seeds.txt
    uv run scripts/glam/awesome_verify.py --seeds my-seeds.txt --output awesome/glam-tools.md
    uv run scripts/glam/awesome_verify.py --max-age-days 365 --title "Awesome GLAM Tools"
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BATCH = 5
DELAY = 2.5  # search API allows 30 requests/minute


def gh_search(repos):
    """Search up to BATCH repos at once; returns {full_name_lower: item}."""
    q = " ".join(f"repo:{r}" for r in repos)
    for attempt in range(4):
        p = subprocess.run(
            ["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "per_page=20"],
            capture_output=True, text=True)
        if p.returncode == 0:
            items = json.loads(p.stdout).get("items", [])
            return {i["full_name"].lower(): i for i in items}
        if "rate limit" in (p.stdout + p.stderr).lower():
            time.sleep(30)
            continue
        raise RuntimeError((p.stderr or p.stdout).strip()[:300])
    raise RuntimeError("rate limited")


def parse_seeds(path):
    sections, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("# "):
            continue
        if line.startswith("## "):
            cur = (line[3:].strip(), [])
            sections.append(cur)
        elif cur is not None and re.fullmatch(r"[\w.-]+/[\w.-]+", line):
            cur[1].append(line)
    return sections


def clean(text, n=170):
    text = re.sub(r"\s+", " ", text or "").strip().replace("|", "/")
    text = re.sub(r":[a-z0-9_+-]+:", "", text).replace("*", "").strip()  # :emoji: shortcodes, markdown stars
    if len(text) > n:
        text = text[: n - 1].rsplit(" ", 1)[0] + "…"
    return text


def anchor(s):
    return re.sub(r"[^a-z0-9 -]", "", s.lower()).replace(" ", "-")


def main():
    here = Path(__file__).parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=str(here / "glam-seeds.txt"))
    ap.add_argument("--output", default="awesome-glam-tools.md")
    ap.add_argument("--title", default="Awesome GLAM Tools")
    ap.add_argument("--max-age-days", type=int, default=730)
    a = ap.parse_args()

    start = datetime.now()
    cutoff = datetime.now(timezone.utc) - timedelta(days=a.max_age_days)
    sections = parse_seeds(Path(a.seeds))
    seeds = [r for _, rs in sections for r in rs]
    found, errors, ok, skipped, warnings = {}, [], [], [], []

    for i in range(0, len(seeds), BATCH):
        chunk = seeds[i:i + BATCH]
        try:
            found.update(gh_search(chunk))
        except Exception as e:  # one failed batch never stops the run
            for r in chunk:
                errors.append((r, f"search failed: {e}"))
        time.sleep(DELAY)

    errored = {r for r, _ in errors}
    result = []
    for name, repos in sections:
        items = []
        for r in repos:
            if r in errored:
                continue
            it = found.get(r.lower())
            if not it:
                errors.append((r, "not found by search (renamed, private or no access)"))
                continue
            pushed = datetime.fromisoformat(it["pushed_at"].replace("Z", "+00:00"))
            if it["archived"]:
                skipped.append((r, "archived"))
            elif pushed < cutoff:
                skipped.append((r, f"last push {pushed:%Y-%m-%d}, older than {a.max_age_days} days"))
            elif not it.get("description"):
                skipped.append((r, "no description on GitHub, cannot describe it without guessing"))
            else:
                items.append(it)
                ok.append((r, f"{it['stargazers_count']} stars, pushed {pushed:%Y-%m-%d}"))
                if it["full_name"] != r:
                    warnings.append((r, f"canonical name is {it['full_name']}"))
        items.sort(key=lambda x: -x["stargazers_count"])
        result.append((name, items))

    total = sum(len(i) for _, i in result)
    today = datetime.now().strftime("%Y-%m-%d")
    out = [f"# {a.title} [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)", "",
           "> Tools, platforms, generators and actions for libraries, archives, museums and digital collections.", "",
           f"Every entry was checked against the GitHub API on {today}: the repository exists, is not archived "
           f"and was pushed to within the last {a.max_age_days} days. "
           "Descriptions are GitHub's own. Stars and last-push dates are in brackets. "
           f"{total} entries.", "", "## Contents", ""]
    out += [f"- [{n}](#{anchor(n)}) ({len(i)})" for n, i in result if i]
    for n, items in result:
        if not items:
            continue
        out += ["", f"## {n}", ""]
        for it in items:
            lic = f", {it['license']['spdx_id']}" if it.get("license") and it["license"]["spdx_id"] not in (None, "NOASSERTION") else ""
            out.append(f"- [{it['full_name']}]({it['html_url']}) - {clean(it['description'])} "
                       f"({it['stargazers_count']:,} ★, pushed {it['pushed_at'][:10]}{lic})")
    Path(a.output).write_text("\n".join(out) + "\n", encoding="utf-8")

    end = datetime.now()
    log = Path(f"results-log-{start:%Y-%m-%d_%H%M%S}.txt")

    def block(title, rows):
        s = [f"{title} ({len(rows)})"]
        s += [f"  {r}\n    {d}" for r, d in rows] or ["  (none)"]
        return "\n".join(s)

    log.write_text("\n".join([
        f"Run started : {start:%Y-%m-%d %H:%M:%S}",
        f"Run finished: {end:%Y-%m-%d %H:%M:%S} (duration {end - start})",
        f"Input       : {a.seeds}", f"Output      : {a.output}", "",
        "SUMMARY", f"  total seeds                 : {len(seeds)}", f"  done this run (written)     : {len(ok)}",
        "  already done (skipped)      : 0", f"  skipped on purpose          : {len(skipped)}",
        f"  errors                      : {len(errors)}", "",
        block("SUCCESSFUL: WRITTEN", ok), "",
        block("SUCCESSFUL: SKIPPED, ALREADY IN OUTPUT", []), "",
        block("SKIPPED ON PURPOSE: archived, stale or undescribed", skipped), "",
        block("ERRORS", errors), "",
        block("WARNINGS", warnings), ""]), encoding="utf-8")
    print(f"{len(ok)} written, {len(skipped)} skipped, {len(errors)} errors\nList: {a.output}\nLog : {log.resolve()}")


if __name__ == "__main__":
    sys.exit(main())
