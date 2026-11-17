"""prosevoice command line: one JSON envelope per command.

Every command prints a single JSON object::

    {"schema_version": 1, "command": ..., "status": "ok"|"blocked"|"error",
     "data": {...}, "diagnostics": [{"code", "message", "paths"}]}

Exit status: 0 success, 1 evaluated blockers, 2 invalid invocation/configuration or
operational failure. ``--help`` stays conventional argparse text.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from pathlib import Path

from . import __version__, essay, migration, policy, resource_mode, rules, skill_root
from .config import (
    ARTIFACT_KINDS,
    GUIDES,
    REQUIRED_GUIDES,
    artifact_paths,
    config_for_essay,
    init,
    load_config,
    prepare_artifacts,
    resolve_guidance,
)
from .errors import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_OK,
    ProsevoiceError,
    UsageError,
    diagnostic,
)

ENVELOPE_VERSION = 1
COMMANDS = ("version", "config", "init", "check", "resolve", "artifacts", "rule", "policy",
            "lint", "extract", "premise", "ready", "migrate")


class _Parser(argparse.ArgumentParser):
    """argparse that raises instead of printing usage text and exiting."""

    def error(self, message: str):  # type: ignore[override]
        raise UsageError(message)


class Result:
    def __init__(self, data: dict | None = None, status: str = "ok", diagnostics: list | None = None):
        self.data = data or {}
        self.status = status
        self.diagnostics = diagnostics or []


def envelope(command: str | None, status: str, data: dict, diagnostics: list) -> dict:
    return {
        "schema_version": ENVELOPE_VERSION,
        "command": command,
        "status": status,
        "data": data,
        "diagnostics": [d.to_json() for d in diagnostics],
    }


# --------------------------------------------------------------------------- commands


def cmd_version(args) -> Result:
    return Result({
        "version": __version__,
        "python": platform.python_version(),
        "resource_mode": resource_mode(),
        "skill_root": str(skill_root()),
    })


def cmd_config(args) -> Result:
    config = load_config(args.project, args.set)
    return Result(config.report())


def cmd_init(args) -> Result:
    data = init(args.scope, project=args.project, overrides=args.set, illustrations=args.illustrations)
    return Result(data)


def cmd_resolve(args) -> Result:
    config = load_config(args.project, args.set)
    guides = resolve_guidance(config)
    missing = [name for name in REQUIRED_GUIDES if guides[name]["resolved"] is None]
    diagnostics = [
        diagnostic("guide-unresolved",
                   f"{name} is required but no candidate is usable (absent, empty or unfilled); "
                   "run `prosevoice init` and fill it in, or configure guidance paths",
                   [t["path"] for t in guides[name]["tried"]])
        for name in missing
    ]
    return Result({"project": str(config.project_root), "guidance": guides},
                  "blocked" if missing else "ok", diagnostics)


def cmd_artifacts(args) -> Result:
    essay = Path(args.essay).expanduser()
    config = config_for_essay(load_config(args.project, args.set), essay)
    if args.apply:
        prepared = prepare_artifacts(config, essay)
        paths, ignore_written = prepared["paths"], prepared["ignore_written"]
    else:
        paths, ignore_written = artifact_paths(config, essay), False
    selected = {args.kind: paths[args.kind]} if args.kind else paths
    return Result({
        "essay": str((essay if essay.is_absolute() else config.cwd / essay).resolve()),
        "project": str(config.project_root),
        "project_selection": config.project_selection,
        "location": config.artifacts_location,
        "applied": bool(args.apply),
        "ignore_updated": ignore_written,
        "paths": {kind: str(path) for kind, path in selected.items()},
    })


def _essay_paths(config, values: list[str]) -> list[Path]:
    """Resolve explicit essay paths against the invocation directory, preserving order."""
    out = []
    for value in values:
        path = Path(value).expanduser()
        path = (path if path.is_absolute() else config.cwd / path).resolve()
        if not path.is_file():
            raise ProsevoiceError("essay-missing", f"essay not found: {value}", paths=[path])
        out.append(path)
    return out


def _cwd_path(config, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else config.cwd / path


def cmd_check(args) -> Result:
    config = load_config(args.project, args.set)
    report = rules.check(config)
    diagnostics = [diagnostic("setup-action", action) for action in report["actions"]]
    return Result(report, "ok" if report["ready"] else "blocked", diagnostics)


def cmd_rule(args) -> Result:
    config = load_config(args.project, args.set)
    report = rules.rule(config, apply=args.apply, remove=args.remove)
    diagnostics = [diagnostic("managed-block-malformed", t.get("detail", "malformed managed block"), [t["path"]])
                   for t in report["targets"] if t["state"] == "malformed"]
    if not report["installation_found"]:
        diagnostics.append(diagnostic("installation-missing",
                                      f"{rules.SKILL} not found in any project or global skill dir"))
    return Result(report, "blocked" if report["blocked"] else "ok", diagnostics)


def _policy_inputs(config, args) -> dict:
    return {
        "user_dicts": [_cwd_path(config, p) for p in args.user_dict],
        "user_ignores": [_cwd_path(config, p) for p in args.user_ignore],
    }


def cmd_policy(args) -> Result:
    config = load_config(args.project, args.set)
    essay_path = _essay_paths(config, [args.essay])[0] if args.essay else None
    try:
        merged = policy.essay_policy(
            config_for_essay(config, essay_path) if essay_path else config, essay_path, sidecar=_cwd_path(config, args.sidecar),
            bundled_dictionary=_cwd_path(config, args.bundled_dictionary),
            bundled_ignore=_cwd_path(config, args.bundled_ignore), **_policy_inputs(config, args))
        out = policy.write_dictionary(merged["words"], _cwd_path(config, args.out))
    except UnicodeError as error:
        raise ProsevoiceError("policy-unreadable", str(error)) from error
    return Result({
        "essay": str(essay_path) if essay_path else None,
        "dictionary": str(out),
        "dictionary_is_temporary": args.out is None,
        "word_count": len(merged["words"]),
        "ignore_rules": ",".join(merged["rules"]),
        "ignore_rule_list": merged["rules"],
        "sources": merged["sources"],
    })


def cmd_lint(args) -> Result:
    config = load_config(args.project, args.set)
    docs = [Path(d) for d in args.docs]
    report = policy.lint_documents(config, docs, dialect=args.dialect, **_policy_inputs(config, args))
    if report["status"] == "skipped":
        return Result(report, "ok", [diagnostic(
            "harper-unavailable", "grammar-check skipped (harper-cli not found — brew install harper)")])
    return Result(report)


def cmd_extract(args) -> Result:
    config = load_config(args.project, args.set)
    source = _essay_paths(config, [args.essay])[0]
    snippets = essay.extract(source)
    out_md = _cwd_path(config, args.out_md)
    if out_md is None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".prose.md", delete=False, encoding="utf-8") as fd:
            out_md = Path(fd.name)
    out_md.write_text("\n".join(s.text for s in snippets) + ("\n" if snippets else ""), encoding="utf-8")
    mapping = {
        # orig_path echoes the essay argument as given, as the former extract helper did.
        str(idx + 1): {"orig_path": str(Path(args.essay)), "orig_line": s.orig_line,
                       "orig_col_offset": s.orig_col_offset, "region": s.region, "coarse": s.coarse}
        for idx, s in enumerate(snippets)
    }
    return Result({"essay": str(source), "temp_md": str(out_md), "temp_is_temporary": args.out_md is None,
                   "count": len(snippets), "map": mapping})


def cmd_premise(args) -> Result:
    config = load_config(args.project, args.set)
    parts = [{"path": str(p), **essay.fingerprint(p)} for p in _essay_paths(config, args.essays)]
    return Result({"parts": parts})


def cmd_ready(args) -> Result:
    config = load_config(args.project, args.set)
    report = essay.check_ready(config, _essay_paths(config, args.essays))
    diagnostics = []
    for path, value in report["image"].items():
        diagnostics += [diagnostic("visual-unresolved", blocker, [path]) for blocker in value["blockers"]]
    diagnostics += [diagnostic("needs-source", f"{loc['file']}:{loc['line']}: {loc['text']}", [loc["file"]])
                    for loc in report["source"]["locations"]]
    return Result(report, "ok" if report["ready"] else "blocked", diagnostics)


def cmd_migrate(args) -> Result:
    if args.set:
        raise ProsevoiceError("usage", "migrate compares persisted configuration; --set is not accepted")
    if args.scope == "project" and args.user_dir:
        raise ProsevoiceError("usage", "--user-dir applies only to --scope user")
    if args.scope == "user" and args.project:
        raise ProsevoiceError("usage", "--project applies only to --scope project")
    report = migration.migrate(args.scope, apply=args.apply, project=args.project,
                               legacy_user_dir=args.legacy_user_dir, user_dir=args.user_dir)
    diagnostics = [diagnostic(b["code"], b["message"], b["paths"]) for b in report["blockers"]]
    diagnostics += [diagnostic(w["code"], w["message"], w["paths"]) for w in report["warnings"]]
    return Result(report, "blocked" if report["operation"] == "blocked" else "ok", diagnostics)


HANDLERS = {
    "migrate": cmd_migrate,
    "version": cmd_version,
    "config": cmd_config,
    "init": cmd_init,
    "check": cmd_check,
    "resolve": cmd_resolve,
    "artifacts": cmd_artifacts,
    "rule": cmd_rule,
    "policy": cmd_policy,
    "lint": cmd_lint,
    "extract": cmd_extract,
    "premise": cmd_premise,
    "ready": cmd_ready,
}


# --------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    common = _Parser(add_help=False)
    common.add_argument("--project", metavar="PATH",
                        help="project root (default: nearest Git root of cwd, else cwd)")
    common.add_argument("--set", action="append", default=[], metavar="KEY=JSON",
                        help="override a setting for this invocation, e.g. "
                             "--set 'guidance.VOICE.md=[\"docs/voice.md\"]' or "
                             "--set 'artifacts.location=\"adjacent\"' (repeatable)")
    parser = _Parser(prog="prosevoice", description="prosevoice support commands (JSON output)")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.add_parser("version", parents=[common], help="package version and resource location")
    sub.add_parser("config", parents=[common], help="effective configuration with provenance")
    p = sub.add_parser("init", parents=[common],
                       help="seed missing config and blank guides; never overwrites")
    p.add_argument("--scope", choices=("project", "user"), default="project")
    p.add_argument("--illustrations", action="store_true", help="also seed optional ILLUSTRATIONS.md")
    sub.add_parser("resolve", parents=[common], help="resolve VOICE/AUDIENCE/ILLUSTRATIONS guidance")
    p = sub.add_parser("artifacts", parents=[common], help="intermediate artifact paths for one essay")
    p.add_argument("essay", help="essay Markdown path")
    p.add_argument("--kind", choices=ARTIFACT_KINDS, help="report one artifact kind only")
    p.add_argument("--apply", action="store_true",
                   help="create the artifact directory and, in cache mode, the cache ignore rule")
    sub.add_parser("check", parents=[common],
                   help="dependencies, guidance resolution and companion-rule state (never writes)")
    p = sub.add_parser("rule", parents=[common],
                       help="preview (default) or apply the PROSEVOICE-PROTOCOL.md companion rule")
    p.add_argument("--apply", action="store_true", help="write the planned rule changes")
    p.add_argument("--remove", action="store_true", help="remove the rule instead of installing it")
    policy_args = _Parser(add_help=False)
    policy_args.add_argument("--user-dict", action="append", default=[], metavar="PATH",
                             help="additional dictionary file (repeatable)")
    policy_args.add_argument("--user-ignore", action="append", default=[], metavar="PATH",
                             help="additional ignore-rules file (repeatable)")
    p = sub.add_parser("policy", parents=[common, policy_args],
                       help="merge Harper dictionary and ignore policy for one essay")
    p.add_argument("essay", nargs="?", help="essay whose directory supplies .harper-words")
    p.add_argument("--sidecar", metavar="PATH", help="essay-local words file (default <essay-dir>/.harper-words)")
    p.add_argument("--bundled-dictionary", metavar="PATH", help="replace the bundled dictionary input")
    p.add_argument("--bundled-ignore", metavar="PATH", help="replace the bundled ignore-rules input")
    p.add_argument("--out", metavar="PATH", help="merged dictionary output (default: temp file; caller removes)")
    p = sub.add_parser("lint", parents=[common, policy_args],
                       help="read-only Harper pass with per-essay merged policy")
    p.add_argument("docs", nargs="+", help="Markdown (.md) documents, in order")
    p.add_argument("--dialect", default="us", choices=policy.DIALECTS)
    p = sub.add_parser("extract", parents=[common],
                       help="extract Harper-skipped reader-facing prose with a back-map")
    p.add_argument("essay", help="essay Markdown path")
    p.add_argument("--out-md", metavar="PATH", help="snippet output path (default: temp file; caller removes)")
    p = sub.add_parser("premise", parents=[common], help="16-character premise fingerprint per part")
    p.add_argument("essays", nargs="+", help="essay part paths, in reading order")
    p = sub.add_parser("ready", parents=[common], help="READY source and active-anchor visual checks")
    p.add_argument("essays", nargs="+", help="essay part paths, in reading order")
    p = sub.add_parser("migrate", parents=[common],
                       help="preview (default) or apply migration of legacy prose-voice data and rules")
    p.add_argument("--scope", choices=("project", "user"), default="project")
    p.add_argument("--apply", action="store_true", help="write the planned migration")
    p.add_argument("--legacy-user-dir", metavar="PATH", help="legacy user directory (default ~/.prose-voice)")
    p.add_argument("--user-dir", metavar="PATH",
                   help="--scope user only: destination user directory (default the prosevoice user dir)")
    return parser


def _guess_command(argv: list[str]) -> str | None:
    for token in argv:
        if token in COMMANDS:
            return token
    return None


def run(argv: list[str]) -> tuple[dict, int]:
    command = _guess_command(argv)
    try:
        args = build_parser().parse_args(argv)
        command = args.command
        if command is None:
            raise UsageError(f"a command is required: {', '.join(COMMANDS)}")
        result = HANDLERS[command](args)
    except ProsevoiceError as error:
        return envelope(command, "error", {}, [error.to_diagnostic()]), EXIT_ERROR
    except OSError as error:
        diag = diagnostic("os-error", str(error), [p for p in (error.filename, error.filename2) if p])
        return envelope(command, "error", {}, [diag]), EXIT_ERROR
    code = {"ok": EXIT_OK, "blocked": EXIT_BLOCKED}.get(result.status, EXIT_ERROR)
    return envelope(command, result.status, result.data, result.diagnostics), code


def main(argv: list[str] | None = None) -> int:
    payload, code = run(list(sys.argv[1:] if argv is None else argv))
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


__all__ = ["GUIDES", "build_parser", "main", "run"]

if __name__ == "__main__":
    sys.exit(main())
