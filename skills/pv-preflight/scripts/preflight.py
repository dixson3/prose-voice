#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""pv-preflight: dependency, voice-file and companion-rule checks for pv-prosevoice.

Subcommands (all print JSON on stdout):

  check                                  full report: deps, voice files, rule targets
  resolve                                required voice and optional visual reference paths
  seed    --scope project|global [--apply]
                                         copy blank VOICE.md / AUDIENCE.md templates into
                                         <git-root>/.prose-voice/ or ~/.prose-voice/; never
                                         overwrites an existing file
  artifacts ESSAY [--apply]              resolve intermediate paths; prepare cache when applied
  rule    [--remove] [--apply]           install (or remove) PV-PROTOCOL.md wherever
                                         pv-prosevoice is installed

`seed` and `rule` are dry runs unless `--apply` is given.

Voice-file resolution is per file, first usable match wins:
  configured .pv/config.json guidance paths -> <git-root>/.prose-voice/<file>
  -> ~/.prose-voice/<file>
Intermediate artifact placement is controlled by .pv/config.json; default .pv/cache/.
A file is usable when it exists, is non-empty, and no longer carries the
`pv-template: unfilled` marker.

Rule targets follow where pv-prosevoice is installed (project = git root, global = $HOME):
  .claude/skills/pv-prosevoice             -> .claude/rules/PV-PROTOCOL.md
  <root>/.agents/skills/pv-prosevoice      -> managed block in <root>/AGENTS.md
  ~/.agents/skills/pv-prosevoice           -> managed block in ~/.pi/agent/AGENTS.md (if ~/.pi
                                              exists) and ~/.codex/AGENTS.md (if ~/.codex exists)
  ~/.config/opencode/skills/pv-prosevoice  -> managed block in ~/.config/opencode/AGENTS.md
Legacy blog-voice rule artifacts in those locations are reported and removed by `rule --apply`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pv_config import artifact_paths, extra_guidance, load_config, prepare_artifacts

SKILL = "pv-prosevoice"
HERE = Path(__file__).resolve().parent.parent  # the pv-preflight skill dir
PROTOCOL = HERE / "PV-PROTOCOL.md"
TEMPLATES = HERE / "templates"
VOICE_FILES = ("VOICE.md", "AUDIENCE.md")
REFERENCE_FILES = (*VOICE_FILES, "ILLUSTRATIONS.md")
UNFILLED = "pv-template: unfilled"
BEGIN = "<!-- BEGIN pv-protocol (managed by pv-preflight; edits are overwritten) -->"
END = "<!-- END pv-protocol -->"
LEGACY_BEGIN = "<!-- BEGIN blog-voice rule (managed by blog-voice/install.sh; edits are overwritten) -->"
LEGACY_END = "<!-- END blog-voice rule -->"
DEPS = {
    "uv": "required — runs the helper scripts",
    "git": "required — locates the project root",
    "harper-cli": "optional — grammar step (brew install harper); absent, it is skipped",
    "naba": "optional raster generator — alternatives include available image tools; not a gate",
}


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(out).resolve() if out else None


def file_state(path: Path) -> str:
    if not path.is_file():
        return "absent"
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return "empty"
    if UNFILLED in text:
        return "unfilled"
    return "ok"


def candidates(name: str, root: Path | None) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = [("configured", p) for p in extra_guidance(root, name)]
    if root is not None:
        out.append(("project", root / ".prose-voice" / name))
    out.append(("global", Path.home() / ".prose-voice" / name))
    return out


def resolve(root: Path | None) -> dict:
    result = {}
    for name in REFERENCE_FILES:
        tried = []
        chosen = None
        for level, path in candidates(name, root):
            state = file_state(path)
            tried.append({"level": level, "path": str(path), "state": state})
            if state == "ok" and chosen is None:
                chosen = {"level": level, "path": str(path)}
        result[name] = {"resolved": chosen, "tried": tried}
    return result


def read_block(text: str, begin: str, end: str) -> str | None:
    lines = text.splitlines()
    try:
        i = lines.index(begin)
        j = lines.index(end, i + 1)
    except ValueError:
        return None
    return "\n".join(lines[i + 1 : j]).strip("\n")


def strip_block(text: str, begin: str, end: str) -> str:
    out, skip = [], False
    for line in text.splitlines():
        if line == begin:
            skip = True
            continue
        if line == end:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip("\n")


def rule_targets(root: Path | None) -> list[dict]:
    home = Path.home()
    targets: list[dict] = []
    bases = [("project", root)] if root is not None else []
    bases.append(("global", home))
    for scope, base in bases:
        if (base / ".claude/skills" / SKILL).exists():
            targets.append({
                "scope": scope, "harness": "claude-code", "kind": "file",
                "path": base / ".claude/rules/PV-PROTOCOL.md",
                "legacy": base / ".claude/rules/BLOG_VOICE.md",
            })
        agents_installed = (base / ".agents/skills" / SKILL).exists()
        if scope == "project" and agents_installed:
            targets.append({"scope": scope, "harness": "pi|codex|opencode", "kind": "block",
                            "path": base / "AGENTS.md"})
        if scope == "global":
            if agents_installed and (home / ".pi").is_dir():
                targets.append({"scope": scope, "harness": "pi", "kind": "block",
                                "path": home / ".pi/agent/AGENTS.md"})
            if agents_installed and (home / ".codex").is_dir():
                targets.append({"scope": scope, "harness": "codex", "kind": "block",
                                "path": home / ".codex/AGENTS.md"})
            if (home / ".config/opencode/skills" / SKILL).exists():
                targets.append({"scope": scope, "harness": "opencode", "kind": "block",
                                "path": home / ".config/opencode/AGENTS.md"})
    return targets


def target_state(t: dict, protocol: str) -> dict:
    path: Path = t["path"]
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    legacy = False
    if t["kind"] == "file":
        if text is None:
            state = "missing"
        else:
            state = "current" if text.strip("\n") == protocol else "stale"
        legacy = t["legacy"].exists()
    else:
        body = read_block(text, BEGIN, END) if text is not None else None
        if body is None:
            state = "missing"
        else:
            state = "current" if body == protocol else "stale"
        legacy = text is not None and LEGACY_BEGIN in text
    return {"scope": t["scope"], "harness": t["harness"], "kind": t["kind"],
            "path": str(path), "state": state, "legacy_blog_voice": legacy}


def apply_target(t: dict, protocol: str, remove: bool) -> None:
    path: Path = t["path"]
    if t["kind"] == "file":
        if t["legacy"].exists():
            t["legacy"].unlink()
        if remove:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(protocol + "\n", encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    text = strip_block(strip_block(text, LEGACY_BEGIN, LEGACY_END), BEGIN, END)
    if not remove:
        block = f"{BEGIN}\n{protocol}\n{END}"
        text = f"{text}\n\n{block}" if text.strip() else block
    if text.strip() or path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip("\n") + "\n" if text.strip() else "", encoding="utf-8")


def cmd_check(root: Path | None) -> dict:
    protocol = PROTOCOL.read_text(encoding="utf-8").strip("\n")
    deps = {name: {"found": shutil.which(name) is not None, "note": note}
            for name, note in DEPS.items()}
    voice = resolve(root)
    rules = [target_state(t, protocol) for t in rule_targets(root)]
    actions = []
    missing_req = [n for n in ("uv", "git") if not deps[n]["found"]]
    if missing_req:
        actions.append(f"install required tools: {', '.join(missing_req)}")
    unresolved = [n for n in VOICE_FILES if voice[n]["resolved"] is None]
    if unresolved:
        actions.append(f"seed and fill in {', '.join(unresolved)} "
                       "(preflight.py seed --scope project|global --apply)")
    if any(r["state"] != "current" or r["legacy_blog_voice"] for r in rules):
        actions.append("install or refresh PV-PROTOCOL.md (preflight.py rule --apply)")
    if not rules:
        actions.append(f"{SKILL} not found in any project or global skill dir; "
                       "install with npx skills add (see README)")
    return {
        "ready": not missing_req and not unresolved,
        "git_root": str(root) if root else None,
        "deps": deps,
        "voice": voice,
        "rules": rules,
        "actions": actions,
    }


def cmd_seed(root: Path | None, scope: str, apply: bool) -> dict:
    if scope == "project":
        if root is None:
            return {"error": "--scope project needs a git working directory"}
        dest = root / ".prose-voice"
    else:
        dest = Path.home() / ".prose-voice"
    results = []
    for name in VOICE_FILES:
        target = dest / name
        if target.exists():
            results.append({"path": str(target), "action": "kept (exists)"})
            continue
        if apply:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATES / name, target)
        results.append({"path": str(target), "action": "seeded" if apply else "would seed"})
    return {"scope": scope, "applied": apply, "files": results}


def cmd_rule(root: Path | None, remove: bool, apply: bool) -> dict:
    protocol = PROTOCOL.read_text(encoding="utf-8").strip("\n")
    targets = rule_targets(root)
    before = [target_state(t, protocol) for t in targets]
    if apply:
        for t in targets:
            apply_target(t, protocol, remove)
    after = [target_state(t, protocol) for t in targets] if apply else None
    return {"action": "remove" if remove else "install", "applied": apply,
            "before": before, "after": after}


def main() -> int:
    p = argparse.ArgumentParser(description="pv-preflight checks for pv-prosevoice")
    p.add_argument("--cwd", default=os.getcwd(), help="directory whose git root is the project")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("resolve")
    artifacts = sub.add_parser("artifacts", help="resolve intermediate paths; --apply prepares cache and ignore rule")
    artifacts.add_argument("essay", type=Path)
    artifacts.add_argument("--apply", action="store_true")
    s = sub.add_parser("seed")
    s.add_argument("--scope", choices=("project", "global"), required=True)
    s.add_argument("--apply", action="store_true")
    s = sub.add_parser("rule")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--apply", action="store_true")
    args = p.parse_args()

    root = git_root(Path(args.cwd))
    try:
        load_config(root)
        if args.cmd == "check":
            out = cmd_check(root)
        elif args.cmd == "resolve":
            out = resolve(root)
        elif args.cmd == "artifacts":
            operation = prepare_artifacts if args.apply else artifact_paths
            out = {key: str(path) for key, path in operation(args.essay, root).items()}
        elif args.cmd == "seed":
            out = cmd_seed(root, args.scope, args.apply)
        else:
            out = cmd_rule(root, args.remove, args.apply)
    except (ValueError, OSError) as error:
        out = {"error": str(error), "ready": False}
    print(json.dumps(out, indent=2))
    return 1 if "error" in out else 0


if __name__ == "__main__":
    sys.exit(main())
