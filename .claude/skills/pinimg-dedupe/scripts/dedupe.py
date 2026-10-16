"""Drop smaller pinimg size variants when an /originals/ copy exists.

Usage: uv run python -I dedupe.py [INPUT] [OUTPUT]
INPUT/OUTPUT default to stdin/stdout. A removal summary goes to stderr.
"""
import re
import sys

# https://i.pinimg.com/<size folder>/aa/bb/cc/<32-char hash>.<ext>
PIN = re.compile(
    r"^https://i\.pinimg\.com/(?P<size>[^/]+)/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{2}/"
    r"(?P<hash>[0-9a-f]{32})\.\w+$"
)


def dedupe(urls):
    originals = set()
    for u in urls:
        m = PIN.match(u)
        if m and m["size"] == "originals":
            originals.add(m["hash"])
    kept, removed = [], []
    for u in urls:
        m = PIN.match(u)
        if m and m["size"] != "originals" and m["hash"] in originals:
            removed.append(u)
        else:
            kept.append(u)
    return kept, removed, originals


def main():
    src = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    urls = [line.strip() for line in src if line.strip()]
    kept, removed, originals = dedupe(urls)
    out = "\n".join(kept) + "\n"
    if len(sys.argv) > 2:
        open(sys.argv[2], "w").write(out)
    else:
        sys.stdout.write(out)
    print(
        f"in={len(urls)} kept={len(kept)} removed={len(removed)} originals={len(originals)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
