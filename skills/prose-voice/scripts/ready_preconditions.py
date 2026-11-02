# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanical READY-gate precondition for prose-voice: no unresolved `[needs-source]` residue.

The READY gate blocks a document on one checkable condition — no LLM judgement here; the
judgement lives upstream in the footnoter that placed the flags:

  * SOURCE — no unresolved `[needs-source]` token remains in the document body (frontmatter
             excluded).

The "a web-enabled footnoter pass has run" half of the precondition is guaranteed structurally by
the READY full pass (which runs the footnoter web-enabled), not by this script; this script checks
the token residue that pass leaves.

Usage:
    ready_preconditions.py <doc.md> [<doc-part.md> ...] [--json]

Exit code: 0 = clear (ready-eligible); 3 = at least one flag remains; 2 = a path is missing.
The override is an operator decision made in the gate, not here — this script reports the residue;
`--json` callers apply the override.
"""
import argparse
import json
import re
import sys
from pathlib import Path

NEEDS_SOURCE_RE = re.compile(r"\[needs-source\]")


def _strip_frontmatter(lines):
    """Return (body_lines, start_index) with YAML frontmatter removed."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1 :], i + 1
    return lines, 0


def check_source(docs):
    hits = []
    for doc in docs:
        lines = doc.read_text(encoding="utf-8").splitlines()
        body, offset = _strip_frontmatter(lines)
        for i, line in enumerate(body):
            if NEEDS_SOURCE_RE.search(line):
                hits.append({"file": str(doc), "line": offset + i + 1, "text": line.strip()})
    return {"resolved": not hits, "needs_source_count": len(hits), "locations": hits}


def main():
    ap = argparse.ArgumentParser(description="prose-voice READY-gate precondition ([needs-source] residue)")
    ap.add_argument("docs", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    for d in args.docs:
        if not d.exists():
            print(f"error: document not found: {d}", file=sys.stderr)
            return 2

    source = check_source(args.docs)
    result = {"ready": source["resolved"], "source": source}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"READY precondition: {'PASS' if source['resolved'] else 'BLOCKED'}")
        for loc in source["locations"]:
            print(f"  - {loc['file']}:{loc['line']}: {loc['text']}")
    return 0 if source["resolved"] else 3


if __name__ == "__main__":
    sys.exit(main())
