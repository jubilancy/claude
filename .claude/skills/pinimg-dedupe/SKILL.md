---
name: pinimg-dedupe
description: Remove smaller pixel-size variants from a list of image URLs when an i.pinimg.com /originals/ copy of the same image exists. Use when the user pastes or points to a list of Pinterest image URLs and asks to dedupe, remove smaller variants, or keep originals.
---

# Pinterest image URL dedupe

Given a list of URLs, drop every `i.pinimg.com` size variant whose image also appears under `/originals/`. Keep all originals.

## Rules

- A pinimg URL looks like `https://i.pinimg.com/<size>/aa/bb/cc/<32-char hash>.<ext>`.
- Match variants to originals by the 32-character hash only, never by size folder or extension (an original may be `.png` while its variants are `.jpg`).
- Size folders include `30x30_RS`, `60x60`, `140x140_RS`, `150x150`, `200x150`, `236x`, `280x280_RS`, `345x`, `474x`, `736x`, `750x`, `1200x`. Any folder other than `originals` counts as a variant.
- Remove a variant only when its hash has an `/originals/` URL in the list.
- Keep everything else: pinimg hashes with no original (all their variants stay), `custom_covers`, `s.pinimg.com`, and every non-pinimg URL.
- Preserve the input order and keep blank lines out.

## How to run

1. Save the pasted URLs to a file in the scratchpad (one per line).
2. Run the bundled script:

   ```
   uv run python -I .claude/skills/pinimg-dedupe/scripts/dedupe.py INPUT.txt OUTPUT.txt
   ```

   It prints `in= kept= removed= originals=` counts to stderr.
3. Save the output where the user can open it (primary working directory) and report the before/after counts.
4. Tell the user that pinimg images without an original keep all their size variants, and offer a second pass that keeps only the largest size for those.
