"""Harper normalization, output validation and per-document policy tests."""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import cli
from prosevoice_lib import policy as harper


def lint(**changes):
    result = {"kind": "Spelling", "rule": "SpellCheck", "priority": 63,
              "span": {"char_start": 0, "char_end": 4}, "line": 1, "column": 1,
              "matched_text": "alot", "message": "Possible typo",
              "suggestions": ['Replace with: “allot”']}
    result.update(changes)
    return result


class HarperTests(unittest.TestCase):
    def test_priority_dedup_preserves_alternate_rules_and_distinct_spans(self):
        specific = lint(rule="OpenCompounds", priority=31, suggestions=['Replace with: “a lot”'])
        other = lint(span={"char_start": 5, "char_end": 9})
        for group in ([lint(), specific, other], [specific, lint(), other]):
            findings = harper.normalize(group, "alot alot")
            self.assertEqual(len(findings), 2)
            self.assertEqual(findings[0]["rule"], "OpenCompounds")
            self.assertEqual(findings[0]["also"], ["SpellCheck"])
            self.assertEqual(findings[0]["replacement"], "a lot")
            self.assertTrue(findings[0]["fixable"])

    def test_unicode_offsets_require_exact_character_match(self):
        text = "é 🐈 alot"
        good = lint(span={"char_start": 4, "char_end": 8})
        self.assertTrue(harper.normalize([good], text)[0]["fixable"])
        for span in ({"char_start": 8, "char_end": 12}, {"char_start": 3, "char_end": 7}):
            finding = harper.normalize([lint(span=span)], text)[0]
            self.assertFalse(finding["offset_guard"])
            self.assertFalse(finding["fixable"])

    def test_candidates_exclude_names_grammar_dictionary_and_advisories(self):
        for entry, text, words, bucket in [
            (lint(matched_text="Alot"), "Alot", [], "name"),
            (lint(kind="Agreement"), "alot", [], "error"),
            (lint(), "alot", ["alot"], "spelling"),
            (lint(rule="DisjointPrefixes"), "alot", [], "advisory"),
            (lint(rule="LongSentences"), "alot", [], "advisory"),
        ]:
            with self.subTest(entry=entry):
                finding = harper.normalize([entry], text, words)[0]
                self.assertEqual(finding["bucket"], bucket)
                self.assertFalse(finding["fixable"])
        for suggestions in ([], ["Remove this"], ['Replace with: “a”', 'Replace with: “b”'],
                            ['Replace with: “a” then “b”'], ['Replace with: “a\nb”']):
            self.assertFalse(harper.normalize([lint(suggestions=suggestions)], "alot")[0]["fixable"])

    def test_json_shape_validation_and_nonzero_lint_exit(self):
        invalid = [{"error": "failed"}, None, [], [None], [{}], [{"lints": {}}],
                   [{"lints": [None]}], [{"lints": [lint(priority=True)]}],
                   [{"lints": [lint(span={"char_start": "0", "char_end": 4})]}],
                   [{"lints": [lint(suggestions=[{}])]}],
                   [{"lints": [lint(message=None)]}],
                   [{"lints": [], "error": "failed"}]]
        for data in invalid:
            with self.subTest(data=data), patch.object(harper.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 1, json.dumps(data), "failed")), self.assertRaises(RuntimeError):
                harper.lint_file("harper", Path("doc.md"), "us", "dict", [])
        for lints in ([], [lint()]):
            with patch.object(harper.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 1, json.dumps([{"lints": lints}]), "")) as run:
                self.assertEqual(harper.lint_file("harper", Path("doc.md"), "us", "dict", []), lints)
                self.assertIs(run.call_args.kwargs["check"], False)
        for output in ("", "not JSON"):
            with patch.object(harper.subprocess, "run", return_value=
                              subprocess.CompletedProcess([], 2, output, "failed")), self.assertRaises(RuntimeError):
                harper.lint_file("harper", Path("doc.md"), "us", "dict", [])
        with patch.object(harper.subprocess, "run", side_effect=OSError("cannot launch")), \
                self.assertRaises(RuntimeError):
            harper.lint_file("harper", Path("doc.md"), "us", "dict", [])

    def run_main(self, argv, cwd):
        old = Path.cwd()
        os.chdir(cwd)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(argv)
        finally:
            os.chdir(old)
        return json.loads(out.getvalue()), code

    def test_policy_isolation_repeatable_overrides_and_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()

            def write(relative, content):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return path

            bundled = root / "bundled"
            write("bundled/dictionary.txt", "base\n")
            write("bundled/ignore-rules.txt", "BaseRule\n")
            write("xdg/prosevoice/dictionary.txt", "user\n")
            write("xdg/prosevoice/ignore-rules.txt", "UserRule\n")
            for project in ("one", "two"):
                subprocess.run(["git", "init", "-q", str(root / project)], check=True)
                write(f"{project}/.prosevoice/dictionary.txt", f"{project}\n")
                write(f"{project}/.prosevoice/ignore-rules.txt", f"{project}Rule\n")
            doc1 = write("one/chapter/doc.md", "alot")
            doc2 = write("two/chapter/doc.md", "alot")
            doc3 = write("one/another/doc.md", "alot")
            write("one/chapter/.harper-words", "alot\n")
            extras = [write(f"extra{i}", f"extra{i}\n") for i in range(2)]
            extra_rules = [write(f"rules{i}", f"Rule{i}\n") for i in range(2)]
            seen = []

            def run_lint(exe, doc, dialect, dictionary, rules):
                path = Path(dictionary)
                seen.append((path, set(path.read_text().splitlines()), set(rules)))
                return [lint()]

            env = {"HOME": str(root / "home"), "XDG_CONFIG_HOME": str(root / "xdg"),
                   "GIT_CEILING_DIRECTORIES": str(root)}
            args = ["lint", str(doc1), str(doc2), str(doc3), "--dialect", "uk"]
            for path in extras:
                args += ["--user-dict", str(path)]
            for path in extra_rules:
                args += ["--user-ignore", str(path)]
            def resource(*parts):
                return bundled / parts[-1]

            with patch.dict(os.environ, env), patch.object(harper, "resource", resource), \
                    patch.object(harper.shutil, "which", return_value="harper"), \
                    patch.object(harper, "harper_version", return_value="harper 1"), \
                    patch.object(harper, "lint_file", side_effect=run_lint):
                payload, code = self.run_main(args, root)
            self.assertEqual(code, 0)
            report = payload["data"]
            self.assertEqual((report["status"], report["harper_version"], report["dialect"]),
                             ("ran", "harper 1", "uk"))
            self.assertEqual(report["counts"]["fixable"], 2)
            self.assertEqual(seen[0][1], {"base", "user", "one", "alot", "extra0", "extra1"})
            self.assertEqual(seen[1][1], {"base", "user", "two", "extra0", "extra1"})
            self.assertEqual(seen[2][1], {"base", "user", "one", "extra0", "extra1"})
            self.assertEqual(seen[1][2], {"BaseRule", "UserRule", "twoRule", "Rule0", "Rule1"})
            self.assertTrue(all(not path.exists() for path, _, _ in seen))
            self.assertEqual(doc1.read_text(), "alot")
            seen.clear()

            def fail(*args):
                seen.append(Path(args[3]))
                raise RuntimeError("bad output")

            with patch.dict(os.environ, env), patch.object(harper, "resource", resource), \
                    patch.object(harper.shutil, "which", return_value="harper"), \
                    patch.object(harper, "harper_version", return_value="harper 1"), \
                    patch.object(harper, "lint_file", side_effect=fail):
                payload, code = self.run_main(["lint", str(doc1)], root)
            self.assertEqual((payload["status"], code), ("error", 2))
            self.assertEqual(payload["diagnostics"][0]["code"], "harper-failed")
            self.assertFalse(seen[0].exists())

    def test_missing_harper_and_markdown_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            doc = root / "doc.md"
            doc.write_text("alot")
            env = {"HOME": str(root), "XDG_CONFIG_HOME": str(root / "xdg"), "GIT_CEILING_DIRECTORIES": str(root)}
            with patch.dict(os.environ, env), patch.object(harper.shutil, "which", return_value=None):
                payload, code = self.run_main(["lint", str(doc)], root)
            # Legacy exit 4 is now exit 0 with data.status "skipped" and a harper-unavailable diagnostic.
            self.assertEqual((payload["status"], code), ("ok", 0))
            self.assertEqual(payload["data"]["status"], "skipped")
            self.assertEqual([d["code"] for d in payload["diagnostics"]], ["harper-unavailable"])
            invalid = doc.with_suffix(".txt")
            invalid.write_text("alot")
            with patch.dict(os.environ, env):
                payload, code = self.run_main(["lint", str(invalid)], root)
            self.assertEqual((payload["status"], code), ("error", 2))
            self.assertEqual(payload["diagnostics"][0]["code"], "not-markdown")


if __name__ == "__main__":
    unittest.main()
