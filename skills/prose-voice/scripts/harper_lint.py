# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tool-backed spelling and grammar pass for prose-voice, via Harper (`harper-cli`).

Runs `harper-cli lint` over one or more documents and prints a normalized, classified finding
list for the copy-editor and the gate reports. The script never edits a document: it marks
auto-fix *candidates*; the caller decides whether a candidate falls inside its write authority.

Harper is optional. When `harper-cli` is not on PATH the script prints a `skipped` result and
exits 4; the gate degrades to the LLM copy-edit alone.

Word lists and suppressed rules are project-owned, resolved like VOICE.md but UNIONED across
every location that has one (a word accepted at the git root is still accepted in a subfolder):

    <document dir>/harper-dictionary.txt   <git root>/harper-dictionary.txt   ~/.config/prose-voice/harper-dictionary.txt
    <document dir>/harper-ignore.txt       <git root>/harper-ignore.txt       ~/.config/prose-voice/harper-ignore.txt

Both files: one entry per line; blank lines and `#` comments ignored; a trailing `# reason` after
an ignore-rule name is allowed. Rule names come from `harper-cli config`.

Processing:
  * Overlapping lints are kept (`-o`) and collapsed to one finding per span. The finding with the
    lowest Harper `priority` (most specific rule) wins; the other rules on that span are listed in
    `also`. Example: `alot` -> OpenCompounds "a lot" (priority 31) beats SpellCheck "allot" (63).
  * Each finding gets a bucket:
      error     grammar, agreement, typo, repetition, punctuation, boundary errors
      spelling  SpellCheck hit on a lowercase token
      name      SpellCheck hit on a capitalized token -> propose a dictionary entry, never "fix"
      advisory  style / readability / word-choice rules -> surface, never auto-fix
  * `fixable` is true only when: bucket is error or spelling, there is exactly one suggestion and
    it is a plain replacement, and the document text at the span equals Harper's `matched_text`
    (the offset guard). Single-suggestion is not proof of intent; the caller still applies the
    authorship / region / preserve bounds.

Usage:
    harper_lint.py <doc>... [--dialect us|uk|au|ca|in] [--json]

Exit codes: 0 ran (see `counts`; findings do not change the exit code), 2 error,
4 harper-cli not found (skipped).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DICT_NAME = "harper-dictionary.txt"
IGNORE_NAME = "harper-ignore.txt"
CONFIG_DIR = Path.home() / ".config" / "prose-voice"

ADVISORY_KINDS = {
    "Style", "Readability", "Enhancement", "WordChoice", "Redundancy", "Regionalism", "Formatting",
}
ADVISORY_RULES = {"LongSentences"}
REPLACE_RE = re.compile(r'^Replace with: [“"](.*)[”"]$', re.S)


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def candidate_dirs(docs: list[Path]) -> list[Path]:
    seen: list[Path] = []
    for doc in docs:
        for d in (doc.parent, git_root(doc.parent), CONFIG_DIR):
            if d is not None and d.resolve() not in seen:
                seen.append(d.resolve())
    return seen


def read_entries(path: Path) -> list[str]:
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if line:
            entries.append(line)
    return entries


def collect(dirs: list[Path], name: str) -> tuple[list[str], list[str]]:
    values: set[str] = set()
    sources: list[str] = []
    for d in dirs:
        f = d / name
        if f.is_file():
            values.update(read_entries(f))
            sources.append(str(f))
    return sorted(values), sources


def bucket_for(lint: dict) -> str:
    kind, rule, text = lint.get("kind", ""), lint.get("rule", ""), lint.get("matched_text", "")
    if kind in ADVISORY_KINDS or rule in ADVISORY_RULES:
        return "advisory"
    if kind == "Spelling":
        return "name" if text[:1].isupper() else "spelling"
    return "error"


def normalize(lints: list[dict], text: str) -> list[dict]:
    by_span: dict[tuple[int, int], list[dict]] = {}
    for lint in lints:
        span = lint.get("span", {})
        by_span.setdefault((span.get("char_start", -1), span.get("char_end", -1)), []).append(lint)

    findings = []
    for (start, end), group in sorted(by_span.items()):
        group.sort(key=lambda lint: (lint.get("priority", 255), lint.get("rule", "")))
        top = group[0]
        suggestions = top.get("suggestions", [])
        bucket = bucket_for(top)
        replacement = None
        if len(suggestions) == 1:
            m = REPLACE_RE.match(suggestions[0])
            replacement = m.group(1) if m else None
        guard = 0 <= start < end <= len(text) and text[start:end] == top.get("matched_text")
        findings.append({
            "line": top.get("line"),
            "column": top.get("column"),
            "char_start": start,
            "char_end": end,
            "rule": top.get("rule"),
            "kind": top.get("kind"),
            "bucket": bucket,
            "message": top.get("message"),
            "matched_text": top.get("matched_text"),
            "suggestions": suggestions,
            "replacement": replacement,
            "fixable": bucket in ("error", "spelling") and replacement is not None and guard,
            "offset_guard": guard,
            "also": [other.get("rule") for other in group[1:]],
        })
    return findings


def harper_version(exe: str) -> str:
    out = subprocess.run([exe, "--version"], capture_output=True, text=True)
    return out.stdout.strip()


def lint_file(exe: str, doc: Path, dialect: str, dict_path: str, ignore: list[str]) -> list[dict]:
    cmd = [exe, "lint", "--format", "json", "--keep-overlapping-lints",
           "--dialect", dialect, "--user-dict-path", dict_path]
    if ignore:
        cmd += ["--ignore", ",".join(ignore)]
    cmd.append(str(doc))
    # Non-zero exit with JSON on stdout is a normal "lints found" result; only unparseable
    # output is an error.
    out = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"harper-cli produced no JSON for {doc}: {out.stderr.strip()}") from exc
    return [lint for entry in data for lint in entry.get("lints", [])]


def render_text(result: dict) -> str:
    lines = [f"{result['harper_version']} (dialect {result['dialect']})"]
    for f in result["files"]:
        lines.append(f"{f['file']}: {len(f['findings'])} finding(s)")
        for x in f["findings"]:
            fix = f" -> {x['replacement']}" if x["replacement"] is not None else ""
            mark = " [fixable]" if x["fixable"] else ""
            lines.append(
                f"  {x['line']}:{x['column']} {x['bucket']:<8} {x['rule']}: "
                f"{x['matched_text']!r}{fix}{mark} — {x['message']}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Tool-backed spelling and grammar pass via harper-cli.")
    ap.add_argument("docs", nargs="+", type=Path, help="document paths (.md, .txt, .eml, ...)")
    ap.add_argument("--dialect", default="us", help="Harper dialect (default: us)")
    ap.add_argument("--json", action="store_true", help="emit JSON (default: compact text)")
    args = ap.parse_args()

    exe = shutil.which("harper-cli")
    if exe is None:
        skipped = {"status": "skipped", "reason": "harper-cli not found (brew install harper)"}
        print(json.dumps(skipped) if args.json else f"skipped: {skipped['reason']}")
        return 4

    docs = [d.resolve() for d in args.docs]
    for d in docs:
        if not d.is_file():
            print(f"error: not a file: {d}", file=sys.stderr)
            return 2

    dirs = candidate_dirs(docs)
    words, dict_sources = collect(dirs, DICT_NAME)
    ignore, ignore_sources = collect(dirs, IGNORE_NAME)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write("\n".join(words) + ("\n" if words else ""))
        dict_path = tf.name

    try:
        files = []
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            lints = lint_file(exe, doc, args.dialect, dict_path, ignore)
            files.append({"file": str(doc), "findings": normalize(lints, text)})
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        Path(dict_path).unlink(missing_ok=True)

    counts: dict[str, int] = {"error": 0, "spelling": 0, "name": 0, "advisory": 0, "fixable": 0}
    for f in files:
        for x in f["findings"]:
            counts[x["bucket"]] += 1
            counts["fixable"] += int(x["fixable"])

    result = {
        "status": "ran",
        "harper_version": harper_version(exe),
        "dialect": args.dialect,
        "dictionary_sources": dict_sources,
        "ignore_sources": ignore_sources,
        "ignore_rules": ignore,
        "counts": counts,
        "files": files,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
