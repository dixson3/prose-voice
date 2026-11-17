"""Harper policy union tests. Run with uv run python -m unittest discover -s tests."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import config as cfg
from prosevoice_lib import policy

LAUNCHER = Path(__file__).resolve().parents[1] / "skills/prosevoice/scripts/prosevoice.py"


class HarperPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.xdg = self.root / "xdg"
        self.user = self.xdg / "prosevoice"
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.xdg),
                    "GIT_CEILING_DIRECTORIES": str(self.root)}
        patcher = patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def config(self):
        return cfg.load_config(cwd=self.project)

    def test_all_dictionary_layers_merge_without_case_folding_or_input_writes(self):
        bundled = self.write(self.root / "bundled.txt", "# defaults\nShared\nBase\n")
        user = self.write(self.user / "dictionary.txt", "Shared\nUserWord\n")
        project = self.write(self.project / ".prosevoice/dictionary.txt", "ProjectWord\nshared\n")
        explicit = self.write(self.root / "custom-user.txt", "ExternalWord\n")
        local = self.write(self.project / "chapter/.harper-words", "LocalWord\nShared\n")
        before = {p: p.read_bytes() for p in (bundled, user, project, explicit, local)}
        dictionaries, _ = policy.policy_sources(self.config(), [explicit])
        self.assertEqual(policy.build(bundled, local, dictionaries),
                         ["Base", "ExternalWord", "LocalWord", "ProjectWord", "Shared", "shared", "UserWord"])
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_ignore_rules_merge_with_comments_and_duplicates(self):
        bundled = self.write(self.root / "rules.txt", "UseTitleCase # bundled\n\n# comment\n")
        self.write(self.user / "ignore-rules.txt", "LongSentences\nUseTitleCase\n")
        self.write(self.project / ".prosevoice/ignore-rules.txt", "DisjointPrefixes # project choice\n")
        explicit = self.write(self.root / "other-rules.txt", "SpellCheck\n")
        _, ignores = policy.policy_sources(self.config(), user_ignores=[explicit])
        self.assertEqual(policy.merge_rules(bundled, ignores),
                         ["DisjointPrefixes", "LongSentences", "SpellCheck", "UseTitleCase"])

    def test_missing_optional_inputs_and_invalid_present_file(self):
        bundled = self.write(self.root / "base.txt", "Base\n")
        dictionaries, ignores = policy.policy_sources(self.config())
        self.assertEqual(policy.build(bundled, self.root / "missing", dictionaries), ["Base"])
        rules = self.write(self.root / "base-rules.txt", "")
        self.assertEqual(policy.merge_rules(rules, ignores), [])
        bad = self.project / ".prosevoice/dictionary.txt"
        bad.mkdir(parents=True)
        with self.assertRaises(OSError):
            policy.build(bundled, None, dictionaries)

    def test_cli_finds_project_from_nested_essay_directory(self):
        essay_dir = self.project / "chapters"
        essay = self.write(essay_dir / "essay.md", "Text\n")
        self.write(essay_dir / ".harper-words", "LocalToken\n")
        self.write(self.project / ".prosevoice/dictionary.txt", "ProjectToken\n")
        self.write(self.project / ".prosevoice/ignore-rules.txt", "UseTitleCase\n")
        output = self.root / "merged.txt"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        for argv, cwd in ((["policy", "--out", str(output)], essay_dir),
                          (["policy", str(essay), "--out", str(output)], self.root)):
            with self.subTest(argv=argv):
                result = subprocess.run([sys.executable, "-I", str(LAUNCHER), *argv], cwd=cwd, env=env,
                                        capture_output=True, text=True, check=True)
                report = json.loads(result.stdout)["data"]
                self.assertEqual(report["dictionary"], str(output))
                self.assertIn("ProjectToken", output.read_text().splitlines())
                self.assertIn("UseTitleCase", report["ignore_rules"].split(","))
                self.assertIn(str(self.project / ".prosevoice/dictionary.txt"), report["sources"]["dictionary"])
        self.assertIn("LocalToken", output.read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
