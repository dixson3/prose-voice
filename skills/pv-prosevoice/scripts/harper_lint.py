# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Report Harper findings for Markdown; never edit essays.

A fixable finding is only a candidate. The caller must still enforce body-region,
VOICE and authorship constraints. Policy is merged independently per document.
Exit codes: 0 ran, 2 error, 4 Harper unavailable.
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

from build_user_dict import POLICY, build, merge_rules, policy_sources, project_root

ADVISORY_KINDS = {
    "Style", "Readability", "Enhancement", "WordChoice", "Redundancy", "Regionalism", "Formatting",
}
ADVISORY_RULES = {"DisjointPrefixes", "LongSentences"}
REPLACE_RE = re.compile(r'^Replace with: (?:“([^\r\n“”]*)”|"([^\r\n"]*)")$')


def bucket_for(lint: dict) -> str:
    if lint["kind"] in ADVISORY_KINDS or lint["rule"] in ADVISORY_RULES:
        return "advisory"
    if lint["kind"] == "Spelling":
        return "name" if lint["matched_text"][:1].isupper() else "spelling"
    return "error"


def normalize(lints: list[dict], text: str, words=()) -> list[dict]:
    """Choose the lowest-priority rule for each identical character span."""
    accepted = set(words)
    by_span: dict[tuple[int, int], list[dict]] = {}
    for lint in lints:
        span = lint["span"]
        by_span.setdefault((span["char_start"], span["char_end"]), []).append(lint)
    findings = []
    for (start, end), group in sorted(by_span.items()):
        group = sorted(group, key=lambda lint: (lint["priority"], lint["rule"]))
        top = group[0]
        suggestions = top["suggestions"]
        bucket = bucket_for(top)
        match = REPLACE_RE.fullmatch(suggestions[0]) if len(suggestions) == 1 else None
        replacement = next((s for s in match.groups() if s is not None), None) if match else None
        guard = 0 <= start < end <= len(text) and text[start:end] == top["matched_text"]
        findings.append({
            "line": top["line"], "column": top["column"],
            "char_start": start, "char_end": end, "rule": top["rule"],
            "kind": top["kind"], "bucket": bucket, "message": top["message"],
            "matched_text": top["matched_text"], "suggestions": suggestions,
            "replacement": replacement,
            "fixable": (top["kind"] == "Spelling" and bucket == "spelling"
                        and replacement is not None and guard and top["matched_text"] not in accepted),
            "offset_guard": guard, "also": [other["rule"] for other in group[1:]],
        })
    return findings


def validate_lints(data: object) -> list[dict]:
    """Reject error objects and malformed successful responses, including partial ones."""
    if not isinstance(data, list) or not data:
        raise RuntimeError("harper-cli JSON must be a nonempty list of file entries")
    lints = []
    for entry in data:
        if not isinstance(entry, dict) or "error" in entry or not isinstance(entry.get("lints"), list):
            raise RuntimeError("harper-cli JSON file entry must contain a lints list")
        for lint in entry["lints"]:
            if not isinstance(lint, dict):
                raise RuntimeError("harper-cli JSON lint must be an object")  # noqa: TRY004 — CLI protocol error
            valid = all(isinstance(lint.get(key), str)
                        for key in ("kind", "rule", "matched_text", "message"))
            valid = valid and all(type(lint.get(key)) is int and lint[key] >= 0
                                  for key in ("line", "column", "priority"))
            suggestions = lint.get("suggestions")
            valid = valid and isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions)
            span = lint.get("span")
            valid = valid and isinstance(span, dict) and all(
                type(span.get(key)) is int and span[key] >= 0 for key in ("char_start", "char_end"))
            if not valid or not isinstance(span, dict) or span["char_end"] < span["char_start"]:
                raise RuntimeError("harper-cli JSON lint has invalid fields")
            lints.append(lint)
    return lints


def harper_version(exe: str) -> str:
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"harper-cli version failed: {out.stderr.strip()}")
    return out.stdout.strip()


def lint_file(exe: str, doc: Path, dialect: str, dict_path: str, ignore: list[str]) -> list[dict]:
    cmd = [exe, "lint", "--format", "json", "--keep-overlapping-lints",
           "--dialect", dialect, "--user-dict-path", dict_path]
    if ignore:
        cmd += ["--ignore", ",".join(ignore)]
    cmd.append(str(doc))
    # Harper can exit nonzero when it finds lints; require a valid report regardless.
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"cannot run harper-cli for {doc}: {exc}") from exc
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"harper-cli produced no valid JSON for {doc}: {out.stderr.strip()}") from exc
    return validate_lints(data)


def render_text(result: dict) -> str:
    lines = [f"{result['harper_version']} (dialect {result['dialect']})"]
    for entry in result["files"]:
        lines.append(f"{entry['file']}: {len(entry['findings'])} finding(s)")
        for finding in entry["findings"]:
            mark = " [fix candidate]" if finding["fixable"] else ""
            lines.append(f"  {finding['line']}:{finding['column']} {finding['bucket']} "
                         f"{finding['rule']}: {finding['matched_text']!r}{mark} — {finding['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", nargs="+", type=Path, help="Markdown (.md) documents")
    parser.add_argument("--dialect", default="us", choices=("us", "uk", "au", "ca", "in"))
    parser.add_argument("--user-dict", type=Path, action="append", default=[])
    parser.add_argument("--user-ignore", type=Path, action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        docs = [doc.expanduser().resolve() for doc in args.docs]
        for doc in docs:
            if doc.suffix.lower() != ".md" or not doc.is_file():
                raise RuntimeError(f"not a Markdown (.md) file: {doc}")
        exe = shutil.which("harper-cli")
        if exe is None:
            skipped = {"status": "skipped", "reason": "harper-cli not found"}
            print(json.dumps(skipped) if args.json else f"skipped: {skipped['reason']}")
            return 4
        version = harper_version(exe)
        files = []
        for doc in docs:
            dictionaries, ignores = policy_sources(
                project_root(doc.parent), [p.expanduser() for p in args.user_dict],
                [p.expanduser() for p in args.user_ignore])
            sidecar = doc.parent / ".harper-words"
            words = build(POLICY / "dictionary.txt", sidecar, dictionaries)
            rules = merge_rules(POLICY / "ignore-rules.txt", ignores)
            text = doc.read_text(encoding="utf-8")
            with tempfile.TemporaryDirectory(prefix="pv-harper-") as temporary:
                dictionary = Path(temporary) / "dictionary.txt"
                dictionary.write_text("\n".join(words) + "\n", encoding="utf-8")
                lints = lint_file(exe, doc, args.dialect, str(dictionary), rules)
            files.append({
                "file": str(doc), "findings": normalize(lints, text, words),
                "dictionary_sources": [str(p) for p in [POLICY / "dictionary.txt", *dictionaries, sidecar]
                                       if p.is_file()],
                "ignore_sources": [str(p) for p in [POLICY / "ignore-rules.txt", *ignores] if p.is_file()],
                "ignore_rules": rules,
            })
    except (RuntimeError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    counts = dict.fromkeys(("error", "spelling", "name", "advisory", "fixable"), 0)
    for entry in files:
        for finding in entry["findings"]:
            counts[finding["bucket"]] += 1
            counts["fixable"] += int(finding["fixable"])
    result = {"status": "ran", "harper_version": version, "dialect": args.dialect,
              "counts": counts, "files": files}
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
