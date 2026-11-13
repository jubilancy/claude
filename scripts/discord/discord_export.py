#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["discord.py"]
# ///
"""
discord_export.py - export channel history from a Discord server you own/administer

Uses a *bot* account (not your user token; automating a user account is
self-botting and can get the account banned). Only the REST API is used, so
the script logs in, reads history, and exits; it never joins the gateway.

One-time setup (Discord Developer Portal, https://discord.com/developers/applications):
  1. New Application -> Bot -> copy the token.
  2. Bot tab -> Privileged Gateway Intents -> enable MESSAGE CONTENT INTENT.
  3. OAuth2 -> URL Generator: scope `bot`, permissions "View Channels" and
     "Read Message History"; open the URL and add the bot to your server.
  4. Provide the token as the DISCORD_TOKEN environment variable
     (in a cloud session: the environment's secrets settings). It is never
     taken from the command line and never printed.
  5. IDs: Discord Settings -> Advanced -> Developer Mode, then right-click a
     channel or server -> Copy ID.

Usage:
    uv run scripts/discord/discord_export.py CHANNEL_ID [CHANNEL_ID ...] [options]
    uv run scripts/discord/discord_export.py --guild GUILD_ID [options]     # every readable text channel

Options:
    --output-dir DIR        default ./discord_export
    --format {md,json,both} default md
    --limit N               newest N messages per channel (default: all)
    --after WHEN            only messages after a date (2025-01-31 or ISO) or message ID
    --before WHEN           only messages before a date or message ID
    --download-attachments  save attachment files next to the export
                            (Discord CDN links are signed and expire, so
                            download them if you want a lasting archive)

A thread ID works as a channel ID. Output is chronological, one file per
channel.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

import discord


def slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "-", name).strip("-") or "channel"


def parse_when(value: str):
    """Message ID (digits) -> Object; otherwise an ISO date/datetime in UTC."""
    if value.isdigit():
        return discord.Object(id=int(value))
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"Could not parse '{value}'. Use a message ID or a date like 2025-01-31 or 2025-01-31T12:00:00.")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def message_text(m: "discord.Message") -> str:
    if m.content:
        return m.content
    return m.system_content if m.is_system() else ""


def message_to_dict(m: "discord.Message") -> dict:
    return {
        "id": str(m.id),
        "created_at": m.created_at.isoformat(),
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "author": {
            "id": str(m.author.id),
            "name": m.author.name,
            "display_name": m.author.display_name,
            "bot": m.author.bot,
        },
        "type": m.type.name,
        "content": message_text(m),
        "pinned": m.pinned,
        "reply_to": str(m.reference.message_id) if m.reference and m.reference.message_id else None,
        "attachments": [
            {"id": str(a.id), "filename": a.filename, "url": a.url, "size": a.size, "content_type": a.content_type}
            for a in m.attachments
        ],
        "embeds": [e.to_dict() for e in m.embeds],
        "reactions": [{"emoji": str(r.emoji), "count": r.count} for r in m.reactions],
    }


def message_to_markdown(m: "discord.Message") -> str:
    head = f"**{m.author.display_name}**{' [bot]' if m.author.bot else ''} - {m.created_at.strftime('%H:%M:%S')} UTC"
    if m.edited_at:
        head += " (edited)"
    if m.pinned:
        head += " (pinned)"
    lines = [head]
    if m.reference and m.reference.message_id:
        lines.append(f"> reply to message {m.reference.message_id}")
    text = message_text(m)
    if text:
        lines.append(text)
    for a in m.attachments:
        lines.append(f"- attachment: [{a.filename}]({a.url})")
    for e in m.embeds:
        bits = [b for b in (e.title, e.url) if b]
        lines.append("- embed: " + " - ".join(bits) if bits else "- embed")
        if e.description:
            lines.append("  " + e.description.replace("\n", "\n  "))
    if m.reactions:
        lines.append("Reactions: " + ", ".join(f"{r.emoji} {r.count}" for r in m.reactions))
    return "\n".join(lines) + "\n"


async def iter_messages(channel, limit, after, before):
    """Chronological messages. With --limit and no --after, that means the
    newest N (discord.py would otherwise return the oldest N when oldest_first)."""
    if limit and after is None:
        newest = [m async for m in channel.history(limit=limit, before=before)]
        for m in reversed(newest):
            yield m
    else:
        async for m in channel.history(limit=limit, after=after, before=before, oldest_first=True):
            yield m


async def export_channel(channel, args, after, before) -> int:
    name = getattr(channel, "name", None) or str(channel.id)
    guild = getattr(getattr(channel, "guild", None), "name", None)
    stem = f"{slug(name)}-{channel.id}"
    want_md, want_json = args.format in ("md", "both"), args.format in ("json", "both")
    md_path = os.path.join(args.output_dir, stem + ".md")
    json_path = os.path.join(args.output_dir, stem + ".json")
    att_dir = os.path.join(args.output_dir, stem + "-attachments")

    md = open(md_path, "w", encoding="utf-8") if want_md else None
    js = open(json_path, "w", encoding="utf-8") if want_json else None
    count = with_text = with_extras = 0
    last_day = None
    try:
        if md:
            md.write(f"# #{name}\n\n")
            md.write(f"- Server: {guild or 'unknown'}\n- Channel ID: {channel.id}\n")
            md.write(f"- Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        if js:
            js.write("[")

        async for m in iter_messages(channel, args.limit, after, before):
            if md:
                day = m.created_at.strftime("%Y-%m-%d")
                if day != last_day:
                    md.write(f"\n## {day}\n\n")
                    last_day = day
                md.write(message_to_markdown(m) + "\n")
            if js:
                js.write(("," if count else "") + "\n" + json.dumps(message_to_dict(m), ensure_ascii=False))
            if args.download_attachments:
                for a in m.attachments:
                    os.makedirs(att_dir, exist_ok=True)
                    try:
                        await a.save(os.path.join(att_dir, f"{m.id}-{a.id}-{slug(a.filename)[:80]}"))
                    except discord.HTTPException as e:
                        print(f"    could not download {a.filename}: {e}")
            count += 1
            with_text += bool(message_text(m))
            with_extras += bool(m.attachments or m.embeds)
            if count % 500 == 0:
                print(f"    {count} messages...")
        if js:
            js.write("\n]\n")
    except discord.HTTPException:
        if count == 0:  # nothing readable: don't leave empty/invalid files behind
            for fh, path in ((md, md_path), (js, json_path)):
                if fh:
                    fh.close()
                    os.remove(path)
        raise
    finally:
        for fh in (md, js):
            if fh and not fh.closed:
                fh.close()

    if count and with_text == 0 and with_extras:
        print("    WARNING: every message has empty text. Enable MESSAGE CONTENT INTENT "
              "(Developer Portal -> Bot -> Privileged Gateway Intents) and re-run.")
    return count


async def run(args) -> int:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        sys.exit("DISCORD_TOKEN is not set. Create a bot in the Discord Developer Portal and "
                 "provide its token as an environment variable (see --help).")
    after = parse_when(args.after) if args.after else None
    before = parse_when(args.before) if args.before else None
    os.makedirs(args.output_dir, exist_ok=True)

    intents = discord.Intents.default()
    intents.message_content = True
    failures = 0

    async with discord.Client(intents=intents) as client:
        try:
            await client.login(token)
        except discord.LoginFailure:
            sys.exit("Discord rejected the token. Use the Bot token from the Developer Portal's Bot tab.")

        channels = []
        for cid in args.channels:
            try:
                channels.append(await client.fetch_channel(cid))
            except discord.Forbidden:
                print(f"Channel {cid}: bot has no access (check View Channels / invite).")
                failures += 1
            except discord.NotFound:
                print(f"Channel {cid}: not found (wrong ID, or the bot is not in that server).")
                failures += 1
        if args.guild:
            try:
                guild = await client.fetch_guild(args.guild)
                found = [c for c in await guild.fetch_channels() if isinstance(c, discord.TextChannel)]
                found.sort(key=lambda c: c.position)
                print(f"Server '{guild.name}': {len(found)} text channel(s).")
                channels.extend(found)
            except (discord.Forbidden, discord.NotFound):
                print(f"Server {args.guild}: not found or the bot is not a member.")
                failures += 1

        total = 0
        for i, ch in enumerate(channels, start=1):
            label = getattr(ch, "name", ch.id)
            print(f"[{i}/{len(channels)}] #{label}")
            try:
                n = await export_channel(ch, args, after, before)
            except discord.Forbidden:
                print("    skipped: bot cannot read this channel (needs View Channel + Read Message History).")
                failures += 1
                continue
            except discord.HTTPException as e:
                print(f"    failed: {e}")
                failures += 1
                continue
            print(f"    {n} message(s)")
            total += n
        print(f"\nDone. {total} message(s) from {len(channels)} channel(s) -> {args.output_dir}/")
    return 1 if failures and not total else 0


def main():
    ap = argparse.ArgumentParser(description="Export Discord channel history with a bot token (DISCORD_TOKEN).")
    ap.add_argument("channels", nargs="*", type=int, help="channel (or thread) IDs")
    ap.add_argument("--guild", type=int, help="server ID: export every text channel the bot can read")
    ap.add_argument("--output-dir", default="discord_export")
    ap.add_argument("--format", choices=("md", "json", "both"), default="md")
    ap.add_argument("--limit", type=int, default=None, help="newest N messages per channel (default: all)")
    ap.add_argument("--after", help="date (2025-01-31) or message ID")
    ap.add_argument("--before", help="date or message ID")
    ap.add_argument("--download-attachments", action="store_true")
    args = ap.parse_args()
    if not args.channels and not args.guild:
        ap.error("give at least one CHANNEL_ID or --guild GUILD_ID")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
