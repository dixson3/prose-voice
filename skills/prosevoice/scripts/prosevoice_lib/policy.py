"""Harper policy merging and the read-only Harper lint wrapper.

Ported without behavioral change from the former ``build_user_dict.py`` and
``harper_lint.py`` helpers; the legacy private path resolver is replaced by the shared
configuration layer.

Policy is an additive union of bundled (``harper/`` in this skill), user (the prosevoice
user directory), project (``<project>/.prosevoice/``), essay-local ``.harper-words`` and
explicit repeatable paths. Config precedence never removes a layer. Dictionary entries
are case-sensitive, one per line, ignoring blank and full-line ``#`` comments; ignore
rules also accept trailing ``#`` comments. Missing optional files are tolerated; present
but unreadable files are errors. Inputs are never modified.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import resource
from .config import Config, config_for_essay
from .errors import ProsevoiceError

DICTIONARY = "dictionary.txt"
IGNORE_RULES = "ignore-rules.txt"
LOCAL_WORDS = ".harper-words"
DIALECTS = ("us", "uk", "au", "ca", "in")


def bundled_policy() -> tuple[Path, Path]:
    return resource("harper", DICTIONARY), resource("harper", IGNORE_RULES)


def words_from_text(text: str) -> list[str]:
    """Case-sensitive word entries, ignoring blank and full-line comments."""
    return [line for raw in text.splitlines() if (line := raw.strip()) and not line.startswith("#")]


def rules_from_text(text: str) -> list[str]:
    """Rule names, including lines with trailing comments."""
    return [line for raw in text.splitlines() if (line := raw.split("#", 1)[0].strip())]


def read_words(path: Path) -> list[str]:
    return words_from_text(path.read_text(encoding="utf-8"))


def read_rules(path: Path) -> list[str]:
    return rules_from_text(path.read_text(encoding="utf-8"))


def build(global_path: Path, sidecar_path: Path | None, extra_paths=()) -> list[str]:
    words = set(read_words(global_path))
    for path in (*extra_paths, sidecar_path):
        if path is not None and path.exists():
            words.update(read_words(path))
    return sorted(words, key=lambda word: (word.casefold(), word))
def merge_rules(bundled: Path, extra_paths=()) -> list[str]:
    rules = set(read_rules(bundled))
    for path in extra_paths:
        if path.exists():
            rules.update(read_rules(path))
    return sorted(rules)
def policy_sources(config: Config, user_dicts=(), user_ignores=()) -> tuple[list[Path], list[Path]]:
    """Additive dictionary and ignore inputs after the bundled layer, lowest scope first."""
    dictionaries = [config.user_dir / DICTIONARY, config.project_dir / DICTIONARY, *user_dicts]
    ignores = [config.user_dir / IGNORE_RULES, config.project_dir / IGNORE_RULES, *user_ignores]
    return dictionaries, ignores


def essay_policy(config: Config, essay: Path | None, *, sidecar: Path | None = None,
                 user_dicts=(), user_ignores=(), bundled_dictionary: Path | None = None,
                 bundled_ignore: Path | None = None) -> dict:
    """Merged words, rules and the files that supplied them for one essay."""
    if bundled_dictionary is None:
        bundled_dictionary = resource("harper", DICTIONARY)
    if bundled_ignore is None:
        bundled_ignore = resource("harper", IGNORE_RULES)
    if sidecar is None and essay is not None:
        sidecar = essay.parent / LOCAL_WORDS
    dictionaries, ignores = policy_sources(config, user_dicts, user_ignores)
    words = build(bundled_dictionary, sidecar, dictionaries)
    rules = merge_rules(bundled_ignore, ignores)
    dictionary_sources = [bundled_dictionary, *dictionaries, *([sidecar] if sidecar else [])]
    return {
        "words": words,
        "rules": rules,
        "sources": {
            "dictionary": [str(p) for p in dictionary_sources if p.is_file()],
            "ignore_rules": [str(p) for p in [bundled_ignore, *ignores] if p.is_file()],
        },
    }


def write_dictionary(words: list[str], out: Path | None) -> Path:
    content = "\n".join(words) + ("\n" if words else "")
    if out is not None:
        out.write_text(content, encoding="utf-8")
        return out
    with tempfile.NamedTemporaryFile(mode="w", suffix=".harper-dict.txt", delete=False,
                                     encoding="utf-8") as output:
        output.write(content)
        return Path(output.name)


# ======================================================================= lint

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
def lint_documents(config: Config, docs: list[Path], *, dialect: str = "us",
                   user_dicts=(), user_ignores=()) -> dict:
    """Lint each document with its own merged policy; never edit documents.

    Returns ``{"status": "skipped", ...}`` when harper-cli is unavailable. Raises
    ``ProsevoiceError`` for non-Markdown inputs, tool failures or malformed output.
    """
    resolved = []
    for doc in docs:
        doc = doc.expanduser()
        doc = (doc if doc.is_absolute() else config.cwd / doc).resolve()
        if doc.suffix.lower() != ".md" or not doc.is_file():
            raise ProsevoiceError("not-markdown", f"not a Markdown (.md) file: {doc}", paths=[doc])
        resolved.append(doc)
    exe = shutil.which("harper-cli")
    if exe is None:
        return {"status": "skipped", "reason": "harper-cli not found"}
    try:
        version = harper_version(exe)
        files = []
        for doc in resolved:
            policy = essay_policy(config_for_essay(config, doc), doc,
                                  user_dicts=user_dicts, user_ignores=user_ignores)
            words, rules = policy["words"], policy["rules"]
            text = doc.read_text(encoding="utf-8")
            with tempfile.TemporaryDirectory(prefix="prosevoice-harper-") as temporary:
                dictionary = Path(temporary) / "dictionary.txt"
                dictionary.write_text("\n".join(words) + "\n", encoding="utf-8")
                lints = lint_file(exe, doc, dialect, str(dictionary), rules)
            files.append({
                "file": str(doc), "findings": normalize(lints, text, words),
                "dictionary_sources": policy["sources"]["dictionary"],
                "ignore_sources": policy["sources"]["ignore_rules"],
                "ignore_rules": rules,
            })
    except RuntimeError as error:
        raise ProsevoiceError("harper-failed", str(error)) from error
    counts = dict.fromkeys(("error", "spelling", "name", "advisory", "fixable"), 0)
    for entry in files:
        for finding in entry["findings"]:
            counts[finding["bucket"]] += 1
            counts["fixable"] += int(finding["fixable"])
    return {"status": "ran", "harper_version": version, "dialect": dialect,
            "counts": counts, "files": files}
