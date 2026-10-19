"""Redact machine-specific paths from files before they are committed (stdlib only).

Usage:  python3 -I reference/rollouts/redact_paths.py <file or dir> [...]     (rewrites files in place)

Replacements: project root -> <project>; Claude Code's encoded project dirs -> <claude-project-dir>;
home dir -> ~; remaining user name -> <user>. PDFs get same-length replacements (padding with spaces),
so their byte offsets stay valid. Used by run_rollout.sh on every run folder and for the history rewrite.
"""
import re
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
HOME = str(Path.home())
USER = Path.home().name
ENCODED = re.sub(r"[^A-Za-z0-9]", "-", ROOT)          # ~/.claude/projects/<encoded root>[-eval]


def pairs():
    return [(ROOT, "<project>"), (ENCODED, "<claude-project-dir>"), (HOME, "~"), (USER, "<user>")]


def redact(data: bytes) -> bytes:
    if data.startswith(b"%PDF"):
        # same length: pad any path containing the home dir out to its original size
        pat = re.compile(re.escape(HOME.encode()) + rb"[^\s\"<>()]*")
        return pat.sub(lambda m: b"<redacted>".ljust(len(m.group(0)), b" ")[:len(m.group(0))], data)
    for old, new in pairs():
        data = data.replace(old.encode(), new.encode())
    return data


def main():
    n = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        for f in ([p] if p.is_file() else [x for x in p.rglob("*") if x.is_file()]):
            d = f.read_bytes()
            r = redact(d)
            if r != d:
                f.write_bytes(r)
                n += 1
    print(f"redacted {n} file(s)")


if __name__ == "__main__":
    main()
