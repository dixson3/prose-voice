"""Harper policy union tests. Run with uv run python -m unittest discover -s tests."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/pv-prosevoice/scripts/build_user_dict.py"
spec = importlib.util.spec_from_file_location("harper_policy", SCRIPT)
assert spec is not None and spec.loader is not None
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class HarperPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        patcher = patch.object(Path, "home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_all_dictionary_layers_merge_without_case_folding_or_input_writes(self):
        bundled = self.write(self.root / "bundled.txt", "# defaults\nShared\nBase\n")
        user = self.write(self.home / ".prose-voice/dictionary.txt", "Shared\nUserWord\n")
        project = self.write(self.project / ".prose-voice/dictionary.txt", "ProjectWord\nshared\n")
        explicit = self.write(self.root / "custom-user.txt", "ExternalWord\n")
        local = self.write(self.project / "chapter/.harper-words", "LocalWord\nShared\n")
        before = {p: p.read_bytes() for p in (bundled, user, project, explicit, local)}
        dictionaries, _ = policy.policy_sources(self.project, [explicit])
        self.assertEqual(policy.build(bundled, local, dictionaries),
                         ["Base", "ExternalWord", "LocalWord", "ProjectWord", "Shared", "shared", "UserWord"])
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_ignore_rules_merge_with_comments_and_duplicates(self):
        bundled = self.write(self.root / "rules.txt", "UseTitleCase # bundled\n\n# comment\n")
        self.write(self.home / ".prose-voice/ignore-rules.txt", "LongSentences\nUseTitleCase\n")
        self.write(self.project / ".prose-voice/ignore-rules.txt", "DisjointPrefixes # project choice\n")
        explicit = self.write(self.root / "other-rules.txt", "SpellCheck\n")
        _, ignores = policy.policy_sources(self.project, user_ignores=[explicit])
        self.assertEqual(policy.merge_rules(bundled, ignores),
                         ["DisjointPrefixes", "LongSentences", "SpellCheck", "UseTitleCase"])

    def test_missing_optional_inputs_and_invalid_present_file(self):
        bundled = self.write(self.root / "base.txt", "Base\n")
        dictionaries, ignores = policy.policy_sources(self.project)
        self.assertEqual(policy.build(bundled, self.root / "missing", dictionaries), ["Base"])
        rules = self.write(self.root / "base-rules.txt", "")
        self.assertEqual(policy.merge_rules(rules, ignores), [])
        bad = self.project / ".prose-voice/dictionary.txt"
        bad.mkdir(parents=True)
        with self.assertRaises(OSError):
            policy.build(bundled, None, dictionaries)

    def test_cli_finds_project_from_nested_essay_directory(self):
        essay_dir = self.project / "chapters"
        essay_dir.mkdir()
        self.write(self.project / ".prose-voice/dictionary.txt", "ProjectToken\n")
        self.write(self.project / ".prose-voice/ignore-rules.txt", "UseTitleCase\n")
        output = self.root / "merged.txt"
        result = subprocess.run([sys.executable, str(SCRIPT), "--cwd", str(essay_dir),
                                 "--out", str(output), "--json"], capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["dictionary"], str(output))
        self.assertIn("ProjectToken", output.read_text().splitlines())
        self.assertIn("UseTitleCase", report["ignore_rules"].split(","))
        self.assertIn(str(self.project / ".prose-voice/dictionary.txt"), report["sources"]["dictionary"])


if __name__ == "__main__":
    unittest.main()
