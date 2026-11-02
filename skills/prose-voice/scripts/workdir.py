# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Resolve the prose-voice working directory for a document under review.

Every artifact prose-voice generates — gate reports, the footnoter proposal list, the
curmudgeon counter-essay, the steelman adjudication, provenance notes — lives under one
project-local tree, never beside the document:

    <root>/.prosevoice/<doc-key>/<artifact>.md

  * <root>     — the git root containing the document (or cwd when not in a git repo).
  * <doc-key>  — the document's path relative to <root>, extension dropped, so
                 posts/2026/why.md  ->  .prosevoice/posts/2026/why/
                 For chat-drafted prose with no file, --chat <slug> gives .prosevoice/_chat/<slug>/.

Artifacts have fixed names (one per agent / gate) so a re-run overwrites rather than accumulates:
    draft.md  review.md  ready.md            gate reports (latest run)
    footnoter.md                             proposal list for operator prose
    fact-check.md  provenance.md             the informational set
    red-team.md  cold-read.md                the persuasive additions
    curmudgeon.md  steelman.md               the gated pair (carry premise_fingerprint:)

Usage:
    workdir.py <doc.md> [--ensure] [--file NAME] [--json]
    workdir.py --chat <slug> [--ensure] [--file NAME] [--json]

Prints the directory (or the artifact path with --file). --ensure creates it. Exit 2 on error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR_NAME = ".prosevoice"
CHAT_BUCKET = "_chat"


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(out) if out else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def slugify(s: str) -> str:
    s = re.sub(r"[^\w-]+", "-", s.strip().lower())
    return re.sub(r"-{2,}", "-", s).strip("-") or "untitled"


def resolve(doc: Path | None, chat: str | None) -> dict:
    if chat is not None:
        root = git_root(Path.cwd()) or Path.cwd()
        key = Path(CHAT_BUCKET) / slugify(chat)
    elif doc is None:
        raise ValueError("one of doc or chat is required")
    else:
        doc = doc.resolve()
        root = git_root(doc.parent) or Path.cwd().resolve()
        try:
            rel = doc.relative_to(root)
        except ValueError:
            # Document outside the git root / cwd: key by name only.
            rel = Path(doc.name)
        key = rel.with_suffix("")
    workdir = root / ROOT_DIR_NAME / key
    return {"root": str(root), "doc_key": key.as_posix(), "workdir": str(workdir)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Resolve the prose-voice .prosevoice/<doc-key>/ workdir.")
    ap.add_argument("doc", nargs="?", type=Path, help="path to the document under review")
    ap.add_argument("--chat", metavar="SLUG", help="chat-drafted prose with no file; a short slug")
    ap.add_argument("--ensure", action="store_true", help="create the directory")
    ap.add_argument("--file", metavar="NAME", help="print the path of this artifact inside the workdir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if (args.doc is None) == (args.chat is None):
        print("error: give exactly one of <doc> or --chat <slug>", file=sys.stderr)
        return 2
    if args.doc is not None and not args.doc.is_file():
        print(f"error: not a file: {args.doc}", file=sys.stderr)
        return 2

    info = resolve(args.doc, args.chat)
    wd = Path(info["workdir"])
    if args.ensure:
        wd.mkdir(parents=True, exist_ok=True)
    target = wd / args.file if args.file else wd
    if args.json:
        info["path"] = str(target)
        print(json.dumps(info))
    else:
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
