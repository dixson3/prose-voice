"""Preflight report, companion-rule targets and the conservative managed-block parser.

The companion rule is ``PROSEVOICE-PROTOCOL.md``. Targets follow where the ``prosevoice``
skill is installed (project = selected project root, global = ``$HOME``):

  .claude/skills/prosevoice              -> .claude/rules/PROSEVOICE-PROTOCOL.md
  <project>/.agents/skills/prosevoice    -> managed block in <project>/AGENTS.md
  ~/.agents/skills/prosevoice            -> managed blocks in the existing pi, Codex and
                                            OpenCode harness AGENTS.md files
  ~/.config/opencode/skills/prosevoice   -> managed block in ~/.config/opencode/AGENTS.md

Targets are deduplicated by path. Normal refresh recognizes only this installation and
rule identity; legacy rules are handled solely by migration.

The block parser is shared with migration. It accepts zero or one well-formed block per
file and rejects unpaired, nested, duplicate or malformed marker lines. Edits replace only
the block's lines; every unrelated byte, including line endings, is retained.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import resource
from .config import REQUIRED_GUIDES, Config, resolve_guidance
from .errors import ProsevoiceError

SKILL = "prosevoice"
PROTOCOL_NAME = "PROSEVOICE-PROTOCOL.md"
BEGIN = "<!-- BEGIN prosevoice (managed by prosevoice rule; edits are overwritten) -->"
END = "<!-- END prosevoice -->"
DEPS = {
    "uv": "required — runs the helper commands",
    "git": "required — locates the project root",
    "harper-cli": "optional — grammar step (brew install harper); absent, it is skipped",
    "naba": "optional raster generator — alternatives include available image tools; not a gate",
}
REQUIRED_DEPS = ("uv", "git")


# ======================================================================= block parser


class BlockError(ProsevoiceError):
    """A managed block is malformed, nested or duplicated."""

    def __init__(self, message: str, path: Path | None = None):
        super().__init__("managed-block-malformed", message, paths=[path] if path else [])


@dataclass(frozen=True)
class Block:
    """Line indices (into ``splitlines(keepends=True)``) of one managed block."""

    begin: int
    end: int
    body: str


def _marker_prefix(marker: str) -> str:
    prefix = marker.split(" (", 1)[0]
    return prefix.removesuffix(" -->").rstrip()


def _looks_like(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    rest = line[len(prefix):]
    return rest == "" or rest[0] in " -("


def find_block(text: str, begin: str, end: str, path: Path | None = None) -> Block | None:
    """Return the single managed block in ``text`` or ``None``; raise ``BlockError`` otherwise."""
    begin_prefix, end_prefix = _marker_prefix(begin), _marker_prefix(end)
    lines = text.splitlines(keepends=True)
    blocks: list[Block] = []
    open_at: int | None = None
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if _looks_like(stripped, begin_prefix):
            if line != begin:
                raise BlockError(f"line {index + 1}: malformed begin marker {stripped!r}", path)
            if open_at is not None:
                raise BlockError(f"line {index + 1}: nested begin marker", path)
            open_at = index
        elif _looks_like(stripped, end_prefix):
            if line != end:
                raise BlockError(f"line {index + 1}: malformed end marker {stripped!r}", path)
            if open_at is None:
                raise BlockError(f"line {index + 1}: end marker without begin", path)
            body = "".join(lines[open_at + 1:index]).replace("\r\n", "\n").strip("\n")
            blocks.append(Block(open_at, index, body))
            open_at = None
    if open_at is not None:
        raise BlockError(f"line {open_at + 1}: begin marker without end", path)
    if len(blocks) > 1:
        raise BlockError(f"{len(blocks)} managed blocks found; expected at most one", path)
    return blocks[0] if blocks else None


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def replace_block(text: str, begin: str, end: str, content: str | None,
                  path: Path | None = None) -> str:
    """Install (``content``) or remove (``None``) the managed block, retaining other bytes."""
    block = find_block(text, begin, end, path)
    nl = _newline(text)
    lines = text.splitlines(keepends=True)
    rendered = "" if content is None else nl.join([begin, *content.strip("\n").split("\n"), end]) + nl
    if block is None:
        if content is None:
            return text
        if not text.strip():
            return rendered
        sep = "" if text.endswith(("\n", "\r")) else nl
        return f"{text}{sep}{nl}{rendered}"
    before, after = lines[:block.begin], lines[block.end + 1:]
    if content is not None:
        tail = "".join(after)
        if not tail and not lines[block.end].endswith(("\n", "\r")):
            rendered = rendered[: -len(nl)]
        return "".join(before) + rendered + tail
    # Removal: drop the block and, when it ended the file, the blank separator before it.
    if not "".join(after).strip() and before and not before[-1].strip():
        before = before[:-1]
    return "".join(before) + "".join(after)


# ======================================================================= targets


def protocol_text() -> str:
    return resource(PROTOCOL_NAME).read_text(encoding="utf-8").strip("\n")


def rule_targets(config: Config, home: Path | None = None) -> list[dict]:
    home = home or Path.home()
    bases = [("project", config.project_root), ("global", home)]
    targets: list[dict] = []
    seen: set[Path] = set()

    def add(scope: str, harness: str, kind: str, path: Path) -> None:
        key = path.resolve() if path.parent.exists() else path
        if key in seen:
            return
        seen.add(key)
        targets.append({"scope": scope, "harness": harness, "kind": kind, "path": path})

    for scope, base in bases:
        if (base / ".claude/skills" / SKILL).exists():
            add(scope, "claude-code", "file", base / ".claude/rules" / PROTOCOL_NAME)
        agents_installed = (base / ".agents/skills" / SKILL).exists()
        if scope == "project" and agents_installed:
            add(scope, "pi|codex|opencode", "block", base / "AGENTS.md")
        if scope == "global":
            if agents_installed and (home / ".pi").is_dir():
                add(scope, "pi", "block", home / ".pi/agent/AGENTS.md")
            if agents_installed and (home / ".codex").is_dir():
                add(scope, "codex", "block", home / ".codex/AGENTS.md")
            if ((agents_installed and (home / ".config/opencode").is_dir())
                    or (home / ".config/opencode/skills" / SKILL).exists()):
                add(scope, "opencode", "block", home / ".config/opencode/AGENTS.md")
    return targets


def target_state(target: dict, protocol: str) -> dict:
    path: Path = target["path"]
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    detail = None
    if target["kind"] == "file":
        state = "missing" if text is None else ("current" if text.strip("\n") == protocol else "stale")
    else:
        try:
            block = find_block(text, BEGIN, END, path) if text is not None else None
        except BlockError as error:
            state, block, detail = "malformed", None, error.message
        else:
            state = "missing" if block is None else ("current" if block.body == protocol else "stale")
    report = {"scope": target["scope"], "harness": target["harness"], "kind": target["kind"],
              "path": str(path), "state": state}
    if detail:
        report["detail"] = detail
    return report


def planned_action(state: str, remove: bool) -> str:
    if state == "malformed":
        return "refuse"
    if remove:
        return "none" if state == "missing" else "remove"
    return "none" if state == "current" else ("install" if state == "missing" else "refresh")


def apply_target(target: dict, protocol: str, remove: bool) -> bool:
    """Apply one target; True when bytes changed."""
    path: Path = target["path"]
    if target["kind"] == "file":
        if remove:
            if path.is_file():
                path.unlink()
                return True
            return False
        wanted = protocol + "\n"
        if path.is_file() and path.read_text(encoding="utf-8") == wanted:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted, encoding="utf-8")
        return True
    original = path.read_bytes().decode("utf-8") if path.is_file() else ""
    updated = replace_block(original, BEGIN, END, None if remove else protocol, path)
    if updated == original:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    return True


def rule(config: Config, *, apply: bool, remove: bool, home: Path | None = None) -> dict:
    """Preview (default) or apply rule install/removal; refuse every write if any target is malformed."""
    protocol = protocol_text()
    targets = rule_targets(config, home)
    before = [target_state(t, protocol) for t in targets]
    for state in before:
        state["action"] = planned_action(state["state"], remove)
    blocked = any(s["action"] == "refuse" for s in before)
    changed: list[str] = []
    if apply and not blocked:
        for target in targets:
            if apply_target(target, protocol, remove):
                changed.append(str(target["path"]))
    after = [target_state(t, protocol) for t in targets] if apply and not blocked else None
    return {"action": "remove" if remove else "install", "applied": bool(apply and not blocked),
            "blocked": blocked, "targets": before, "changed": changed, "after": after,
            "installation_found": bool(targets)}


# ======================================================================= check


def check(config: Config, home: Path | None = None) -> dict:
    """Dependencies, guidance resolution and rule state; never writes."""
    deps = {name: {"found": shutil.which(name) is not None, "note": note} for name, note in DEPS.items()}
    guidance = resolve_guidance(config)
    protocol = protocol_text()
    rules = []
    for target in rule_targets(config, home):
        rules.append(target_state(target, protocol))
    actions = []
    missing_req = [n for n in REQUIRED_DEPS if not deps[n]["found"]]
    if missing_req:
        actions.append(f"install required tools: {', '.join(missing_req)}")
    unresolved = [n for n in REQUIRED_GUIDES if guidance[n]["resolved"] is None]
    if unresolved:
        actions.append(f"seed and fill in {', '.join(unresolved)} "
                       "(prosevoice init --scope project|user, then remove the unfilled marker)")
    if any(r["state"] != "current" for r in rules):
        actions.append(f"install or refresh {PROTOCOL_NAME} (prosevoice rule, then prosevoice rule --apply)")
    if not rules:
        actions.append(f"{SKILL} not found in any project or global skill dir; "
                       "install with npx skills add (see README)")
    return {
        "ready": not missing_req and not unresolved,
        "project": str(config.project_root),
        "deps": deps,
        "guidance": guidance,
        "rules": rules,
        "actions": actions,
    }
