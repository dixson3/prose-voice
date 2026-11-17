"""Companion-rule targets, managed-block parser, preview and apply behavior.

Run with uv run python -m unittest discover -s tests.
"""
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import cli, rules
from prosevoice_lib import config as cfg

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = (ROOT / "skills/prosevoice/PROSEVOICE-PROTOCOL.md").read_text(encoding="utf-8").strip("\n")
B, E = rules.BEGIN, rules.END
LEGACY_BEGIN = "<!-- BEGIN pv-protocol (managed by pv-preflight; edits are overwritten) -->"
LEGACY_END = "<!-- END pv-protocol -->"


def block(body=PROTOCOL, nl="\n"):
    return nl.join([B, *body.split("\n"), E]) + nl


def found(text, begin=B, end=E) -> rules.Block:
    result = rules.find_block(text, begin, end)
    assert result is not None, "expected a managed block"
    return result


class RulesEnv(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.base / "xdg"),
               "GIT_CEILING_DIRECTORIES": str(self.base)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def config(self, project=None):
        return cfg.load_config(project, cwd=self.project)

    def install(self, base, *where):
        for relative in where:
            (base / relative / "prosevoice").mkdir(parents=True, exist_ok=True)

    def snapshot(self):
        return {p: p.read_bytes() for root in (self.home, self.project)
                for p in root.rglob("*") if p.is_file() and ".git/" not in str(p)}

    def run_cli(self, *argv):
        old = Path.cwd()
        os.chdir(self.project)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(list(argv))
        finally:
            os.chdir(old)
        return json.loads(out.getvalue()), code


class TargetDiscoveryTests(RulesEnv):
    def targets(self):
        return [(t["scope"], t["harness"], t["kind"], t["path"]) for t in
                rules.rule_targets(self.config(), self.home)]

    def test_no_installation_no_targets(self):
        self.assertEqual(self.targets(), [])

    def test_project_claude_and_agents_targets(self):
        self.install(self.project, ".claude/skills", ".agents/skills")
        self.assertEqual(self.targets(), [
            ("project", "claude-code", "file", self.project / ".claude/rules/PROSEVOICE-PROTOCOL.md"),
            ("project", "pi|codex|opencode", "block", self.project / "AGENTS.md"),
        ])

    def test_global_targets_follow_existing_harness_dirs(self):
        self.install(self.home, ".claude/skills", ".agents/skills")
        self.assertEqual([t[1] for t in self.targets()], ["claude-code"])
        for harness in (".pi", ".codex", ".config/opencode"):
            (self.home / harness).mkdir(parents=True)
        self.assertEqual(self.targets(), [
            ("global", "claude-code", "file", self.home / ".claude/rules/PROSEVOICE-PROTOCOL.md"),
            ("global", "pi", "block", self.home / ".pi/agent/AGENTS.md"),
            ("global", "codex", "block", self.home / ".codex/AGENTS.md"),
            ("global", "opencode", "block", self.home / ".config/opencode/AGENTS.md"),
        ])

    def test_opencode_skill_dir_alone_and_shared_install_target_once(self):
        self.install(self.home, ".config/opencode/skills")
        self.assertEqual([t[1] for t in self.targets()], ["opencode"])
        self.install(self.home, ".agents/skills")
        self.assertEqual([t[1] for t in self.targets()], ["opencode"])

    def test_project_equal_to_home_is_deduplicated(self):
        subprocess.run(["git", "-C", str(self.home), "init", "-q"], check=True)
        self.install(self.home, ".claude/skills")
        targets = rules.rule_targets(self.config(self.home), self.home)
        self.assertEqual([(t["scope"], t["harness"]) for t in targets], [("project", "claude-code")])

    def test_legacy_installation_is_not_recognized(self):
        (self.project / ".claude/skills/pv-prosevoice").mkdir(parents=True)
        (self.home / ".agents/skills/pv-prosevoice").mkdir(parents=True)
        (self.home / ".pi").mkdir()
        self.assertEqual(self.targets(), [])


class BlockParserTests(unittest.TestCase):
    def test_well_formed_and_absent(self):
        self.assertIsNone(rules.find_block("# Title\n\nText\n", B, E))
        two_lines = block("one\ntwo")
        located = found("# Title\n\n" + two_lines + "tail\n")
        self.assertEqual((located.begin, located.end, located.body), (2, 5, "one\ntwo"))

    def test_malformed_nested_duplicate_and_unpaired_are_rejected(self):
        cases = {
            "begin without end": f"{B}\nbody\n",
            "end without begin": f"text\n{E}\n",
            "nested": f"{B}\n{B}\nx\n{E}\n{E}\n",
            "duplicate": block("a") + "\n" + block("b"),
            "malformed begin": "<!-- BEGIN prosevoice -->\nx\n" + E + "\n",
            "malformed end": f"{B}\nx\n<!-- END prosevoice (old) -->\n",
            "indented marker": f"  {B}\nx\n{E}\n",
            "suffixed name": f"<!-- BEGIN prosevoice-extra -->\nx\n{E}\n",
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(rules.BlockError):
                rules.find_block(text, B, E)

    def test_other_managed_blocks_are_unrelated_content(self):
        text = f"{LEGACY_BEGIN}\nold\n{LEGACY_END}\n<!-- BEGIN yf rules -->\nx\n<!-- END yf rules -->\n"
        self.assertIsNone(rules.find_block(text, B, E))
        self.assertEqual(found(text, LEGACY_BEGIN, LEGACY_END).body, "old")

    def test_install_append_replace_and_remove_preserve_unrelated_bytes(self):
        original = "# Agents\n\nKeep  this\ttext.\n"
        installed = rules.replace_block(original, B, E, "rule v1")
        self.assertEqual(installed, original + "\n" + block("rule v1"))
        refreshed = rules.replace_block(installed + "after\n", B, E, "rule v2")
        self.assertEqual(refreshed, original + "\n" + block("rule v2") + "after\n")
        self.assertEqual(rules.replace_block(installed, B, E, None), original)
        self.assertEqual(rules.replace_block(original, B, E, None), original)
        self.assertEqual(rules.replace_block("", B, E, "r"), block("r"))

    def test_crlf_and_missing_final_newline(self):
        original = "# Agents\r\nLine\r\n"
        installed = rules.replace_block(original, B, E, "r1")
        self.assertEqual(installed, original + "\r\n" + block("r1", "\r\n"))
        self.assertEqual(found(installed).body, "r1")
        self.assertEqual(rules.replace_block(installed, B, E, None), original)
        no_newline = rules.replace_block("text", B, E, "r")
        self.assertEqual(no_newline, "text\n\n" + block("r"))
        middle = f"top\n{B}\nold\n{E}"
        self.assertEqual(rules.replace_block(middle, B, E, "new"), f"top\n{B}\nnew\n{E}")


class RuleCommandTests(RulesEnv):
    def setUp(self):
        super().setUp()
        self.install(self.project, ".claude/skills", ".agents/skills")
        self.install(self.home, ".agents/skills")
        (self.home / ".pi/agent").mkdir(parents=True)
        self.pi = self.home / ".pi/agent/AGENTS.md"
        self.pi.write_text(f"# Mine\n\n{LEGACY_BEGIN}\nlegacy\n{LEGACY_END}\n\nOther rules.\n", encoding="utf-8")
        self.pi_original = self.pi.read_bytes()

    def test_preview_is_default_and_never_writes(self):
        before = self.snapshot()
        payload, code = self.run_cli("rule")
        self.assertEqual((payload["status"], code), ("ok", 0))
        self.assertFalse(payload["data"]["applied"])
        self.assertEqual([t["action"] for t in payload["data"]["targets"]], ["install", "install", "install"])
        self.assertEqual(self.snapshot(), before)
        payload, _ = self.run_cli("rule", "--remove")
        self.assertEqual(self.snapshot(), before)

    def test_apply_is_idempotent_and_preserves_unrelated_content(self):
        payload, code = self.run_cli("rule", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["data"]["changed"]), 3)
        self.assertTrue(all(t["state"] == "current" for t in payload["data"]["after"]))
        self.assertEqual((self.project / ".claude/rules/PROSEVOICE-PROTOCOL.md").read_text(), PROTOCOL + "\n")
        text = self.pi.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(self.pi_original.decode()))
        self.assertIn(LEGACY_BEGIN, text)  # legacy blocks belong to migration only
        after_first = self.snapshot()
        payload, code = self.run_cli("rule", "--apply")
        self.assertEqual((code, payload["data"]["changed"]), (0, []))
        self.assertEqual([t["action"] for t in payload["data"]["targets"]], ["none"] * 3)
        self.assertEqual(self.snapshot(), after_first)

    def test_stale_block_is_refreshed_in_place(self):
        agents = self.project / "AGENTS.md"
        agents.write_text(f"head\n{B}\nold rule\n{E}\ntail\n", encoding="utf-8")
        payload, _ = self.run_cli("rule")
        states = {t["path"]: (t["state"], t["action"]) for t in payload["data"]["targets"]}
        self.assertEqual(states[str(agents)], ("stale", "refresh"))
        self.run_cli("rule", "--apply")
        self.assertEqual(agents.read_text(), f"head\n{block()}tail\n")

    def test_remove_restores_original_bytes(self):
        self.run_cli("rule", "--apply")
        _, code = self.run_cli("rule", "--remove", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(self.pi.read_bytes(), self.pi_original)
        self.assertFalse((self.project / ".claude/rules/PROSEVOICE-PROTOCOL.md").exists())
        self.assertEqual((self.project / "AGENTS.md").read_text(), "")

    def test_malformed_block_blocks_every_write(self):
        self.pi.write_text(f"{self.pi_original.decode()}{B}\nunterminated\n", encoding="utf-8")
        before = self.snapshot()
        payload, code = self.run_cli("rule", "--apply")
        self.assertEqual((payload["status"], code), ("blocked", 1))
        self.assertFalse(payload["data"]["applied"])
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["managed-block-malformed"])
        self.assertEqual(self.snapshot(), before)

    def test_check_reports_rule_state_without_writing(self):
        before = self.snapshot()
        with patch.object(rules.shutil, "which", return_value="/tool"):
            report = rules.check(self.config(), self.home)
        self.assertEqual({r["state"] for r in report["rules"]}, {"missing"})
        self.assertTrue(any("PROSEVOICE-PROTOCOL.md" in a for a in report["actions"]))
        self.assertEqual(self.snapshot(), before)

    def test_missing_installation_is_reported(self):
        for path in (self.project / ".claude", self.project / ".agents", self.home / ".agents"):
            subprocess.run(["rm", "-rf", str(path)], check=True)
        payload, code = self.run_cli("rule", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["installation-missing"])
        self.assertEqual(self.pi.read_bytes(), self.pi_original)


if __name__ == "__main__":
    unittest.main()
