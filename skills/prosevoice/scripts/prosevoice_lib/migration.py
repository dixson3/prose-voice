"""Explicit, bounded migration from legacy prose-voice data and companion rules.

``prosevoice migrate`` is the only runtime code that reads ``.prose-voice`` trees, the
legacy ``~/.prose-voice`` user directory and legacy rule identities (``PV-PROTOCOL.md``,
``BLOG_VOICE.md``, ``pv-protocol`` / ``blog-voice`` managed blocks). Ordinary commands
never look at them.

Scopes
  project (default)  <project>/.prose-voice -> <project>/.prosevoice, plus project rule
                     targets. Never writes the user directory or global rules.
  user               legacy user dir (default ~/.prose-voice) -> the prosevoice user dir
                     (default $XDG_CONFIG_HOME/prosevoice or ~/.config/prosevoice), plus
                     global rule targets under $HOME. Never writes project files.

Preview is the default and writes nothing. ``--apply`` preflights every input and
destination, records a manifest at ``<scope dir>/migrations/<id>/manifest.json``, backs up
replaced rules there, stages changed bytes, atomically replaces each destination, verifies
equivalence through the shared resolver and only then activates the new rules. A rerun
resumes an unfinished manifest when every file still matches its recorded state.

Legacy sources are retained unchanged and inactive. Removing legacy skill installations
is an explicit installer task for the operator.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import itertools
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import essay as essay_mod
from . import policy as policy_mod
from . import rules as rules_mod
from .config import (
    ARTIFACT_KINDS,
    ARTIFACT_LOCATIONS,
    CONFIG_NAME,
    GUIDES,
    PROJECT_DIR,
    SCHEMA_VERSION,
    artifact_paths,
    build_config,
    file_state,
    loads_strict,
    read_config_file,
    resolve_guidance,
    select_project,
    text_state,
    user_config_dir,
)
from .errors import ProsevoiceError

MIGRATION_VERSION = 1
LEGACY_DIR = ".prose-voice"
LEGACY_USER_DIR = ".prose-voice"
POLICY_FILES = (policy_mod.DICTIONARY, policy_mod.IGNORE_RULES)
STANDARD_FILES = (*GUIDES, *POLICY_FILES, ".gitignore")
LEGACY_RULE_FILES = ("PV-PROTOCOL.md", "BLOG_VOICE.md")
LEGACY_BLOCKS = {
    "pv-protocol": ("<!-- BEGIN pv-protocol (managed by pv-preflight; edits are overwritten) -->",
                    "<!-- END pv-protocol -->"),
    "blog-voice": ("<!-- BEGIN blog-voice rule (managed by blog-voice/install.sh; edits are overwritten) -->",
                   "<!-- END blog-voice rule -->"),
}
# SHA-256 of every released legacy protocol text, normalized to LF and stripped of
# leading/trailing newlines. Rule content outside this set is an unfamiliar modification.
KNOWN_PROTOCOLS = {
    "978dcac0f665833c56254122e45d3803952e429cb4c3c232e34e768124f8df88": "PV-PROTOCOL.md (b01e89e)",
    "bb15fade5e7b0c150ea3a6dc159b8f7cdce5443ff0186aec3a776ed48091d56a": "PV-PROTOCOL.md (041bbdd)",
    "dd19c186040a666ad591960ef9cf45d0d3567215115e9f4945373db8aac97f67": "PV-PROTOCOL.md (6624722)",
    "a823fb76dbbec46c5b0ed4208dabecb5849aa557be1e3c0612a9828410f59217": "PV-PROTOCOL.md (6959b63)",
    "0f124849b9ba6febeeca3b3a391b80a2110af7ad41500eac145ce46c688b973a": "BLOG_VOICE.md (2215c5a)",
}
INSTALL_HINT = ("install the prosevoice skill for this harness first, e.g. "
                "npx skills add <prosevoice-source> -s prosevoice -a <agent> (add -g for global); "
                "migration never removes legacy installations or edits installer locks")

# Test-only interruption hook: called as FAULT_HOOK(point, action) at apply boundaries.
FAULT_HOOK = None


class Interrupted(ProsevoiceError):
    """Raised by tests through ``FAULT_HOOK`` to simulate an interrupted apply."""

    def __init__(self, point: str):
        super().__init__("migration-interrupted", f"apply interrupted at {point}")


def _checkpoint(point: str, action: dict | None = None) -> None:
    if FAULT_HOOK is not None:
        FAULT_HOOK(point, action)


# ======================================================================= helpers


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm_text_hash(text: str) -> str:
    return sha(text.replace("\r\n", "\n").strip("\n").encode("utf-8"))


def _norm(path: Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


def _inside(path: Path, root: Path) -> bool:
    try:
        _norm(path).relative_to(_norm(root))
    except ValueError:
        return False
    return True


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError:
        return None


def _hash_of(path: Path) -> str | None:
    if path.is_symlink() and not path.exists():
        return "dangling-symlink"
    data = _read(path)
    return None if data is None else sha(data)


def _key(path: Path) -> str:
    return str(Path(os.path.abspath(path)).resolve())


def _symlink_component(path: Path, root: Path) -> Path | None:
    """The first existing symlink from ``root`` (exclusive) down to ``path`` (inclusive)."""
    current = _norm(root)
    for part in _norm(path).relative_to(current).parts:
        current = current / part
        if current.is_symlink():
            return current
    return None


def _blk(code: str, message: str, paths=(), **extra) -> dict:
    out = {"code": code, "message": message, "paths": [str(p) for p in paths]}
    out.update(extra)
    return out


# ======================================================================= plan model


@dataclass
class Plan:
    scope: str
    roots: dict
    manifest_base: Path
    inputs: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    staged: dict = field(default_factory=dict)  # action id -> bytes
    unchanged: list = field(default_factory=list)
    blockers: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    external: list = field(default_factory=list)
    retained: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    link_rewrites: list = field(default_factory=list)
    translated_config: dict | None = None
    equivalence: dict = field(default_factory=dict)
    essays: list = field(default_factory=list)
    verify: object = None  # callable(overlay) -> (equivalence, blockers, dependencies)
    write_roots: dict = field(default_factory=dict)  # phase -> root

    def read_input(self, path: Path) -> bytes | None:
        data = _read(path)
        self.inputs[str(path)] = None if data is None else sha(data)
        return data

    def overlay(self) -> dict:
        out = {}
        for action in self.actions:
            out[_key(Path(action["path"]))] = self.staged.get(action["id"]) if action["op"] == "write" else None
        return out

    def add_write(self, dest: Path, data: bytes, kind: str, root: Path, phase: str = "data",
                  source: Path | None = None, backup: bool = False) -> None:
        dest = _norm(dest)
        if any(a["path"] == str(dest) for a in self.actions):
            existing = next(a for a in self.actions if a["path"] == str(dest))
            if existing["after"] != sha(data):
                self.blockers.append(_blk("mapping-ambiguous", "two legacy sources map to one destination "
                                          "with different content", [dest]))
            return
        if not self.safe_destination(dest, root):
            return
        if dest.exists() and not dest.is_file():
            self.blockers.append(_blk("destination-not-file", "destination exists and is not a file", [dest]))
            return
        current = _read(dest)
        if current == data:
            if not any(u["path"] == str(dest) for u in self.unchanged):
                self.unchanged.append({"path": str(dest), "kind": kind, "reason": "identical bytes",
                                       "source": str(source) if source else None})
            return
        if current is not None and not backup:
            self.blockers.append(_blk(
                "destination-conflict", "destination exists with different content; resolve it manually "
                "(compare with the legacy source) and rerun", [dest, *([source] if source else [])],
                expected=sha(data), actual=sha(current)))
            return
        self.add_action("write", dest, kind, phase, source, before=current, after=data, backup=backup)

    def add_action(self, op: str, dest: Path, kind: str, phase: str, source: Path | None,
                   before: bytes | None, after: bytes | None, backup: bool) -> None:
        action = {"id": len(self.actions) + 1, "op": op, "kind": kind, "phase": phase,
                  "path": str(dest), "source": str(source) if source else None,
                  "before": None if before is None else sha(before),
                  "after": None if after is None else sha(after),
                  "backup": backup, "state": "pending"}
        self.actions.append(action)
        if op == "write":
            self.staged[action["id"]] = after

    def safe_destination(self, dest: Path, root: Path) -> bool:
        if not _inside(dest, root):
            self.blockers.append(_blk("destination-escape", f"destination is outside the {self.scope} scope",
                                      [dest, root]))
            return False
        link = _symlink_component(dest, root)
        if link is not None:
            self.blockers.append(_blk("destination-symlink", "destination path passes through a symlink; "
                                      "replace it with a real directory/file or remove it", [link]))
            return False
        return True


# ======================================================================= legacy config


def _parse_legacy_config(plan: Plan, path: Path) -> dict | None:
    data = plan.read_input(path)
    if data is None:
        plan.blockers.append(_blk("legacy-config-unreadable", "legacy config is not a readable file", [path]))
        return None
    try:
        doc = loads_strict(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        plan.blockers.append(_blk("legacy-config-invalid", f"malformed legacy config: {error}", [path]))
        return None
    if not isinstance(doc, dict):
        plan.blockers.append(_blk("legacy-config-invalid", "legacy config must be a JSON object", [path]))
        return None
    unknown = sorted(set(doc) - {"guidance", "artifacts"})
    if unknown:
        plan.blockers.append(_blk("legacy-config-unknown", "unknown legacy configuration semantics: "
                                  f"{', '.join(unknown)}; translate them manually", [path]))
        return None
    guidance = doc.get("guidance", {})
    problems = []
    if not isinstance(guidance, dict) or set(guidance) - set(GUIDES):
        problems.append("guidance keys must be VOICE.md, AUDIENCE.md or ILLUSTRATIONS.md")
    else:
        for name, value in guidance.items():
            if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
                problems.append(f"guidance.{name} must be an ordered list of path strings")
    artifacts = doc.get("artifacts", {})
    if not isinstance(artifacts, dict) or set(artifacts) - {"location"}:
        problems.append("artifacts must contain only location")
    elif artifacts.get("location", "cache") not in ARTIFACT_LOCATIONS:
        problems.append("artifacts.location must be cache or adjacent")
    if problems:
        plan.blockers.append(_blk("legacy-config-invalid", "; ".join(problems), [path]))
        return None
    return doc


def _legacy_candidate(value: str, root: Path) -> Path:
    raw = Path(value).expanduser()
    return _norm(raw if raw.is_absolute() else root / raw)


# ======================================================================= links


FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_RE = re.compile(r"(!?\[[^\]\n]*\]\()([^)\s]*)((?:\s+\"[^\"\n]*\")?\))")
REFDEF_RE = re.compile(r"^(\s{0,3}\[[^\]\n]+\]:[ \t]*)(\S+)(.*)$")
FIELD_RE = re.compile(r"^(\s*[-*]\s+(?:Source|Render):[ \t]*)(\S+)([ \t]*)$")
HTML_RE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _is_relative_target(target: str) -> bool:
    return bool(target) and not (target.startswith(("#", "/", "~", "\\")) or SCHEME_RE.match(target))


def rebase_links(text: str, old_dir: Path, new_dir: Path, sidecar: Path) -> tuple[str, list, list]:
    """Rewrite relative links so they reach the same targets from ``new_dir``.

    Recognized: inline links/images, reference definitions and ``- Source:``/``- Render:``
    path fields outside fenced code. Relative raw-HTML ``src``/``href`` and angle-bracket
    targets are unsupported and returned as problems.
    """
    rewrites, problems = [], []

    def rebase(target: str, lineno: int) -> str:
        if target.startswith("<"):
            problems.append(_blk("link-unsupported", f"line {lineno}: angle-bracket link target", [sidecar]))
            return target
        if not _is_relative_target(target):
            return target
        cut = min([i for i in (target.find("#"), target.find("?")) if i >= 0], default=len(target))
        path, suffix = target[:cut], target[cut:]
        if not path:
            return target
        absolute = _norm(old_dir / path)
        new = Path(os.path.relpath(absolute, _norm(new_dir))).as_posix()
        if new == path:
            return target
        rewrites.append({"sidecar": str(sidecar), "line": lineno, "from": target, "to": new + suffix,
                         "target": str(absolute)})
        return new + suffix

    out, fenced = [], False
    for index, line in enumerate(text.splitlines(keepends=True), 1):
        if FENCE_RE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        for match in HTML_RE.finditer(line):
            if _is_relative_target(match.group(1)):
                problems.append(_blk("link-unsupported", f"line {index}: relative HTML link "
                                     f"{match.group(1)!r} cannot be rebased; use a Markdown link", [sidecar]))
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        body = INLINE_RE.sub(lambda m, n=index: m.group(1) + rebase(m.group(2), n) + m.group(3), body)
        for regex in (REFDEF_RE, FIELD_RE):
            match = regex.match(body)
            if match and (regex is REFDEF_RE or "/" in match.group(2) or re.search(r"\.\w{1,8}$", match.group(2))):
                body = match.group(1) + rebase(match.group(2), index) + match.group(3)
        out.append(body + ending)
    return "".join(out), rewrites, problems


# ======================================================================= essays


def inventory_essays(root: Path) -> list[Path]:
    """Markdown essay sources under ``root``: hidden directories, nested repositories and
    intermediate ``<stem>.<kind>.md`` artifacts beside their essay are excluded."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames
                             if not n.startswith(".") and not (directory / n / ".git").exists()
                             and not (directory / n).is_symlink())
        for name in sorted(filenames):
            path = directory / name
            if not name.endswith(".md") or path.is_symlink():
                continue
            stem = name[:-3]
            if "." in stem:
                base, kind = stem.rsplit(".", 1)
                if kind in ARTIFACT_KINDS and (directory / f"{base}.md").exists():
                    continue
            found.append(path)
    return found


# ======================================================================= rules


def _rule_targets(base_config, home: Path) -> set[str]:
    return {str(_norm(t["path"])) for t in rules_mod.rule_targets(base_config, home)}


def _plan_rules(plan: Plan, claude_bases: list[Path], block_files: list[Path], targets: set[str],
                root: Path) -> None:
    protocol = rules_mod.protocol_text()
    wanted_file = (protocol + "\n").encode("utf-8")
    for base in claude_bases:
        rules_dir = base / ".claude/rules"
        legacy = [rules_dir / n for n in LEGACY_RULE_FILES if os.path.lexists(rules_dir / n)]
        if not legacy:
            continue
        ok = True
        for path in legacy:
            if path.is_symlink() or not path.is_file():
                plan.blockers.append(_blk("legacy-rule-unsupported", "legacy rule is a symlink or not a file; "
                                          "review and replace it manually", [path]))
                ok = False
                continue
            data = plan.read_input(path) or b""
            if norm_text_hash(data.decode("utf-8", "replace")) not in KNOWN_PROTOCOLS:
                plan.blockers.append(_blk("legacy-rule-unrecognized", "legacy rule content does not match a "
                                          "released protocol; review the modification manually", [path]))
                ok = False
        new = rules_dir / rules_mod.PROTOCOL_NAME
        if str(_norm(new)) not in targets:
            plan.blockers.append(_blk("installation-missing", f"no prosevoice installation for this Claude "
                                      f"rule target ({base / '.claude/skills/prosevoice'}); {INSTALL_HINT}",
                                      [new, *legacy]))
            ok = False
        if not ok:
            continue
        current = _read(new)
        if current is not None and current.decode("utf-8", "replace").replace("\r\n", "\n").strip("\n") != protocol:
            plan.blockers.append(_blk("rule-target-conflict", "the new rule file exists with different "
                                      "content; run prosevoice rule --apply first", [new]))
            continue
        plan.add_write(new, wanted_file, "rule-file", root, phase="rule")
        for path in legacy:
            if plan.safe_destination(path, root):
                plan.add_action("remove", _norm(path), "legacy-rule-file", "rule", None,
                                before=_read(path), after=None, backup=True)

    for path in block_files:
        if not os.path.lexists(path):
            continue
        if path.is_symlink() or not path.is_file():
            plan.blockers.append(_blk("legacy-rule-unsupported", "rule target is a symlink or not a file", [path]))
            continue
        data = plan.read_input(path) or b""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            plan.blockers.append(_blk("legacy-rule-unsupported", "rule target is not UTF-8", [path]))
            continue
        blocks = {}
        try:
            current = rules_mod.find_block(text, rules_mod.BEGIN, rules_mod.END, path)
            for name, (begin, end) in LEGACY_BLOCKS.items():
                blocks[name] = rules_mod.find_block(text, begin, end, path)
        except rules_mod.BlockError as error:
            plan.blockers.append(_blk("managed-block-malformed", f"{error.message}; fix the markers manually",
                                      [path]))
            continue
        found = sorted([(b.begin, b.end, name, b) for name, b in blocks.items() if b is not None])
        if not found:
            continue
        spans = sorted([(b.begin, b.end) for b in [current, *[f[3] for f in found]] if b is not None])
        if any(a[1] >= b[0] for a, b in itertools.pairwise(spans)):
            plan.blockers.append(_blk("managed-block-malformed", "managed blocks overlap or are nested", [path]))
            continue
        unknown = [name for _, _, name, b in found if norm_text_hash(b.body) not in KNOWN_PROTOCOLS]
        if unknown:
            plan.blockers.append(_blk("legacy-rule-unrecognized", f"legacy {', '.join(unknown)} block content "
                                      "does not match a released protocol; review it manually", [path]))
            continue
        if str(_norm(path)) not in targets:
            plan.blockers.append(_blk("installation-missing", f"no prosevoice installation selects this "
                                      f"AGENTS.md target; {INSTALL_HINT}", [path]))
            continue
        if current is not None and current.body != protocol:
            plan.blockers.append(_blk("rule-target-conflict", "a stale prosevoice block exists; run "
                                      "prosevoice rule --apply first", [path]))
            continue
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(keepends=True)
        out, index = [], 0
        for position, (begin, end, _name, _b) in enumerate(found):
            out.extend(lines[index:begin])
            if position == 0 and current is None:
                rendered = nl.join([rules_mod.BEGIN, *protocol.split("\n"), rules_mod.END]) + nl
                if not lines[end].endswith(("\n", "\r")):
                    rendered = rendered[:-len(nl)]
                out.append(rendered)
            index = end + 1
        out.extend(lines[index:])
        plan.add_write(path, "".join(out).encode("utf-8"), "rule-block", root, phase="rule", backup=True)


# ======================================================================= project scope


def _plan_project(root: Path, home: Path, legacy_user: Path, env) -> Plan:
    new_user = user_config_dir(env)
    legacy = root / LEGACY_DIR
    new_dir = root / PROJECT_DIR
    plan = Plan("project", {"project": str(root), "legacy_project_dir": str(legacy),
                            "project_dir": str(new_dir), "legacy_user_dir": str(legacy_user),
                            "user_dir": str(new_user), "home": str(home)},
                new_dir / "migrations")
    read_config_file(new_user / CONFIG_NAME)  # validate early: an invalid new config is exit 2
    existing_project = read_config_file(new_dir / CONFIG_NAME)
    base_config = build_config(root, root, "explicit", new_user, None, None)

    legacy_doc = None
    legacy_mode = "cache"
    legacy_present = False
    if legacy.is_symlink():
        plan.blockers.append(_blk("legacy-dir-symlink", "the legacy .prose-voice directory is a symlink; "
                                  "replace it with a real directory or migrate its target manually", [legacy]))
    elif legacy.is_dir():
        legacy_present = True
    config_ok = True
    if legacy_present and os.path.lexists(legacy / CONFIG_NAME):
        legacy_doc = _parse_legacy_config(plan, legacy / CONFIG_NAME)
        config_ok = legacy_doc is not None
        if legacy_doc is not None:
            legacy_mode = legacy_doc.get("artifacts", {}).get("location", "cache")

    # ---- standard files
    if legacy_present:
        for name in STANDARD_FILES:
            src = legacy / name
            if not os.path.lexists(src):
                continue
            if src.is_symlink() or not src.is_file():
                plan.blockers.append(_blk("legacy-symlink", "legacy file is a symlink or not a regular file; "
                                          "symlinks are external references and are not copied: replace it with "
                                          "a file, or point an explicit guidance entry at its target", [src]))
                continue
            plan.add_write(new_dir / name, plan.read_input(src) or b"", "copy", root, source=src)

    # ---- config translation
    if legacy_doc is not None:
        translated: dict = {"schema_version": SCHEMA_VERSION}
        if "guidance" in legacy_doc:
            translated["guidance"] = {}
            for name, values in legacy_doc["guidance"].items():
                translated["guidance"][name] = [
                    _translate_value(plan, value, root, legacy, legacy_user, new_user) for value in values]
        if "artifacts" in legacy_doc:
            translated["artifacts"] = dict(legacy_doc["artifacts"])
        plan.translated_config = translated
        dest = new_dir / CONFIG_NAME
        if existing_project is not None:
            if existing_project == translated:
                plan.unchanged.append({"path": str(dest), "kind": "config", "reason": "semantically identical"})
            else:
                actual = _read(dest) or b""
                plan.blockers.append(_blk("destination-conflict", "a prosevoice project config already exists "
                                          "with different settings; reconcile it with translated_config manually",
                                          [dest, legacy / CONFIG_NAME], expected=sha(_render_config(translated)),
                                          actual=sha(actual)))
        else:
            plan.add_write(dest, _render_config(translated), "config", root, source=legacy / CONFIG_NAME)

    # ---- inventory of other legacy content
    if legacy_present:
        known = {CONFIG_NAME, "cache", *STANDARD_FILES}
        copied = {a["source"] for a in plan.actions if a["source"]} | {u.get("source") for u in plan.unchanged}
        for path in sorted(legacy.rglob("*")):
            rel = path.relative_to(legacy)
            if rel.parts[0] == "cache" or path.is_dir() and not path.is_symlink():
                continue
            if rel.parts[0] in known and len(rel.parts) == 1:
                continue
            if str(path) not in copied:
                plan.retained.append({"path": str(path), "reason": "unknown legacy file left at source"})

    # ---- essays and illustration decisions
    sidecars_used: set[str] = set()
    if legacy_present or legacy_doc is not None:
        for essay_path in inventory_essays(root):
            _plan_essay(plan, essay_path, root, legacy, new_dir, legacy_mode, sidecars_used)
        cache = legacy / "cache"
        if cache.is_dir() and not cache.is_symlink():
            for path in sorted(cache.rglob("*")):
                if not path.is_file() or str(path) in sidecars_used:
                    continue
                if path.name.endswith(".illustrations.md"):
                    plan.warnings.append(_blk(
                        "sidecar-orphaned", "cached illustration decisions match no current essay; they are "
                        "retained at source, not migrated — move them beside the right essay's new cache route "
                        "by hand if still needed", [path]))
                    plan.retained.append({"path": str(path), "reason": "orphaned illustration sidecar"})
                else:
                    plan.skipped.append({"path": str(path), "reason": "disposable report history left inactive; "
                                         "regenerate it with the new cache routes when needed"})

    # ---- rules
    targets = _rule_targets(base_config, home)
    _plan_rules(plan, [root], [root / "AGENTS.md"], targets, root)

    if not (legacy_present or plan.actions or any(b["code"].startswith("legacy-rule") for b in plan.blockers)):
        if legacy_user.is_dir():
            plan.warnings.append(_blk("legacy-user-data", "legacy user data exists; migrate it with "
                                      "prosevoice migrate --scope user", [legacy_user]))
        return plan

    def verify(overlay: dict):
        read = _overlay_reader(overlay)
        cfg_path = new_dir / CONFIG_NAME
        if _key(cfg_path) in overlay:
            project_doc = json.loads(overlay[_key(cfg_path)])
        else:
            project_doc = read_config_file(cfg_path)
        cfg = build_config(root, root, "explicit", new_user, read_config_file(new_user / CONFIG_NAME),
                           project_doc, None, env)
        return _verify_project(cfg, read, root, legacy, legacy_user, legacy_doc, legacy_mode, plan.essays)

    plan.verify = verify
    if config_ok and not plan.blockers:
        equivalence, blockers, dependencies = verify(plan.overlay())
        plan.equivalence = equivalence
        plan.blockers += blockers
        plan.dependencies += dependencies
    return plan


def _render_config(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def _translate_value(plan: Plan, value: str, root: Path, legacy: Path, legacy_user: Path,
                     new_user: Path) -> str:
    absolute = _legacy_candidate(value, root)
    written_absolute = Path(value).is_absolute() or value.startswith("~")
    if _inside(absolute, legacy):
        rel = absolute.relative_to(_norm(legacy))
        src = legacy / rel
        link = _symlink_component(src, legacy) if rel.parts else None
        if link is not None:
            target = src.resolve()
            plan.external.append({"value": value, "translated": str(target), "referent": str(target),
                                  "ownership": "external (symlink inside the legacy tree; not copied)"})
            return str(target)
        new_rel = Path(PROJECT_DIR) / rel
        if src.is_file():
            plan.add_write(root / new_rel, plan.read_input(src) or b"", "copy", root, source=src)
        else:
            plan.warnings.append(_blk("guide-missing", "configured legacy guide does not exist; its "
                                      "translated candidate is also absent", [src]))
        return str(root / new_rel) if written_absolute else new_rel.as_posix()
    if _inside(absolute, legacy_user):
        rel = absolute.relative_to(_norm(legacy_user))
        new = new_user / rel
        plan.dependencies.append({"legacy": str(absolute), "requires": str(new),
                                  "remedy": "prosevoice migrate --scope user (or copy the file there)"})
        return str(new)
    owner = "project" if _inside(absolute, root) else "external"
    plan.external.append({"value": value, "translated": value, "referent": str(absolute),
                          "ownership": f"{owner} (retained, not copied or modified)"})
    return value


def _plan_essay(plan: Plan, essay_path: Path, root: Path, legacy: Path, new_dir: Path, mode: str,
                used: set[str]) -> None:
    rel = essay_path.relative_to(root)
    name = f"{essay_path.stem}.illustrations.md"
    cache_side = legacy / "cache" / rel.parent / name
    adjacent_side = essay_path.parent / name
    legacy_side, other = (cache_side, adjacent_side) if mode == "cache" else (adjacent_side, cache_side)
    try:
        text = essay_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        plan.blockers.append(_blk("essay-unreadable", f"cannot read essay: {error}", [essay_path]))
        return
    anchors = essay_mod.active_anchors(text)
    if not anchors and not os.path.lexists(legacy_side):
        return
    plan.read_input(essay_path)
    entry = {"essay": str(essay_path), "anchors": anchors, "legacy_sidecar": str(legacy_side),
             "new_sidecar": str(legacy_side)}
    if anchors and not os.path.lexists(legacy_side) and os.path.lexists(other):
        plan.blockers.append(_blk("sidecar-ambiguous", f"active anchors expect {mode}-mode decisions at "
                                  f"{legacy_side}, but a sidecar exists only at {other}; move the decisions "
                                  "to the expected path or fix artifacts.location, then rerun",
                                  [essay_path, legacy_side, other]))
        return
    if os.path.lexists(legacy_side):
        if legacy_side.is_symlink() or not legacy_side.is_file():
            plan.blockers.append(_blk("legacy-symlink", "legacy sidecar is a symlink or not a file", [legacy_side]))
            return
        used.add(str(legacy_side))
        data = plan.read_input(legacy_side) or b""
        if mode == "cache":
            new_side = new_dir / "cache" / rel.parent / name
            try:
                side_text = data.decode("utf-8")
            except UnicodeDecodeError:
                plan.blockers.append(_blk("sidecar-unsupported", "sidecar is not UTF-8", [legacy_side]))
                return
            rebased, rewrites, problems = rebase_links(side_text, legacy_side.parent, new_side.parent, legacy_side)
            if problems:
                plan.blockers += problems
                return
            plan.link_rewrites += rewrites
            plan.add_write(new_side, rebased.encode("utf-8"), "sidecar", root, source=legacy_side)
            entry["new_sidecar"] = str(_norm(new_side))
    plan.essays.append(entry)


def _overlay_reader(overlay: dict):
    def read(path: Path) -> bytes | None:
        key = _key(path)
        if key in overlay:
            return overlay[key]
        return _read(path)
    return read


def _legacy_guides(read, root: Path, legacy: Path, legacy_user: Path, legacy_doc: dict | None) -> dict:
    out = {}
    for name in GUIDES:
        candidates = [("configured", _legacy_candidate(v, root))
                      for v in (legacy_doc or {}).get("guidance", {}).get(name, [])]
        candidates += [("project", legacy / name), ("global", legacy_user / name)]
        chosen = None
        for level, path in candidates:
            if file_state(path) == "ok":
                chosen = {"level": level, "path": str(path), "sha256": sha(read(path) or b"")}
                break
        out[name] = chosen
    return out


def _words(read, paths, parse) -> tuple[set, dict]:
    words, origin = set(), {}
    for path in paths:
        data = read(path)
        if data is not None:
            for word in parse(data.decode("utf-8", "replace")):
                words.add(word)
                origin.setdefault(word, str(path))
    return words, origin


def _verify_project(cfg, read, root, legacy, legacy_user, legacy_doc, legacy_mode, essays):
    """Compare legacy effective guidance, policy, artifact mode and READY visuals with the new
    resolver's view of ``read`` (disk plus staged bytes)."""
    blockers, dependencies = [], []
    equivalence: dict = {"guidance": {}, "policy": {}, "artifacts": {}, "ready": []}

    def state_of(path: Path) -> str:
        data = read(path)
        return "absent" if data is None else text_state(data.decode("utf-8", "replace"))

    legacy_guides = _legacy_guides(read, root, legacy, legacy_user, legacy_doc)
    new_guides = resolve_guidance(cfg, state_of=state_of)
    for name in GUIDES:
        old = legacy_guides[name]
        chosen = new_guides[name]["resolved"]
        new = None if chosen is None else {**chosen, "sha256": sha(read(Path(chosen["path"])) or b"")}
        equal = (old is None and new is None) or (old is not None and new is not None
                                                  and old["sha256"] == new["sha256"])
        equivalence["guidance"][name] = {"legacy": old, "new": new, "equal": equal}
        if equal:
            continue
        if old is not None and (old["level"] == "global" or _inside(Path(old["path"]), legacy_user)):
            dependencies.append({"legacy": old["path"], "requires": str(cfg.user_dir / name),
                                 "remedy": "prosevoice migrate --scope user"})
            blockers.append(_blk("user-dependency-unmet", f"{name} resolves from the legacy user directory; "
                                 f"migrate user guidance first so {cfg.user_dir / name} holds identical content",
                                 [old["path"], cfg.user_dir / name]))
        else:
            blockers.append(_blk("guidance-not-equivalent", f"{name} would resolve to different content "
                                 f"(legacy {old and old['path']}, new {new and new['path']}); review the new "
                                 "user/project configuration", [p for p in (old and old["path"], new and new["path"]) if p]))

    dictionaries, ignores = policy_mod.policy_sources(cfg)
    for label, legacy_paths, new_paths, parse in (
        ("dictionary", [legacy_user / policy_mod.DICTIONARY, legacy / policy_mod.DICTIONARY], dictionaries[:2],
         policy_mod.words_from_text),
        ("ignore_rules", [legacy_user / policy_mod.IGNORE_RULES, legacy / policy_mod.IGNORE_RULES], ignores[:2],
         policy_mod.rules_from_text),
    ):
        old, origin = _words(read, legacy_paths, parse)
        new, _ = _words(read, new_paths, parse)
        missing, extra = sorted(old - new), sorted(new - old)
        equivalence["policy"][label] = {"legacy_count": len(old), "new_count": len(new),
                                        "missing": missing, "extra": extra, "equal": not missing and not extra}
        user_missing = [w for w in missing if origin[w] == str(legacy_user / legacy_paths[0].name)]
        if user_missing:
            dependencies.append({"legacy": str(legacy_paths[0]), "requires": str(new_paths[0]),
                                 "remedy": "prosevoice migrate --scope user"})
            blockers.append(_blk("user-dependency-unmet", f"{label} entries from the legacy user policy are "
                                 f"missing from {new_paths[0]}: {', '.join(user_missing[:10])}",
                                 [legacy_paths[0], new_paths[0]]))
        if extra or set(missing) - set(user_missing):
            blockers.append(_blk("policy-not-equivalent", f"{label} union differs (missing "
                                 f"{sorted(set(missing) - set(user_missing))[:10]}, extra {extra[:10]})",
                                 [*legacy_paths, *new_paths]))

    equal_mode = cfg.artifacts_location == legacy_mode
    equivalence["artifacts"] = {"legacy": legacy_mode, "new": cfg.artifacts_location, "equal": equal_mode}
    if not equal_mode:
        blockers.append(_blk("artifacts-not-equivalent", f"artifacts.location would change from {legacy_mode} to "
                             f"{cfg.artifacts_location}; review the user/project configuration", [cfg.project_config]))

    for entry in essays:
        essay_path = Path(entry["essay"])
        text = (read(essay_path) or b"").decode("utf-8", "replace")
        old_side = Path(entry["legacy_sidecar"])
        new_side = artifact_paths(cfg, essay_path)["illustrations"]
        old_text, new_text = read(old_side), read(new_side)
        old = essay_mod.image_outcome(text, None if old_text is None else old_text.decode("utf-8"), old_side)
        new = essay_mod.image_outcome(text, None if new_text is None else new_text.decode("utf-8"), new_side)
        same = (old["resolved"], old["blockers"], old["planned_visual_count"]) == (
            new["resolved"], new["blockers"], new["planned_visual_count"])
        equivalence["ready"].append({"essay": str(essay_path), "legacy": old, "new": new, "equal": same})
        if not same:
            blockers.append(_blk("ready-not-equivalent", "READY visual outcome would change", [essay_path, new_side]))
    if essays:
        source = essay_mod.check_source([Path(e["essay"]) for e in essays])
        equivalence["ready_source"] = {"unchanged": True, "needs_source_count": source["needs_source_count"],
                                       "note": "essay sources are never modified by migration"}
    return equivalence, blockers, dependencies


# ======================================================================= user scope


def _plan_user(home: Path, legacy_user: Path, new_user: Path, env) -> Plan:
    plan = Plan("user", {"home": str(home), "legacy_user_dir": str(legacy_user), "user_dir": str(new_user)},
                new_user / "migrations")
    new_user_doc = read_config_file(new_user / CONFIG_NAME)  # invalid new config: exit 2
    if legacy_user.is_symlink():
        plan.blockers.append(_blk("legacy-dir-symlink", "the legacy user directory is a symlink; migrate "
                                  "its target with --legacy-user-dir", [legacy_user]))
    elif legacy_user.is_dir():
        for name in (*GUIDES, *POLICY_FILES):
            src = legacy_user / name
            if not os.path.lexists(src):
                continue
            if src.is_symlink() or not src.is_file():
                plan.blockers.append(_blk("legacy-symlink", "legacy user file is a symlink or not a regular file; "
                                          "replace it with a file or configure its target explicitly", [src]))
                continue
            plan.add_write(new_user / name, plan.read_input(src) or b"", "copy", new_user, source=src)
        for path in sorted(legacy_user.rglob("*")):
            if path.is_file() and path.parent == legacy_user and path.name in (*GUIDES, *POLICY_FILES):
                continue
            if path.is_file() or path.is_symlink():
                plan.retained.append({"path": str(path), "reason": "unknown legacy user file left at source"})
    if new_user_doc and new_user_doc.get("guidance"):
        plan.warnings.append(_blk("user-config-guidance", "the prosevoice user config lists guidance candidates "
                                  "that are tried before the user directory guides", [new_user / CONFIG_NAME]))

    base_config = build_config(home, home, "explicit", new_user, None, None)
    targets = _rule_targets(base_config, home)
    _plan_rules(plan, [home], [home / ".pi/agent/AGENTS.md", home / ".codex/AGENTS.md",
                               home / ".config/opencode/AGENTS.md"], targets, home)

    def verify(overlay: dict):
        read = _overlay_reader(overlay)
        cfg = build_config(new_user, new_user, "explicit", new_user, None, None, None, env)

        def state_of(path: Path) -> str:
            data = read(path)
            return "absent" if data is None else text_state(data.decode("utf-8", "replace"))

        resolved = resolve_guidance(cfg, state_of=state_of)
        equivalence: dict = {"guidance": {}, "policy": {}}
        blockers = []
        for name in GUIDES:
            new_entry = next(t for t in resolved[name]["tried"] if t["level"] == "user")
            old_path = legacy_user / name
            old_data, new_data = read(old_path), read(Path(new_entry["path"]))
            old_state = file_state(old_path)
            # A guide absent from the legacy user directory has nothing to migrate.
            equal = old_data is None or (old_state == new_entry["state"] and old_data == new_data)
            equivalence["guidance"][name] = {"legacy_state": old_state, "new_state": new_entry["state"],
                                             "path": new_entry["path"], "equal": equal}
            if not equal:
                blockers.append(_blk("guidance-not-equivalent", f"user {name} differs after migration",
                                     [old_path, new_entry["path"]]))
        dictionaries, ignores = policy_mod.policy_sources(cfg)
        for label, new_path, parse in (("dictionary", dictionaries[0], policy_mod.words_from_text),
                                       ("ignore_rules", ignores[0], policy_mod.rules_from_text)):
            if read(legacy_user / new_path.name) is None:
                equivalence["policy"][label] = {"equal": True, "legacy_count": 0, "note": "no legacy file"}
                continue
            old, _ = _words(read, [legacy_user / new_path.name], parse)
            new, _ = _words(read, [new_path], parse)
            equivalence["policy"][label] = {"equal": old == new, "legacy_count": len(old), "new_count": len(new)}
            if old != new:
                blockers.append(_blk("policy-not-equivalent", f"user {label} differs after migration",
                                     [legacy_user / new_path.name, new_path]))
        return equivalence, blockers, []

    plan.verify = verify
    if not plan.blockers:
        equivalence, blockers, _ = verify(plan.overlay())
        plan.equivalence = equivalence
        plan.blockers += blockers
    return plan


# ======================================================================= manifest / apply


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _manifests(base: Path) -> list[tuple[Path, dict]]:
    out = []
    if base.is_dir():
        for path in sorted(base.glob("*/manifest.json")):
            try:
                out.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError) as error:
                raise ProsevoiceError("manifest-unreadable", f"cannot read migration manifest: {error}",
                                      [path]) from error
    return out


def _replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.prosevoice-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _run_actions(manifest_path: Path, manifest: dict, phase: str) -> None:
    mdir = manifest_path.parent
    for action in manifest["actions"]:
        if action["phase"] != phase or action["state"] == "done":
            continue
        path = Path(action["path"])
        action["state"] = "started"
        _write_json(manifest_path, manifest)  # record intent before the write
        _checkpoint("before-replace", action)
        if action["op"] == "write":
            data = (mdir / "staged" / f"{action['id']:03d}").read_bytes()
            if sha(data) != action["after"]:
                raise ProsevoiceError("manifest-corrupt", "staged bytes do not match the manifest", [mdir])
            _replace(path, data)
        else:
            path.unlink(missing_ok=True)
        _checkpoint("after-replace", action)
        action["state"] = "done"
        _write_json(manifest_path, manifest)


def _finish(plan_verify, manifest_path: Path, manifest: dict, report: dict) -> dict:
    """Run data actions, verify on disk, activate rules and complete the manifest."""
    _run_actions(manifest_path, manifest, "data")
    _checkpoint("before-verify")
    equivalence, blockers, dependencies = plan_verify({}) if plan_verify else ({}, [], [])
    report["equivalence"] = equivalence
    if blockers:
        report["operation"] = "blocked"
        report["blockers"] += blockers
        report["dependencies"] += dependencies
        manifest["verification"] = {"state": "failed", "blockers": blockers}
        _write_json(manifest_path, manifest)
        return report
    manifest["verification"] = {"state": "passed"}
    _write_json(manifest_path, manifest)
    _checkpoint("before-rules")
    _run_actions(manifest_path, manifest, "rule")
    _checkpoint("before-complete")
    manifest["state"] = "complete"
    manifest["completed"] = _now()
    _write_json(manifest_path, manifest)
    report["operation"] = "applied"
    report["actions"] = manifest["actions"]
    return report


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resume_conflicts(manifest_path: Path, manifest: dict) -> list:
    blockers = []
    destinations = {a["path"] for a in manifest["actions"]}
    for path, recorded in manifest["inputs"].items():
        if path in destinations:
            continue
        if _hash_of(Path(path)) != recorded:
            blockers.append(_blk("resume-input-changed", "a migration input changed since the unfinished apply "
                                 "began; restore it or finish manually using the manifest", [path, manifest_path],
                                 expected=recorded, actual=_hash_of(Path(path))))
    for action in manifest["actions"]:
        current = _hash_of(Path(action["path"]))
        if action["state"] == "done":
            ok = current == action["after"]
        else:
            ok = current in (action["before"], action["after"])
        if not ok:
            blockers.append(_blk("resume-conflict", "file was edited after the interrupted apply; reconcile it "
                                 "with the manifest's before/after hashes and backups", [action["path"], manifest_path],
                                 expected=action["after"] if action["state"] == "done" else
                                 [action["before"], action["after"]], actual=current))
    return blockers


def _accept_completed(manifest: dict) -> None:
    """Pending actions whose destination already equals the after state were interrupted
    between the replacement and the completion record."""
    for action in manifest["actions"]:
        if action["state"] != "done" and _hash_of(Path(action["path"])) == action["after"] \
                and action["before"] != action["after"]:
            action["state"] = "done"


# ======================================================================= entry point


def recovery_instructions(plan_roots: dict, manifest: str | None) -> list[str]:
    where = manifest or "<scope dir>/migrations/<id>/manifest.json"
    return [
        f"Roots: {', '.join(f'{k}={v}' for k, v in sorted(plan_roots.items()))}.",
        ("Legacy sources are retained unchanged and ordinary prosevoice commands ignore them; nothing needs "
         "restoring for the legacy tools to keep their data."),
        (f"An interrupted --apply resumes when rerun with the same scope; it continues from {where} and "
         "blocks on any file edited in between."),
        ("To undo a migration-written file, check that its current sha256 equals the action's 'after' hash in "
         "the manifest; if so delete it when 'before' is null, or restore backups/<id>-<name> when the action "
         "has a backup. A differing hash means the file was edited afterwards: reconcile it manually."),
        ("Removed legacy rule files and replaced AGENTS.md files are backed up under the manifest's backups/ "
         "directory; copy a backup back only after confirming the current file still equals the 'after' hash."),
        ("Removing legacy pv-prosevoice / pv-preflight skill installations is an explicit installer task, e.g. "
         "npx skills remove pv-prosevoice pv-preflight; migration never edits installer locks or symlinks."),
    ]


def migrate(scope: str = "project", *, apply: bool = False, project: str | Path | None = None,
            legacy_user_dir: str | Path | None = None, user_dir: str | Path | None = None,
            cwd: Path | None = None, env=None) -> dict:
    cwd = (cwd or Path.cwd()).resolve()
    home = Path.home().resolve()
    legacy_user = _norm(Path(legacy_user_dir).expanduser()) if legacy_user_dir else home / LEGACY_USER_DIR
    if scope == "project":
        root, _how = select_project(project, cwd)
        plan = _plan_project(root, home, legacy_user, env)
    elif scope == "user":
        new_user = _norm(Path(user_dir).expanduser()) if user_dir else user_config_dir(env)
        plan = _plan_user(home, legacy_user, new_user, env)
    else:
        raise ProsevoiceError("usage", f"unknown migration scope {scope!r}")

    report = {
        "migration_version": MIGRATION_VERSION, "scope": plan.scope, "mode": "apply" if apply else "preview",
        "operation": None, "roots": plan.roots,
        "reads": [{"path": p, "sha256": h} for p, h in sorted(plan.inputs.items())],
        "actions": plan.actions, "unchanged": plan.unchanged, "translated_config": plan.translated_config,
        "external_references": plan.external, "dependencies": plan.dependencies, "blockers": plan.blockers,
        "conflicts": [b for b in plan.blockers if "conflict" in b["code"]], "warnings": plan.warnings,
        "retained": plan.retained, "skipped": plan.skipped, "link_rewrites": plan.link_rewrites,
        "essays": plan.essays, "equivalence": plan.equivalence, "manifest": None, "backups": [],
    }
    unfinished = [(p, m) for p, m in _manifests(plan.manifest_base) if m.get("state") != "complete"]
    if len(unfinished) > 1:
        report["blockers"].append(_blk("manifest-multiple", "more than one unfinished migration manifest; "
                                       "resolve them manually", [p for p, _ in unfinished]))
        unfinished = []
        report["operation"] = "blocked"
    if unfinished:
        manifest_path, manifest = unfinished[0]
        report.update({"manifest": str(manifest_path), "actions": manifest["actions"], "resumed": True,
                       "backups": manifest.get("backups", []), "blockers": [], "conflicts": []})
        conflicts = _resume_conflicts(manifest_path, manifest)
        if conflicts:
            report["blockers"] = report["conflicts"] = conflicts
            report["operation"] = "blocked"
        elif not apply:
            report["operation"] = "would-change"
        else:
            _accept_completed(manifest)
            _write_json(manifest_path, manifest)
            _finish(plan.verify, manifest_path, manifest, report)
    elif report["operation"] == "blocked" or plan.blockers:
        report["operation"] = "blocked"
    elif not plan.actions:
        report["operation"] = "unchanged"
    elif not apply:
        report["operation"] = "would-change"
    else:
        manifest_path = _start_manifest(plan)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report.update({"manifest": str(manifest_path), "backups": manifest["backups"]})
        _checkpoint("manifest-written")
        _finish(plan.verify, manifest_path, manifest, report)
    report["recovery"] = recovery_instructions(plan.roots, report["manifest"])
    return report


def _start_manifest(plan: Plan) -> Path:
    ident = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    mdir = plan.manifest_base / ident
    scope_root = Path(plan.roots["project"] if plan.scope == "project" else plan.roots["user_dir"])
    link = _symlink_component(plan.manifest_base, scope_root)
    if link is not None:
        raise ProsevoiceError("destination-symlink", "migration directory passes through a symlink", [link])
    for check in (plan.manifest_base, mdir):
        if os.path.lexists(check) and check.is_symlink():
            raise ProsevoiceError("destination-symlink", "migration directory is a symlink", [check])
    (mdir / "staged").mkdir(parents=True)
    backups = []
    for action in plan.actions:
        if action["op"] == "write":
            (mdir / "staged" / f"{action['id']:03d}").write_bytes(plan.staged[action["id"]])
        if action["backup"]:
            (mdir / "backups").mkdir(exist_ok=True)
            target = mdir / "backups" / f"{action['id']:03d}-{Path(action['path']).name}"
            target.write_bytes(Path(action["path"]).read_bytes())
            backups.append({"action": action["id"], "path": action["path"], "backup": str(target)})
    manifest = {
        "migration_version": MIGRATION_VERSION, "id": ident, "scope": plan.scope, "roots": plan.roots,
        "state": "in-progress", "created": _now(), "inputs": plan.inputs, "actions": plan.actions,
        "backups": backups, "translated_config": plan.translated_config,
    }
    _write_json(mdir / "manifest.json", manifest)
    return mdir / "manifest.json"
