# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compute the deterministic premise fingerprint of an essay.

The `blog-voice` curmudgeon/steelman adversarial pass is *gated*: it fires once per essay and is
skipped when the essay's premise is unchanged since the last run. This script produces the stable
token that decides "changed or not." It is deterministic and reproducible — a normalized-text hash
over a DECLARED thesis region, so ordinary body-prose edits do not move it; only the essay's
title or its declared thesis does.

The declared thesis region is:

  * the essay `title` frontmatter field, PLUS
  * the `thesis:` frontmatter field if present;
  * else (no `thesis:` field) a MECHANICAL fallback — the first body paragraph after the
    frontmatter. "First body paragraph" is defined mechanically (first non-blank run of lines
    after the closing frontmatter fence that is not a heading, image, or HTML comment), NOT by
    semantic judgement, so the fallback stays reproducible.

Normalization: lowercase, strip punctuation to spaces, collapse whitespace. The hash is SHA-256;
the reported fingerprint is the first 16 hex chars (64 bits — ample for change detection).

stdlib-only, uv-run. Usage:

    uv run premise_fingerprint.py path/to/ESSAY.md            # prints the 16-char fingerprint
    uv run premise_fingerprint.py path/to/ESSAY.md --json     # {fingerprint, region, title, ...}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter-fields, body). Only the flat scalar fields we need are parsed.

    Handles `key: value`, `key: "value"`, and YAML block scalars (`key: >-` / `key: |`) whose
    continuation lines are more-indented. Good enough for `title:` and `thesis:`; not a full YAML
    parser (no external dep).
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    # find the closing fence
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :])

    fields: dict[str, str] = {}
    i = 0
    key_re = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
    while i < len(fm_lines):
        line = fm_lines[i]
        m = key_re.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", ">-", "|", "|-", ">+", "|+"):
            # block scalar: gather more-indented continuation lines
            block: list[str] = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].strip() == "" or fm_lines[i][:1] in (" ", "\t")):
                block.append(fm_lines[i].strip())
                i += 1
            fields[key] = " ".join(b for b in block if b)
            continue
        # strip matching surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        fields[key] = val
        i += 1
    return fields, body


def first_body_paragraph(body: str) -> str:
    """Mechanical fallback: the first paragraph of real prose after the frontmatter.

    Skips blank lines, ATX headings (`#`), images (`![`), and HTML comments (`<!--`). A paragraph
    is the first maximal run of non-blank lines once a qualifying line is found.
    """
    lines = body.splitlines()
    para: list[str] = []
    started = False
    for line in lines:
        s = line.strip()
        if not started:
            if s == "" or s.startswith("#") or s.startswith("![") or s.startswith("<!--"):
                continue
            started = True
            para.append(s)
        else:
            if s == "":
                break
            para.append(s)
    return " ".join(para)


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)  # punctuation -> space
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fingerprint(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    fields, body = split_frontmatter(text)
    title = fields.get("title", "")
    thesis = fields.get("thesis", "")
    if thesis:
        region = "thesis-field"
        source = f"{title}\n{thesis}"
    else:
        region = "first-body-paragraph"
        source = f"{title}\n{first_body_paragraph(body)}"
    norm = normalize(source)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return {
        "fingerprint": digest,
        "region": region,
        "title": title,
        "normalized_len": str(len(norm)),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Deterministic premise fingerprint of an essay.")
    ap.add_argument("essay", type=Path, help="path to ESSAY*.md")
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = ap.parse_args(argv)

    if not args.essay.is_file():
        print(f"error: not a file: {args.essay}", file=sys.stderr)
        return 2
    result = fingerprint(args.essay)
    if args.json:
        print(json.dumps(result))
    else:
        print(result["fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
