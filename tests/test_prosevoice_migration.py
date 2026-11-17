"""Legacy prose-voice migration: preservation, conflicts, rule switching and interrupted apply.

Every fixture lives in a temporary directory with an isolated HOME, XDG_CONFIG_HOME and Git
ceiling; no real project, user directory or installed tooling is touched.

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
from prosevoice_lib import cli, migration, rules

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/legacy_rules"
PROTOCOL = (ROOT / "skills/prosevoice/PROSEVOICE-PROTOCOL.md").read_text(encoding="utf-8").strip("\n")
PV_BEGIN, PV_END = migration.LEGACY_BLOCKS["pv-protocol"]
BV_BEGIN, BV_END = migration.LEGACY_BLOCKS["blog-voice"]
VOICE = "# Voice\n\nPlain, direct sentences.\n"
AUDIENCE = "# Audience\n\nEngineers who read closely.\n"
UNFILLED = "# Voice\n\n<!-- pv-template: unfilled -->\n"


def legacy_rule(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip("\n")


def legacy_block(begin: str, end: str, body: str) -> str:
    return f"{begin}\n{body}\n{end}\n"


class MigrationEnv(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.xdg = self.base / "xdg"
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.xdg),
               "GIT_CEILING_DIRECTORIES": str(self.base)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, migration, "FAULT_HOOK", None)
        self.legacy = self.project / ".prose-voice"
        self.new = self.project / ".prosevoice"
        self.user = self.xdg / "prosevoice"
        self.legacy_user = self.home / ".prose-voice"

    # ------------------------------------------------------------------ helpers

    def write(self, path: Path, content: str | bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_bytes(content.encode("utf-8"))
        return path

    def run_cli(self, *argv, cwd: Path | None = None):
        old = Path.cwd()
        os.chdir(cwd or self.project)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(list(argv))
        finally:
            os.chdir(old)
        return json.loads(out.getvalue()), code

    def migrate(self, *argv):
        payload, code = self.run_cli("migrate", *argv)
        self.assertEqual(payload["command"], "migrate")
        return payload, code

    def snapshot(self) -> dict:
        out = {}
        for path in self.base.rglob("*"):
            if ".git" in path.relative_to(self.base).parts:
                continue
            rel = str(path.relative_to(self.base))
            if path.is_symlink():
                out[rel] = ("link", os.readlink(path))
            elif path.is_file():
                out[rel] = path.read_bytes()
        return out

    def legacy_guides(self):
        self.write(self.legacy / "VOICE.md", VOICE)
        self.write(self.legacy / "AUDIENCE.md", AUDIENCE)

    def resolved(self, name: str):
        payload, _ = self.run_cli("resolve")
        return payload["data"]["guidance"][name]["resolved"]

    def policy(self) -> dict:
        """Merged policy with the dictionary written inside the fixture: words, rules, sources."""
        out = self.base / "merged-dictionary.txt"
        payload, code = self.run_cli("policy", "--out", str(out))
        self.assertEqual(code, 0, payload["diagnostics"])
        words = out.read_text(encoding="utf-8").splitlines()
        out.unlink()
        return {"words": words, "rules": payload["data"]["ignore_rule_list"],
                "sources": payload["data"]["sources"]}

    def manifests(self, base: Path | None = None) -> list[Path]:
        return sorted((base or self.new / "migrations").glob("*/manifest.json"))

    def assert_preview_unchanged(self, *argv, operation="would-change", code=0):
        before = self.snapshot()
        payload, exit_code = self.migrate(*argv)
        self.assertEqual(payload["data"]["operation"], operation, payload["diagnostics"])
        self.assertEqual(exit_code, code)
        self.assertEqual(self.snapshot(), before, "preview/blocked migration must not write")
        return payload

    def apply_ok(self, *argv):
        payload, code = self.migrate(*argv, "--apply")
        self.assertEqual((payload["data"]["operation"], code), ("applied", 0), payload["diagnostics"])
        return payload

    def codes(self, payload) -> set:
        return {d["code"] for d in payload["diagnostics"]}

    def install(self, base: Path, *where: str):
        for relative in where:
            (base / relative / "prosevoice").mkdir(parents=True, exist_ok=True)


# ====================================================================== success cases


class ProjectSuccessTests(MigrationEnv):
    def test_no_config_project_preview_apply_and_equal_rerun(self):
        self.legacy_guides()
        essay = self.write(self.project / "posts/one.md", "# One\n\nBody.\n")
        legacy_bytes = {p: p.read_bytes() for p in self.legacy.rglob("*") if p.is_file()}
        payload = self.assert_preview_unchanged()
        data = payload["data"]
        self.assertEqual(data["migration_version"], 1)
        self.assertEqual(data["scope"], "project")
        self.assertIsNone(data["translated_config"])
        self.assertTrue(all(r["sha256"] for r in data["reads"] if r["path"].endswith("VOICE.md")))
        self.assertTrue(data["recovery"])
        self.assertIsNone(self.resolved("VOICE.md"), "ordinary runtime must ignore legacy data")

        applied = self.apply_ok()["data"]
        self.assertEqual(applied["actions"][0]["state"], "done")
        self.assertFalse((self.new / "config.json").exists(), "no legacy config means no new config")
        self.assertEqual((self.new / "VOICE.md").read_text(encoding="utf-8"), VOICE)
        self.assertEqual(self.resolved("VOICE.md")["level"], "project")
        self.assertTrue(applied["equivalence"]["guidance"]["AUDIENCE.md"]["equal"])
        manifest = json.loads(Path(applied["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "complete")
        self.assertNotIn("cache", Path(applied["manifest"]).relative_to(self.new).parts)
        for path, data_bytes in legacy_bytes.items():
            self.assertEqual(path.read_bytes(), data_bytes, "legacy data must stay intact")
        self.assertEqual(essay.read_text(encoding="utf-8"), "# One\n\nBody.\n")

        before = self.snapshot()
        rerun, code = self.migrate("--apply")
        self.assertEqual((rerun["data"]["operation"], code), ("unchanged", 0))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.manifests()), 1, "an equal rerun creates no new manifest")

    def test_ordered_and_external_guides_are_preserved(self):
        shared = self.write(self.base / "shared/VOICE.md", "# Shared voice\n\nTeam rules.\n")
        self.write(self.legacy / "team/VOICE.md", "# Team voice\n\nLocal.\n")
        self.write(self.legacy / "AUDIENCE.md", AUDIENCE)
        self.write(self.legacy / "config.json", json.dumps({
            "guidance": {"VOICE.md": ["../shared/VOICE.md", ".prose-voice/team/VOICE.md"]}}))
        shared_before = shared.read_bytes()
        data = self.assert_preview_unchanged()["data"]
        self.assertEqual(data["translated_config"], {
            "schema_version": 1, "guidance": {"VOICE.md": ["../shared/VOICE.md", ".prosevoice/team/VOICE.md"]}})
        external = [e for e in data["external_references"] if e["value"] == "../shared/VOICE.md"]
        self.assertEqual(external[0]["referent"], str(shared))
        self.assertIn("external", external[0]["ownership"])
        self.apply_ok()
        self.assertEqual(Path(self.resolved("VOICE.md")["path"]), shared)
        self.assertEqual(shared.read_bytes(), shared_before)
        self.assertEqual((self.new / "team/VOICE.md").read_text(encoding="utf-8"), "# Team voice\n\nLocal.\n")
        config = json.loads((self.new / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["guidance"]["VOICE.md"][1], ".prosevoice/team/VOICE.md")
        # Removing the external file falls through to the migrated second candidate, as before.
        shared.unlink()
        self.assertEqual(Path(self.resolved("VOICE.md")["path"]), (self.new / "team/VOICE.md"))

    def test_user_only_fallback_blocks_until_user_migration(self):
        self.write(self.legacy_user / "VOICE.md", VOICE)
        self.write(self.legacy_user / "AUDIENCE.md", AUDIENCE)
        self.write(self.legacy_user / "dictionary.txt", "Kubernetes\n")
        self.write(self.legacy / "ignore-rules.txt", "LongSentences\n")
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("user-dependency-unmet", self.codes(payload))
        deps = payload["data"]["dependencies"]
        self.assertIn(str(self.user / "VOICE.md"), [d["requires"] for d in deps])
        self.assertIn(str(self.user / "dictionary.txt"), [d["requires"] for d in deps])

        user = self.apply_ok("--scope", "user")["data"]
        self.assertEqual(user["scope"], "user")
        self.assertFalse(self.new.exists(), "user migration must not write project files")
        self.assertEqual((self.user / "dictionary.txt").read_text(encoding="utf-8"), "Kubernetes\n")
        self.assertTrue(self.manifests(self.user / "migrations"))

        applied = self.apply_ok()["data"]
        self.assertTrue(applied["equivalence"]["policy"]["dictionary"]["equal"])
        self.assertEqual(self.resolved("VOICE.md")["level"], "user")
        self.assertEqual(self.legacy_user.joinpath("VOICE.md").read_text(encoding="utf-8"), VOICE)

    def test_mixed_fallback_and_user_policy_retained_with_project_guides(self):
        self.write(self.legacy / "VOICE.md", VOICE)
        self.write(self.legacy_user / "VOICE.md", "# User voice\n\nUnused here.\n")
        self.write(self.legacy_user / "AUDIENCE.md", AUDIENCE)
        self.write(self.legacy_user / "ignore-rules.txt", "SpellCheck # noisy\n")
        self.write(self.legacy_user / "notes.txt", "keep me\n")
        self.assertEqual(self.migrate()[1], 1)
        user = self.apply_ok("--scope", "user")["data"]
        self.assertIn(str(self.legacy_user / "notes.txt"), [r["path"] for r in user["retained"]])
        self.assertFalse((self.user / "notes.txt").exists())
        self.assertEqual((self.user / "VOICE.md").read_text(encoding="utf-8"), "# User voice\n\nUnused here.\n")
        self.apply_ok()
        self.assertEqual(self.resolved("VOICE.md")["level"], "project")
        self.assertEqual(self.resolved("AUDIENCE.md")["level"], "user")
        self.assertIn("SpellCheck", self.policy()["rules"])

    def test_cache_mode_duplicate_stems_links_and_visual_choices(self):
        self.legacy_guides()
        a = self.write(self.project / "a/post.md", "# A\n\nText.\n<!-- illus:flow1 -->\n")
        b = self.write(self.project / "b/post.md", "# B\n\nText.\n<!-- illus:pic -->\n")
        self.write(self.project / "c/post.md", "# C\n\nNo visuals.\n")
        self.write(self.project / "a/images/flow1.svg", "<svg/>")
        side_a = ("## illus:flow1 — sequence\n\n- Source: ../../../a/images/flow1.mmd\n"
                  "- Render: ../../../a/images/flow1.svg\n![flow](../../../a/images/flow1.svg)\n"
                  "![candidate](cand/flow1-v2.png)\n\n```text\n![raw](cand/keep.png)\n```\n\nselected: flow1svg\n")
        side_b = "## illus:pic — photo\n\nselected: no-image\n"
        self.write(self.legacy / "cache/a/post.illustrations.md", side_a)
        self.write(self.legacy / "cache/a/cand/flow1-v2.png", b"png")
        self.write(self.legacy / "cache/b/post.illustrations.md", side_b)
        self.write(self.legacy / "cache/a/post.review.md", "old review\n")
        ready_before = {str(p): self.run_cli("ready", str(p))[0]["data"]["ready"] for p in (a, b)}
        self.assertEqual(ready_before, {str(a): False, str(b): False}, "runtime ignores legacy sidecars")

        data = self.assert_preview_unchanged()["data"]
        self.assertEqual({Path(e["essay"]) for e in data["essays"]}, {a, b})
        rewrites = {r["from"]: r["to"] for r in data["link_rewrites"]}
        self.assertEqual(rewrites, {"cand/flow1-v2.png": "../../../.prose-voice/cache/a/cand/flow1-v2.png"})
        self.assertIn(str(self.legacy / "cache/a/post.review.md"), [s["path"] for s in data["skipped"]])

        self.apply_ok()
        new_a = (self.new / "cache/a/post.illustrations.md").read_text(encoding="utf-8")
        self.assertIn("![flow](../../../a/images/flow1.svg)", new_a)
        self.assertIn("![candidate](../../../.prose-voice/cache/a/cand/flow1-v2.png)", new_a)
        self.assertIn("![raw](cand/keep.png)", new_a, "fenced code is not rewritten")
        self.assertTrue((self.new / "cache/a" / "../../../.prose-voice/cache/a/cand/flow1-v2.png").resolve().is_file())
        self.assertEqual((self.new / "cache/b/post.illustrations.md").read_text(encoding="utf-8"), side_b)
        for essay in (a, b):
            ready, code = self.run_cli("ready", str(essay))
            self.assertEqual((ready["data"]["ready"], code), (True, 0), ready["diagnostics"])
        self.assertFalse((self.new / "cache/a/post.review.md").exists())

    def test_adjacent_mode_leaves_sidecars_and_essays_untouched(self):
        self.legacy_guides()
        self.write(self.legacy / "config.json", json.dumps({"artifacts": {"location": "adjacent"}}))
        essay = self.write(self.project / "essay.md", "# E\n\n<!-- illus:x1 -->\n")
        side = self.write(self.project / "essay.illustrations.md", "## illus:x1 — y\n\nselected: x1\n")
        self.write(self.project / ".harper-words", "Zyx\n")
        before = {p: p.read_bytes() for p in (essay, side, self.project / ".harper-words")}
        data = self.apply_ok()["data"]
        self.assertEqual(data["equivalence"]["artifacts"], {"legacy": "adjacent", "new": "adjacent", "equal": True})
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse((self.new / "cache").exists())
        ready, code = self.run_cli("ready", str(essay))
        self.assertEqual((ready["data"]["ready"], code), (True, 0))

    def test_missing_visual_decision_keeps_blocked_ready_outcome(self):
        self.legacy_guides()
        essay = self.write(self.project / "e.md", "# E\n\n<!-- illus:q -->\n")
        data = self.apply_ok()["data"]
        entry = data["equivalence"]["ready"][0]
        self.assertEqual(Path(entry["essay"]), essay)
        self.assertFalse(entry["legacy"]["resolved"])
        self.assertTrue(entry["equal"])

    def test_blank_templates_policy_and_custom_ignores_copied_exactly(self):
        self.write(self.legacy / "VOICE.md", UNFILLED)
        self.write(self.legacy / "AUDIENCE.md", AUDIENCE)
        self.write(self.legacy / "dictionary.txt", "Foo\nfoo\n# comment\n")
        self.write(self.legacy / "ignore-rules.txt", "LongSentences  # wordy\n")
        self.write(self.legacy / ".gitignore", "/cache/\n*.local.md\n")
        self.write(self.legacy / "extra/notes.md", "operator notes\n")
        data = self.apply_ok()["data"]
        for name in ("VOICE.md", "dictionary.txt", "ignore-rules.txt", ".gitignore"):
            self.assertEqual((self.new / name).read_bytes(), (self.legacy / name).read_bytes(), name)
        self.assertIsNone(self.resolved("VOICE.md"), "the unfilled marker keeps the blank inactive")
        self.assertIn(str(self.legacy / "extra/notes.md"), [r["path"] for r in data["retained"]])
        self.assertFalse((self.new / "extra").exists())
        policy = self.policy()
        self.assertIn("Foo", policy["words"])
        self.assertIn("foo", policy["words"])
        self.assertIn("LongSentences", policy["rules"])

    def test_equal_destination_is_a_noop(self):
        self.legacy_guides()
        self.write(self.new / "VOICE.md", VOICE)
        self.write(self.legacy / "config.json", json.dumps({"artifacts": {"location": "cache"}}))
        self.write(self.new / "config.json", json.dumps({"artifacts": {"location": "cache"}, "schema_version": 1}))
        data = self.migrate()[0]["data"]
        unchanged = {Path(u["path"]).name for u in data["unchanged"]}
        self.assertEqual(unchanged, {"VOICE.md", "config.json"})
        self.assertEqual([Path(a["path"]).name for a in data["actions"]], ["AUDIENCE.md"])


# ====================================================================== rules


class RuleMigrationTests(MigrationEnv):
    def test_project_rule_files_and_blocks_switch_last(self):
        self.legacy_guides()
        self.install(self.project, ".claude/skills", ".agents/skills")
        rules_dir = self.project / ".claude/rules"
        self.write(rules_dir / "PV-PROTOCOL.md", legacy_rule("PV-PROTOCOL.v1.md") + "\n")
        self.write(rules_dir / "BLOG_VOICE.md", legacy_rule("BLOG_VOICE.md") + "\n")
        unrelated_top = "# Project agents\r\n\r\nKeep this.\r\n\r\n"
        agents_text = (unrelated_top
                       + legacy_block(PV_BEGIN, PV_END, legacy_rule("PV-PROTOCOL.v4.md")).replace("\n", "\r\n")
                       + "\r\nMiddle text.\r\n\r\n"
                       + legacy_block(BV_BEGIN, BV_END, legacy_rule("BLOG_VOICE.md")).replace("\n", "\r\n")
                       + "Tail.")
        agents = self.write(self.project / "AGENTS.md", agents_text.encode("utf-8"))
        order = []
        migration.FAULT_HOOK = lambda point, action: order.append((point, action and action["phase"]))
        data = self.apply_ok()["data"]
        new_rule = rules_dir / rules.PROTOCOL_NAME
        self.assertEqual(new_rule.read_text(encoding="utf-8"), PROTOCOL + "\n")
        self.assertFalse((rules_dir / "PV-PROTOCOL.md").exists())
        self.assertFalse((rules_dir / "BLOG_VOICE.md").exists())
        result = agents.read_bytes().decode("utf-8")
        block = rules.find_block(result, rules.BEGIN, rules.END)
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block.body, PROTOCOL)
        lines = result.splitlines(keepends=True)
        outside = "".join(lines[:block.begin] + lines[block.end + 1:])
        self.assertEqual(outside, unrelated_top + "\r\nMiddle text.\r\n\r\n" + "Tail.")
        self.assertNotIn("pv-protocol", result)
        self.assertNotIn("blog-voice", result)
        backups = {Path(b["path"]).name for b in data["backups"]}
        self.assertEqual(backups, {"PV-PROTOCOL.md", "BLOG_VOICE.md", "AGENTS.md"})
        for entry in data["backups"]:
            if Path(entry["path"]).name == "AGENTS.md":
                self.assertEqual(Path(entry["backup"]).read_bytes(), agents_text.encode("utf-8"))
        phases = [phase for point, phase in order if point == "before-replace"]
        self.assertEqual(phases, sorted(phases), "data writes precede rule activation")
        self.assertLess(order.index(("before-rules", None)), order.index(("before-replace", "rule")))
        check, _ = self.run_cli("check")
        self.assertTrue(all(r["state"] == "current" for r in check["data"]["rules"]))
        rerun, code = self.migrate("--apply")
        self.assertEqual((rerun["data"]["operation"], code), ("unchanged", 0))

    def test_every_released_protocol_version_is_recognized(self):
        self.install(self.project, ".claude/skills")
        for name in ("PV-PROTOCOL.v1.md", "PV-PROTOCOL.v2.md", "PV-PROTOCOL.v3.md", "PV-PROTOCOL.v4.md"):
            with self.subTest(version=name):
                path = self.write(self.project / ".claude/rules/PV-PROTOCOL.md", legacy_rule(name) + "\n")
                data = self.migrate()[0]["data"]
                self.assertEqual(data["operation"], "would-change", data["blockers"])
                path.unlink()

    def test_global_rules_switch_only_in_user_scope(self):
        self.install(self.home, ".claude/skills", ".agents/skills")
        (self.home / ".pi").mkdir()
        claude = self.write(self.home / ".claude/rules/PV-PROTOCOL.md", legacy_rule("PV-PROTOCOL.v4.md") + "\n")
        pi = self.write(self.home / ".pi/agent/AGENTS.md",
                        "# Pi\n\n" + legacy_block(PV_BEGIN, PV_END, legacy_rule("PV-PROTOCOL.v4.md")))
        self.legacy_guides()
        self.apply_ok()
        self.assertTrue(claude.exists(), "project migration must not touch global rules")
        self.assertIn(PV_BEGIN, pi.read_text(encoding="utf-8"))
        self.apply_ok("--scope", "user")
        self.assertFalse(claude.exists())
        self.assertEqual((self.home / ".claude/rules" / rules.PROTOCOL_NAME).read_text(encoding="utf-8"),
                         PROTOCOL + "\n")
        text = pi.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Pi\n\n" + rules.BEGIN))
        self.assertNotIn(PV_BEGIN, text)

    def test_global_codex_opencode_and_blog_voice_remnants(self):
        self.install(self.home, ".claude/skills", ".agents/skills")
        (self.home / ".codex").mkdir()
        (self.home / ".config/opencode").mkdir(parents=True)
        blog = self.write(self.home / ".claude/rules/BLOG_VOICE.md", legacy_rule("BLOG_VOICE.md") + "\n")
        codex = self.write(self.home / ".codex/AGENTS.md",
                           legacy_block(BV_BEGIN, BV_END, legacy_rule("BLOG_VOICE.md")) + "\nCodex notes.\n")
        opencode = self.write(self.home / ".config/opencode/AGENTS.md",
                              "OC\n\n" + legacy_block(PV_BEGIN, PV_END, legacy_rule("PV-PROTOCOL.v3.md")))
        self.apply_ok("--scope", "user")
        self.assertFalse(blog.exists())
        self.assertTrue((self.home / ".claude/rules" / rules.PROTOCOL_NAME).is_file())
        for path, unrelated in ((codex, "\nCodex notes.\n"), (opencode, "OC\n\n")):
            text = path.read_text(encoding="utf-8")
            block = rules.find_block(text, rules.BEGIN, rules.END)
            assert block is not None
            self.assertEqual(block.body, PROTOCOL)
            lines = text.splitlines(keepends=True)
            self.assertEqual("".join(lines[:block.begin] + lines[block.end + 1:]), unrelated)
        self.assertEqual(self.migrate("--scope", "user", "--apply")[0]["data"]["operation"], "unchanged")

    def test_existing_current_block_absorbs_legacy_remnant(self):
        self.install(self.project, ".agents/skills")
        current = rules.BEGIN + "\n" + PROTOCOL + "\n" + rules.END + "\n"
        agents = self.write(self.project / "AGENTS.md", "Intro\n\n" + current + "\n"
                            + legacy_block(BV_BEGIN, BV_END, legacy_rule("BLOG_VOICE.md")))
        self.apply_ok()
        self.assertEqual(agents.read_text(encoding="utf-8"), "Intro\n\n" + current + "\n")

    def test_missing_installation_blocks_with_installer_instructions(self):
        self.legacy_guides()
        self.write(self.project / ".claude/rules/PV-PROTOCOL.md", legacy_rule("PV-PROTOCOL.v4.md") + "\n")
        self.write(self.project / "AGENTS.md", legacy_block(PV_BEGIN, PV_END, legacy_rule("PV-PROTOCOL.v4.md")))
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        missing = [d for d in payload["diagnostics"] if d["code"] == "installation-missing"]
        self.assertEqual(len(missing), 2)
        self.assertIn("npx skills add", missing[0]["message"])

    def test_unrecognized_and_malformed_rules_block_before_writes(self):
        self.legacy_guides()
        self.install(self.project, ".claude/skills", ".agents/skills")
        body = legacy_rule("PV-PROTOCOL.v4.md")
        cases = {
            "modified file": ("file", body + "\nLocal edit.\n", "legacy-rule-unrecognized"),
            "modified block": ("agents", legacy_block(PV_BEGIN, PV_END, body + "\nedit"), "legacy-rule-unrecognized"),
            "end only": ("agents", "text\n" + PV_END + "\n", "managed-block-malformed"),
            "begin only": ("agents", PV_BEGIN + "\n" + body + "\n", "managed-block-malformed"),
            "duplicate": ("agents", legacy_block(PV_BEGIN, PV_END, body) * 2, "managed-block-malformed"),
            "nested same": ("agents", PV_BEGIN + "\n" + legacy_block(PV_BEGIN, PV_END, body) + PV_END + "\n",
                            "managed-block-malformed"),
            "nested other": ("agents", PV_BEGIN + "\n" + legacy_block(BV_BEGIN, BV_END, legacy_rule("BLOG_VOICE.md"))
                             + body + "\n" + PV_END + "\n", "managed-block-malformed"),
            "stale new block": ("agents", rules.BEGIN + "\nold\n" + rules.END + "\n"
                                + legacy_block(PV_BEGIN, PV_END, body), "rule-target-conflict"),
        }
        for label, (kind, content, code) in cases.items():
            with self.subTest(case=label):
                target = (self.project / ".claude/rules/PV-PROTOCOL.md" if kind == "file"
                          else self.project / "AGENTS.md")
                self.write(target, content)
                payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
                self.assertIn(code, self.codes(payload))
                self.assertEqual(target.read_text(encoding="utf-8"), content, "content is never truncated")
                target.unlink()


# ====================================================================== conflicts


class ConflictTests(MigrationEnv):
    def test_differing_destination_blocks_with_hashes(self):
        self.legacy_guides()
        self.write(self.new / "VOICE.md", "# Different\n\nvoice\n")
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        conflict = payload["data"]["conflicts"][0]
        self.assertEqual(conflict["code"], "destination-conflict")
        self.assertIn(str(self.new / "VOICE.md"), conflict["paths"])
        self.assertTrue(conflict["expected"] and conflict["actual"] and conflict["expected"] != conflict["actual"])

    def test_differing_existing_config_blocks(self):
        self.legacy_guides()
        self.write(self.legacy / "config.json", json.dumps({"artifacts": {"location": "adjacent"}}))
        self.write(self.new / "config.json", json.dumps({"schema_version": 1}))
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("destination-conflict", self.codes(payload))

    def test_invalid_duplicate_and_unknown_legacy_config_block(self):
        self.legacy_guides()
        cases = {
            '{"guidance": {}, "guidance": {}}': "legacy-config-invalid",
            "{not json": "legacy-config-invalid",
            '{"dialect": "uk"}': "legacy-config-unknown",
            '{"schema_version": 1}': "legacy-config-unknown",
            '{"artifacts": {"location": "elsewhere"}}': "legacy-config-invalid",
            '{"guidance": {"STYLE.md": ["x"]}}': "legacy-config-invalid",
            '{"guidance": {"VOICE.md": "x"}}': "legacy-config-invalid",
        }
        for text, code in cases.items():
            with self.subTest(config=text):
                self.write(self.legacy / "config.json", text)
                payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
                self.assertIn(code, self.codes(payload))

    def test_invalid_new_config_is_an_error(self):
        self.legacy_guides()
        self.write(self.user / "config.json", '{"schema_version": 1, "schema_version": 1}')
        before = self.snapshot()
        payload, code = self.migrate("--apply")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(self.snapshot(), before)

    def test_symlink_escapes_block(self):
        self.legacy_guides()
        outside = self.base / "outside"
        outside.mkdir()
        self.new.symlink_to(outside, target_is_directory=True)
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("destination-symlink", self.codes(payload))
        self.assertEqual(list(outside.iterdir()), [])
        self.new.unlink()

        target = self.write(self.base / "elsewhere/VOICE.md", VOICE)
        (self.legacy / "VOICE.md").unlink()
        (self.legacy / "VOICE.md").symlink_to(target)
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("legacy-symlink", self.codes(payload))

    def test_legacy_symlink_named_in_config_is_an_external_reference(self):
        target = self.write(self.base / "elsewhere/VOICE.md", VOICE)
        self.write(self.legacy / "AUDIENCE.md", AUDIENCE)
        (self.legacy / "linked").mkdir()
        (self.legacy / "linked/VOICE.md").symlink_to(target)
        self.write(self.legacy / "config.json", json.dumps({"guidance": {"VOICE.md": [".prose-voice/linked/VOICE.md"]}}))
        data = self.apply_ok()["data"]
        self.assertEqual(data["translated_config"]["guidance"]["VOICE.md"], [str(target)])
        self.assertFalse((self.new / "linked").exists(), "symlinked trees are not traversed or copied")
        self.assertEqual(Path(self.resolved("VOICE.md")["path"]), target)

    def test_ambiguous_sidecar_and_unsupported_links_block(self):
        self.legacy_guides()
        self.write(self.project / "e.md", "# E\n\n<!-- illus:a -->\n")
        self.write(self.project / "e.illustrations.md", "## illus:a — x\n\nselected: a\n")
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("sidecar-ambiguous", self.codes(payload))
        (self.project / "e.illustrations.md").unlink()
        self.write(self.legacy / "cache/e.illustrations.md",
                   '## illus:a — x\n\n<img src="cand/a.png">\n\nselected: a\n')
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("link-unsupported", self.codes(payload))

    def test_orphaned_sidecar_is_retained_and_reported(self):
        self.legacy_guides()
        orphan = self.write(self.legacy / "cache/gone/post.illustrations.md", "## illus:z — z\n\nselected: z\n")
        data = self.apply_ok()["data"]
        self.assertIn(str(orphan), [r["path"] for r in data["retained"]])
        self.assertIn("sidecar-orphaned", {w["code"] for w in data["warnings"]})

    def test_usage_errors(self):
        for argv in (("--user-dir", "x"), ("--scope", "user", "--project", "."),
                     ("--set", 'artifacts.location="cache"')):
            with self.subTest(argv=argv):
                payload, code = self.migrate(*argv)
                self.assertEqual((payload["status"], code), ("error", 2))


# ====================================================================== interruption


class InterruptionTests(MigrationEnv):
    def fixture(self):
        self.legacy_guides()
        self.write(self.legacy / "dictionary.txt", "Foo\n")
        self.install(self.project, ".claude/skills")
        self.write(self.project / ".claude/rules/PV-PROTOCOL.md", legacy_rule("PV-PROTOCOL.v4.md") + "\n")

    def interrupt(self, point: str, nth: int = 1, phase: str | None = None):
        seen = {"n": 0}

        def hook(where, action):
            if where == point and (phase is None or (action and action["phase"] == phase)):
                seen["n"] += 1
                if seen["n"] == nth:
                    raise migration.Interrupted(point)

        migration.FAULT_HOOK = hook
        payload, code = self.migrate("--apply")
        migration.FAULT_HOOK = None
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertIn("migration-interrupted", self.codes(payload))
        manifest = json.loads(self.manifests()[0].read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "in-progress")
        return manifest

    def resume_ok(self):
        payload, code = self.migrate("--apply")
        self.assertEqual((payload["data"]["operation"], code), ("applied", 0), payload["diagnostics"])
        self.assertTrue(payload["data"].get("resumed"))
        self.assertEqual(len(self.manifests()), 1, "resume must not create another manifest")
        mdir = self.manifests()[0].parent
        self.assertEqual(len(list((mdir / "backups").iterdir())), 1, "no repeated backups")
        self.assertEqual((self.new / "VOICE.md").read_text(encoding="utf-8"), VOICE)
        self.assertFalse((self.project / ".claude/rules/PV-PROTOCOL.md").exists())
        rerun, code = self.migrate("--apply")
        self.assertEqual((rerun["data"]["operation"], code), ("unchanged", 0))

    def test_resume_before_a_replacement(self):
        self.fixture()
        self.interrupt("before-replace", nth=2)
        self.assertTrue((self.new / "VOICE.md").exists())
        self.assertFalse((self.new / "AUDIENCE.md").exists())
        preview = self.assert_preview_unchanged()
        self.assertTrue(preview["data"]["resumed"])
        self.resume_ok()

    def test_resume_after_replacement_before_completion_record(self):
        self.fixture()
        manifest = self.interrupt("after-replace", nth=2)
        started = [a for a in manifest["actions"] if a["state"] == "started"]
        self.assertEqual(len(started), 1)
        self.assertTrue(Path(started[0]["path"]).exists(), "replacement happened before the crash")
        self.resume_ok()

    def test_resume_before_rule_activation(self):
        self.fixture()
        manifest = self.interrupt("before-rules")
        self.assertEqual(manifest["verification"]["state"], "passed")
        self.assertTrue((self.project / ".claude/rules/PV-PROTOCOL.md").exists(), "rules activate last")
        self.assertFalse((self.project / ".claude/rules" / rules.PROTOCOL_NAME).exists())
        self.resume_ok()

    def test_resume_mid_rule_phase(self):
        self.fixture()
        self.interrupt("after-replace", phase="rule")
        self.resume_ok()

    def test_intervening_edit_blocks_with_file_and_manifest(self):
        self.fixture()
        self.interrupt("before-replace", nth=2)
        self.write(self.new / "VOICE.md", "# Edited after the crash\n")
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        conflict = next(d for d in payload["diagnostics"] if d["code"] == "resume-conflict")
        self.assertIn(str(self.new / "VOICE.md"), conflict["paths"])
        self.assertIn(str(self.manifests()[0]), conflict["paths"])

    def test_changed_input_blocks_resume(self):
        self.fixture()
        self.interrupt("before-replace", nth=2)
        self.write(self.legacy / "AUDIENCE.md", "# Audience changed\n")
        payload = self.assert_preview_unchanged("--apply", operation="blocked", code=1)
        self.assertIn("resume-input-changed", self.codes(payload))


# ====================================================================== runtime isolation


class RuntimeIsolationTests(MigrationEnv):
    def test_runtime_ignores_retained_legacy_data_after_migration(self):
        self.legacy_guides()
        self.write(self.legacy / "dictionary.txt", "Legacyword\n")
        self.write(self.legacy_user / "AUDIENCE.md", "# User audience\n\nx\n")
        self.apply_ok()
        self.write(self.legacy / "VOICE.md", "# Changed legacy voice\n")
        self.write(self.legacy / "dictionary.txt", "Onlylegacy\n")
        payload, _ = self.run_cli("resolve")
        voice = payload["data"]["guidance"]["VOICE.md"]
        self.assertEqual(Path(voice["resolved"]["path"]), self.new / "VOICE.md")
        self.assertFalse(any(".prose-voice" in t["path"] for t in voice["tried"]))
        policy = self.policy()
        self.assertIn("Legacyword", policy["words"])
        self.assertNotIn("Onlylegacy", policy["words"])
        self.assertFalse(any(".prose-voice" in p for p in policy["sources"]["dictionary"]))
        config, _ = self.run_cli("config")
        self.assertNotIn(".prose-voice", json.dumps(config["data"]))


if __name__ == "__main__":
    unittest.main()
