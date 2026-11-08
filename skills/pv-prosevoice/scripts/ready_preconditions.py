# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check READY source flags and explicitly planned visuals in Markdown essays.

Only <!-- illus:ID --> anchors opt into visual-selection checks. Every active anchor
needs a matching ## illus:ID block at the configured illustrations artifact path
(default .prose-voice/cache/, optional adjacent mode) with a chosen
asset id or `selected: no-image`. Unanchored sections need no visual or sidecar;
stale sidecar blocks without anchors are ignored. Anchors may occur anywhere.

No unresolved [needs-source] token may remain in the body. A web-enabled source
review is required by the skill, not proven by this mechanical check. Explicit
source overrides are reported by the caller, never silently applied here.

Usage: ready_preconditions.py <essay.md> [<part.md> ...] [--json]
Exit: 0 = clear, 3 = blocked, 2 = missing input.
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

# Both skills are installed together; load their shared project configuration.
_config_path = Path(__file__).resolve().parents[2] / "pv-preflight/scripts/pv_config.py"
_spec = importlib.util.spec_from_file_location("pv_config", _config_path)
assert _spec is not None and _spec.loader is not None
_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config)
artifact_paths = _config.artifact_paths

ANCHOR_RE = re.compile(r"<!--\s*illus:([A-Za-z0-9]+)\s*-->")
BLOCK_HDR_RE = re.compile(r"^##\s+illus:([A-Za-z0-9]+)\b")
SELECTED_RE = re.compile(r"^selected:\s*(\S+)", re.IGNORECASE)
NEEDS_SOURCE_RE = re.compile(r"\[needs-source\]")


def _strip_frontmatter(lines):
    """Return (body_lines, start_index) with YAML frontmatter removed."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1 :], i + 1
    return lines, 0


def sidecar_path(essay: Path) -> Path:
    return artifact_paths(essay)["illustrations"]


def parse_sidecar(text: str):
    """Return {anchor_id: selected_asset_or_None}."""
    blocks = {}
    current = None
    for line in text.splitlines():
        heading = BLOCK_HDR_RE.match(line)
        if heading:
            current = heading.group(1)
            blocks[current] = None
            continue
        selected = SELECTED_RE.match(line.strip())
        if current is not None and selected:
            blocks[current] = selected.group(1)
    return blocks


def check_image(essay: Path):
    body, _ = _strip_frontmatter(essay.read_text(encoding="utf-8").splitlines())
    anchors = sorted(set(ANCHOR_RE.findall("\n".join(body))))
    side = sidecar_path(essay)
    blocks = parse_sidecar(side.read_text(encoding="utf-8")) if side.is_file() else {}
    blockers = []
    for anchor in anchors:
        if anchor not in blocks:
            blockers.append(f"illus:{anchor}: no sidecar block")
        elif blocks[anchor] is None or blocks[anchor].lower() == "unresolved":
            blockers.append(f"illus:{anchor}: selection unresolved")
    return {
        "resolved": not blockers,
        "sidecar": str(side),
        "sidecar_present": side.is_file(),
        "planned_visual_count": len(anchors),
        "blockers": blockers,
    }


def check_source(essays):
    hits = []
    for essay in essays:
        lines = essay.read_text(encoding="utf-8").splitlines()
        body, offset = _strip_frontmatter(lines)
        for i, line in enumerate(body):
            if NEEDS_SOURCE_RE.search(line):
                hits.append({"file": str(essay), "line": offset + i + 1, "text": line.strip()})
    return {"resolved": not hits, "needs_source_count": len(hits), "locations": hits}


def main():
    ap = argparse.ArgumentParser(description="pv-prosevoice READY checks (planned visuals + sources)")
    ap.add_argument("essays", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()
    for essay in args.essays:
        if not essay.is_file():
            print(f"error: essay not found: {essay}", file=sys.stderr)
            return 2

    try:
        image = {str(essay): check_image(essay) for essay in args.essays}
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error), "ready": False}))
        return 2
    source = check_source(args.essays)
    ready = all(v["resolved"] for v in image.values()) and source["resolved"]
    result = {"ready": ready, "image": image, "source": source}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"READY preconditions: {'PASS' if ready else 'BLOCKED'}")
        for path, value in image.items():
            for blocker in value["blockers"]:
                print(f"  VISUAL ({path}): {blocker}")
        for location in source["locations"]:
            print(f"  SOURCE: {location['file']}:{location['line']}: {location['text']}")
    return 0 if ready else 3


if __name__ == "__main__":
    sys.exit(main())
