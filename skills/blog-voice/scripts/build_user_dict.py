# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build a merged Harper user dictionary for the blog-voice grammar-check agent.

Harper's `harper-cli lint --user-dict-path <path>` accepts a SINGLE dictionary
file. The blog-voice policy splits custom words across two committed sources:

  1. the GLOBAL skill dictionary  (<skill dir>/harper/dictionary.txt)
     — repo-wide coinages and recurring proper nouns; and
  2. an optional per-incubator sidecar (Incubator/<slug>/.harper-words)
     — essay-local proper nouns (citation author names, one-off names).

This helper unions the two into one temp dictionary and prints its path on
stdout, so the agent can pass it straight to `--user-dict-path`. A missing
sidecar is fine — the global dictionary is used alone (the common case).

Both inputs share the same line format: one word per line; blank lines and
lines whose first non-space character is '#' are comments and are dropped.
The output is the sorted, de-duplicated union, one word per line (Harper reads
a plain word-per-line dictionary; comments are stripped so they never leak in
as dictionary entries).

Usage:
    build_user_dict.py --global <dictionary.txt> [--sidecar <.harper-words>] [--out <path>]

  --global   Path to the global dictionary. Required. A missing global file is
             an error (the policy file should always exist); use an empty file
             to mean "no global words".
  --sidecar  Path to the per-incubator sidecar. Optional and may be absent —
             absence is silently tolerated (falls back to the global alone).
  --out      Where to write the merged dictionary. Optional; defaults to a
             NamedTemporaryFile the caller is responsible for cleaning up. The
             chosen path is always printed to stdout.

Exit codes: 0 on success; 2 if --global is missing/unreadable.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def read_words(path: Path) -> list[str]:
    """Return the word entries in a dictionary/sidecar file.

    One word per line; blank lines and '#' comment lines are dropped. Trailing
    inline content is NOT stripped — a dictionary line is the whole (trimmed)
    line, because a custom word may legitimately contain '#' only as its first
    char (comment) and Harper dictionary entries are single tokens.
    """
    words: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def build(global_path: Path, sidecar_path: Path | None) -> list[str]:
    words = set(read_words(global_path))
    if sidecar_path is not None and sidecar_path.is_file():
        words.update(read_words(sidecar_path))
    # Sort case-insensitively but stably so the file is deterministic and
    # diff-friendly; Harper itself is order-independent.
    return sorted(words, key=lambda w: (w.casefold(), w))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Merge Harper dictionaries into one user-dict.")
    p.add_argument("--global", dest="global_path", required=True, help="global dictionary.txt")
    p.add_argument("--sidecar", dest="sidecar_path", default=None, help="per-incubator .harper-words (optional)")
    p.add_argument("--out", dest="out_path", default=None, help="output path (default: temp file)")
    args = p.parse_args(argv)

    global_path = Path(args.global_path)
    if not global_path.is_file():
        print(f"error: global dictionary not found: {global_path}", file=sys.stderr)
        return 2

    sidecar_path = Path(args.sidecar_path) if args.sidecar_path else None
    words = build(global_path, sidecar_path)

    if args.out_path:
        out = Path(args.out_path)
        out.write_text("\n".join(words) + ("\n" if words else ""), encoding="utf-8")
    else:
        fd = tempfile.NamedTemporaryFile(
            mode="w", suffix=".harper-dict.txt", delete=False, encoding="utf-8"
        )
        fd.write("\n".join(words) + ("\n" if words else ""))
        fd.close()
        out = Path(fd.name)

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
