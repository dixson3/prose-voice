# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Merge bundled, user, project and essay-local Harper policy without modifying inputs.

Default user files: ~/.pv/dictionary.txt and ~/.pv/ignore-rules.txt.
Project files: <git-root>/.pv/dictionary.txt and .pv/ignore-rules.txt, discovered
from --cwd (default current directory). Missing optional files are tolerated.
Additional user files can be supplied with repeatable --user-dict / --user-ignore.

Dictionary entries are case-sensitive, one per line, with blank and full-line #
comments ignored. Ignore rules also accept trailing # comments. All inputs are
additive unions: project files do not remove user words or re-enable suppressed rules.

Usage:
  build_user_dict.py --cwd <essay-dir> --sidecar <essay-dir>/.harper-words --json

By default prints the merged dictionary path (legacy interface). --json prints
{dictionary, ignore_rules, sources}; ignore_rules is ready for Harper's --ignore.
--global overrides the bundled dictionary; --ignore overrides bundled ignore rules.
--out chooses the dictionary output; otherwise the caller must clean up the temp file.
Exit 2 on unreadable present files or missing required bundled inputs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

POLICY = Path(__file__).resolve().parent.parent / "harper"


def read_words(path: Path) -> list[str]:
    """Read case-sensitive word entries, ignoring blank and full-line comments."""
    return [line for raw in path.read_text(encoding="utf-8").splitlines()
            if (line := raw.strip()) and not line.startswith("#")]


def read_rules(path: Path) -> list[str]:
    """Read rule names, including files with trailing comments."""
    return [line for raw in path.read_text(encoding="utf-8").splitlines()
            if (line := raw.split("#", 1)[0].strip())]


def build(global_path: Path, sidecar_path: Path | None, extra_paths=()) -> list[str]:
    words = set(read_words(global_path))
    for path in (*extra_paths, sidecar_path):
        if path is not None and path.exists():
            words.update(read_words(path))
    return sorted(words, key=lambda word: (word.casefold(), word))


def project_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip())


def policy_sources(root: Path | None, user_dicts=(), user_ignores=()) -> tuple[list[Path], list[Path]]:
    dictionaries = [Path.home() / ".pv/dictionary.txt", *user_dicts]
    ignores = [Path.home() / ".pv/ignore-rules.txt", *user_ignores]
    if root is not None:
        dictionaries.append(root / ".pv/dictionary.txt")
        ignores.append(root / ".pv/ignore-rules.txt")
    return dictionaries, ignores


def merge_rules(bundled: Path, extra_paths=()) -> list[str]:
    rules = set(read_rules(bundled))
    for path in extra_paths:
        if path.exists():
            rules.update(read_rules(path))
    return sorted(rules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge Harper dictionaries and ignored rules.")
    parser.add_argument("--global", dest="global_path", type=Path, default=POLICY / "dictionary.txt")
    parser.add_argument("--ignore", type=Path, default=POLICY / "ignore-rules.txt", help="bundled rule file")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="essay directory for git-root discovery")
    parser.add_argument("--user-dict", type=Path, action="append", default=[], help="additional user dictionary (repeatable)")
    parser.add_argument("--user-ignore", type=Path, action="append", default=[], help="additional user rule file (repeatable)")
    parser.add_argument("--sidecar", type=Path, help="optional essay-local .harper-words")
    parser.add_argument("--out", type=Path, help="output dictionary path (default: temp file)")
    parser.add_argument("--json", action="store_true", help="report dictionary path, merged ignore rules and input paths")
    args = parser.parse_args(argv)
    dictionaries, ignores = policy_sources(project_root(args.cwd),
                                            [p.expanduser() for p in args.user_dict],
                                            [p.expanduser() for p in args.user_ignore])
    try:
        words = build(args.global_path, args.sidecar, dictionaries)
        rules = merge_rules(args.ignore, ignores) if args.json else []
        content = "\n".join(words) + ("\n" if words else "")
        if args.out:
            out = args.out
            out.write_text(content, encoding="utf-8")
        else:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".harper-dict.txt",
                                             delete=False, encoding="utf-8") as output:
                output.write(content)
                out = Path(output.name)
    except (OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        dictionary_sources = [args.global_path, *dictionaries]
        if args.sidecar:
            dictionary_sources.append(args.sidecar)
        print(json.dumps({"dictionary": str(out), "ignore_rules": ",".join(rules),
                          "sources": {"dictionary": [str(p) for p in dictionary_sources if p.is_file()],
                                      "ignore_rules": [str(p) for p in [args.ignore, *ignores] if p.is_file()]}}))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
