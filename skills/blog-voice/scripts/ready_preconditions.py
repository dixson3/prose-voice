# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanical READY-gate preconditions for blog-voice: image + source.

The blog-voice READY gate blocks an essay from reaching `ready` on two mechanical, checkable
conditions (no LLM judgement here — the judgement lives upstream in the illustrator that placed
the anchors and the footnoter that placed the `[needs-source]` flags):

  * IMAGE  — every *current* essay section (each `## heading`) plus the hero has a RESOLVED
             illustration selection (`selected: <id>` or `selected: no-image`). A current
             section with no `<!-- illus:<id> -->` anchor, or whose sidecar block is
             `unresolved` or missing, BLOCKS. Stale blocks (an anchor no longer in the essay)
             are ignored.
  * SOURCE — no unresolved `[needs-source]` token remains in the essay body.

The "a web-enabled footnoter pass has run" half of the source precondition is guaranteed
STRUCTURALLY by the READY full pass (which runs the footnoter web-enabled), not by this script;
this script checks the token residue that pass leaves.

Section identity — "adjacent" anchor: a heading's anchor is the nearest preceding
`<!-- illus:<id> -->` comment with NO intervening `## heading` between the comment and the
heading. The hero anchor is `<!-- illus:hero -->`.

Usage:
    ready_preconditions.py <essay.md> [<essay-part.md> ...] [--json]

Exit code: 0 = both preconditions resolved (ready-eligible); 3 = at least one blocks.
The `[needs-source]` override is an operator decision made in the gate, not here — this script
reports the residue; `--json` callers apply the override.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^##\s+(?!#)(.*)$")           # a level-2 heading line
ANCHOR_RE = re.compile(r"<!--\s*illus:([A-Za-z0-9]+)\s*-->")
BLOCK_HDR_RE = re.compile(r"^##\s+illus:([A-Za-z0-9]+)\b")
SELECTED_RE = re.compile(r"^selected:\s*(\S+)", re.IGNORECASE)
STALE_RE = re.compile(r"^stale:\s*true\b", re.IGNORECASE)
NEEDS_SOURCE_RE = re.compile(r"\[needs-source\]")

# Apparatus headings that are NOT content sections and never need an illustration.
# `Notes` is the footnoter's footnote-definitions block; keep this in sync with
# agents/footnoter.md (the Notes heading) and agents/illustrator.md (anchors skip these).
EXCLUDED_HEADINGS = {"notes", "footnotes"}


def _strip_frontmatter(lines):
    """Return (body_lines, start_index) with YAML frontmatter removed."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1 :], i + 1
    return lines, 0


def sidecar_path(essay: Path) -> Path:
    # ESSAY.md -> ESSAY.illustrations.md ; ESSAY-2.md -> ESSAY-2.illustrations.md
    return essay.with_name(essay.stem + ".illustrations.md")


def parse_essay_sections(text: str):
    """Return (hero_present, [(anchor_id_or_None, heading_text), ...])."""
    lines = text.splitlines()
    body, _ = _strip_frontmatter(lines)
    hero_present = any(
        m and m.group(1) == "hero" for m in (ANCHOR_RE.search(l) for l in body)
    )
    sections = []
    pending_anchor = None
    for line in body:
        am = ANCHOR_RE.search(line)
        if am:
            if am.group(1) != "hero":
                pending_anchor = am.group(1)
            continue
        hm = HEADING_RE.match(line)
        if hm:
            heading = hm.group(1).strip()
            if heading.lower() not in EXCLUDED_HEADINGS:
                sections.append((pending_anchor, heading))
            pending_anchor = None  # consumed; no intervening-## carry past a heading
    return hero_present, sections


def parse_sidecar(text: str):
    """Return {id: {'selected': str|None, 'stale': bool}}."""
    blocks = {}
    cur = None
    for line in text.splitlines():
        hm = BLOCK_HDR_RE.match(line)
        if hm:
            cur = hm.group(1)
            blocks[cur] = {"selected": None, "stale": False}
            continue
        if cur is None:
            continue
        sm = SELECTED_RE.match(line.strip())
        if sm:
            blocks[cur]["selected"] = sm.group(1).lower()
        elif STALE_RE.match(line.strip()):
            blocks[cur]["stale"] = True
    return blocks


def _resolved(sel):
    return sel is not None and sel != "unresolved"


def check_image(essay: Path):
    hero_present, sections = parse_essay_sections(essay.read_text())
    side = sidecar_path(essay)
    blocks = parse_sidecar(side.read_text()) if side.exists() else {}
    blockers = []

    # hero
    if not hero_present:
        blockers.append("hero: no <!-- illus:hero --> anchor in essay")
    else:
        b = blocks.get("hero")
        if b is None:
            blockers.append("hero: no sidecar block")
        elif not _resolved(b["selected"]):
            blockers.append(f"hero: selection {b['selected'] or 'unresolved'}")

    # sections
    for anchor_id, heading in sections:
        if anchor_id is None:
            blockers.append(f"section '{heading}': no illustration anchor")
            continue
        b = blocks.get(anchor_id)
        if b is None:
            blockers.append(f"section '{heading}' (illus:{anchor_id}): no sidecar block")
        elif not _resolved(b["selected"]):
            blockers.append(
                f"section '{heading}' (illus:{anchor_id}): selection "
                f"{b['selected'] or 'unresolved'}"
            )
    return {
        "resolved": not blockers,
        "sidecar": str(side),
        "sidecar_present": side.exists(),
        "section_count": len(sections),
        "hero_present": hero_present,
        "blockers": blockers,
    }


def check_source(essays):
    hits = []
    for essay in essays:
        lines = essay.read_text().splitlines()
        body, offset = _strip_frontmatter(lines)
        for i, line in enumerate(body):
            if NEEDS_SOURCE_RE.search(line):
                hits.append({"file": str(essay), "line": offset + i + 1, "text": line.strip()})
    return {"resolved": not hits, "needs_source_count": len(hits), "locations": hits}


def main():
    ap = argparse.ArgumentParser(description="blog-voice READY-gate preconditions (image + source)")
    ap.add_argument("essays", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    for e in args.essays:
        if not e.exists():
            print(f"error: essay not found: {e}", file=sys.stderr)
            return 2

    # The image precondition is per-essay-file (each part has its own sections + hero).
    image = {str(e): check_image(e) for e in args.essays}
    source = check_source(args.essays)
    image_ok = all(v["resolved"] for v in image.values())
    ready = image_ok and source["resolved"]

    result = {"ready": ready, "image": image, "source": source}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"READY preconditions: {'PASS' if ready else 'BLOCKED'}")
        for path, v in image.items():
            if v["blockers"]:
                print(f"  IMAGE ({path}):")
                for b in v["blockers"]:
                    print(f"    - {b}")
        if not source["resolved"]:
            print("  SOURCE:")
            for loc in source["locations"]:
                print(f"    - {loc['file']}:{loc['line']}: {loc['text']}")
        if ready:
            print("  both preconditions resolved.")
    return 0 if ready else 3


if __name__ == "__main__":
    sys.exit(main())
