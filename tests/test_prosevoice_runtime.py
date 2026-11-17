"""Consolidated runtime: artifacts, READY, premise, policy, lint/extract and launcher isolation.

Run with uv run python -m unittest discover -s tests.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import cli
from prosevoice_lib import policy as harper
from prosevoice_lib.config import ARTIFACT_KINDS

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/prosevoice"
LAUNCHER = SKILL / "scripts/prosevoice.py"
KINDS = ("curmudgeon", "steelman", "illustrations", "draft", "review", "ready",
         "copyedit", "provenance", "fact-check", "footnoter", "red-team", "cold-read")


class RuntimeEnv(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.user = self.base / "xdg/prosevoice"
        self.project = self.base / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.base / "xdg"),
                    "GIT_CEILING_DIRECTORIES": str(self.base)}
        patcher = patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text) -> Path:
        path = Path(path)
        path = path if path.is_absolute() else self.project / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *argv, cwd=None):
        old = Path.cwd()
        os.chdir(cwd or self.project)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main([str(a) for a in argv])
        finally:
            os.chdir(old)
        return json.loads(out.getvalue()), code

    def launch(self, launcher, *argv, cwd=None):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        proc = subprocess.run([sys.executable, "-I", str(launcher), *map(str, argv)],
                              cwd=cwd or self.project, env=env, capture_output=True, text=True, check=False)
        return json.loads(proc.stdout), proc.returncode


class ArtifactRoutingTests(RuntimeEnv):
    def test_twelve_kinds_are_the_contract_kinds(self):
        self.assertEqual(ARTIFACT_KINDS, KINDS)

    def test_cache_mode_routes_all_kinds_with_nested_directories(self):
        for relative in ("essay.md", "posts/2026/deep/essay.md"):
            with self.subTest(relative=relative):
                payload, code = self.run_cli("artifacts", relative)
                self.assertEqual(code, 0)
                parent = (self.project / ".prosevoice/cache" / relative).parent
                self.assertEqual(payload["data"]["paths"],
                                 {k: str(parent / f"essay.{k}.md") for k in KINDS})
                for kind in KINDS:
                    one, _ = self.run_cli("artifacts", relative, "--kind", kind)
                    self.assertEqual(one["data"]["paths"], {kind: str(parent / f"essay.{kind}.md")})
        self.assertFalse((self.project / ".prosevoice").exists())

    def test_same_stem_in_different_directories_does_not_collide(self):
        one, _ = self.run_cli("artifacts", "a/one.md")
        two, _ = self.run_cli("artifacts", "b/one.md")
        self.assertTrue(set(one["data"]["paths"].values()).isdisjoint(two["data"]["paths"].values()))

    def test_adjacent_mode_routes_all_kinds_beside_essay(self):
        for relative in ("essay.md", "posts/2026/essay.md"):
            with self.subTest(relative=relative):
                payload, code = self.run_cli("artifacts", relative, "--set", 'artifacts.location="adjacent"')
                self.assertEqual(code, 0)
                parent = (self.project / relative).parent
                self.assertEqual(payload["data"]["paths"], {k: str(parent / f"essay.{k}.md") for k in KINDS})
        payload, _ = self.run_cli("artifacts", "posts/essay.md", "--apply",
                                  "--set", 'artifacts.location="adjacent"')
        self.assertFalse(payload["data"]["ignore_updated"])
        self.assertFalse((self.project / ".prosevoice/.gitignore").exists())

    def test_essay_in_other_git_project_uses_its_own_project(self):
        other = self.base / "other"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        payload, code = self.run_cli("artifacts", other / "x/e.md")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["project"], str(other))
        self.assertEqual(payload["data"]["project_selection"], "essay-git")
        self.assertEqual(payload["data"]["paths"]["draft"], str(other / ".prosevoice/cache/x/e.draft.md"))
        payload, code = self.run_cli("artifacts", other / "x/e.md", "--project", self.project)
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "essay-outside-project")


class NonGitEssayRoutingTests(RuntimeEnv):
    """An essay outside any Git repository, without --project, keeps its cache beside it."""

    def setUp(self):
        super().setUp()
        self.essays = self.base / "plain/notes/essays"  # GIT_CEILING_DIRECTORIES keeps this non-Git
        self.essay = self.write(self.essays / "queues.md", "Intro\n<!-- illus:flow1 -->\nMore.\n")
        self.unrelated = self.base / "unrelated"
        self.unrelated.mkdir()
        self.cache = self.essays / ".prosevoice/cache"

    def cwds(self):
        return {"unrelated": self.unrelated, "ancestor": self.base / "plain"}

    def test_artifacts_route_beside_the_essay_from_any_directory(self):
        for label, cwd in self.cwds().items():
            with self.subTest(cwd=label):
                payload, code = self.launch(LAUNCHER, "artifacts", self.essay, cwd=cwd)
                self.assertEqual((payload["status"], code), ("ok", 0), payload)
                self.assertEqual(payload["data"]["project"], str(self.essays))
                self.assertEqual(payload["data"]["project_selection"], "essay-dir")
                self.assertEqual(payload["data"]["paths"], {k: str(self.cache / f"queues.{k}.md") for k in KINDS})
                self.assertEqual(payload["data"]["paths"]["illustrations"],
                                 str(self.essays / ".prosevoice/cache/queues.illustrations.md"))
        self.assertFalse((self.essays / ".prosevoice").exists())
        self.assertFalse((self.base / "plain/.prosevoice").exists())
        self.assertFalse((self.unrelated / ".prosevoice").exists())

    def test_ready_evaluates_the_essay_with_the_adjacent_cache_sidecar(self):
        for label, cwd in self.cwds().items():
            with self.subTest(cwd=label, sidecar="absent"):
                payload, code = self.launch(LAUNCHER, "ready", self.essay, cwd=cwd)
                self.assertEqual((payload["status"], code), ("blocked", 1), payload)
                image = payload["data"]["image"][str(self.essay)]
                self.assertEqual(image["sidecar"], str(self.cache / "queues.illustrations.md"))
                self.assertEqual(image["blockers"], ["illus:flow1: no sidecar block"])
        self.write(self.cache / "queues.illustrations.md", "## illus:flow1\nselected: flowSvg\n")
        for label, cwd in self.cwds().items():
            with self.subTest(cwd=label, sidecar="selected"):
                payload, code = self.launch(LAUNCHER, "ready", self.essay, cwd=cwd)
                self.assertEqual((payload["status"], code), ("ok", 0), payload)
                image = payload["data"]["image"][str(self.essay)]
                self.assertTrue(image["sidecar_present"] and image["resolved"])

    def test_explicit_project_is_unchanged(self):
        payload, code = self.run_cli("artifacts", self.essay, "--project", self.project, cwd=self.unrelated)
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "essay-outside-project")
        payload, code = self.run_cli("artifacts", self.essay, "--project", self.base / "plain", "--kind", "draft",
                                     cwd=self.unrelated)
        self.assertEqual((code, payload["data"]["project_selection"]), (0, "explicit"))
        self.assertEqual(payload["data"]["paths"],
                         {"draft": str(self.base / "plain/.prosevoice/cache/notes/essays/queues.draft.md")})
        payload, code = self.run_cli("artifacts", self.essay, "--project", self.base / "missing", cwd=self.unrelated)
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "project-missing")
        payload, code = self.run_cli("ready", self.essay, "--project", self.base / "plain", cwd=self.unrelated)
        self.assertEqual(payload["data"]["image"][str(self.essay)]["sidecar"],
                         str(self.base / "plain/.prosevoice/cache/notes/essays/queues.illustrations.md"))

    def test_essay_directory_project_config_applies_and_cli_guidance_stays_cwd_anchored(self):
        from prosevoice_lib import config as cfg
        self.write(self.essays / ".prosevoice/config.json",
                   '{"schema_version": 1, "guidance": {"AUDIENCE.md": ["aud.md"]}}')
        base = cfg.load_config(overrides=['guidance.VOICE.md=["voice.md"]'], cwd=self.unrelated)
        selected = cfg.config_for_essay(base, self.essay)
        self.assertEqual((selected.project_root, selected.project_selection), (self.essays, "essay-dir"))
        self.assertEqual(selected.guidance_candidates("VOICE.md"), [self.unrelated / "voice.md"])
        self.assertEqual(selected.guidance_candidates("AUDIENCE.md"), [self.essays / "aud.md"])
        self.assertEqual(selected.cwd, self.unrelated)
        self.write(self.essays / ".prosevoice/config.json",
                   '{"schema_version": 1, "artifacts": {"location": "adjacent"}}')
        payload, code = self.run_cli("artifacts", self.essay, "--kind", "draft", cwd=self.unrelated)
        self.assertEqual((code, payload["data"]["location"]), (0, "adjacent"))
        self.assertEqual(payload["data"]["paths"], {"draft": str(self.essays / "queues.draft.md")})

    def test_not_yet_created_essay_directory_resolves_and_applies(self):
        future = self.base / "plain/new/deeper/draft.md"
        payload, code = self.run_cli("artifacts", future, "--kind", "illustrations", cwd=self.unrelated)
        self.assertEqual((payload["status"], code), ("ok", 0), payload)
        self.assertEqual(payload["data"]["paths"],
                         {"illustrations": str(future.parent / ".prosevoice/cache/draft.illustrations.md")})
        self.assertFalse(future.parent.exists())
        payload, code = self.run_cli("artifacts", future, "--apply", cwd=self.unrelated)
        self.assertEqual((payload["status"], code), ("ok", 0), payload)
        self.assertTrue(payload["data"]["ignore_updated"])
        self.assertTrue((future.parent / ".prosevoice/cache").is_dir())
        self.assertEqual((future.parent / ".prosevoice/.gitignore").read_text(encoding="utf-8"), "/cache/\n")
        self.assertFalse(future.exists())
        self.assertFalse((self.base / "plain/.prosevoice").exists())
        payload, code = self.run_cli("artifacts", future, "--project", self.base / "plain/absent", cwd=self.unrelated)
        self.assertEqual(payload["diagnostics"][0]["code"], "project-missing")


class ReadyTests(RuntimeEnv):
    def sidecar(self, essay, text, adjacent=False):
        stem = Path(essay).stem
        rel = Path(essay).parent
        base = self.project / rel if adjacent else self.project / ".prosevoice/cache" / rel
        return self.write(base / f"{stem}.illustrations.md", text)

    def test_unillustrated_multipart_essay_is_ready(self):
        self.write("one.md", "# Why\nPlain prose.\n")
        self.write("parts/two.md", "## More\nMore prose.\n")
        payload, code = self.run_cli("ready", "one.md", "parts/two.md")
        self.assertEqual((payload["status"], code), ("ok", 0))
        self.assertEqual(list(payload["data"]["image"]),
                         [str(self.project / "one.md"), str(self.project / "parts/two.md")])
        self.assertTrue(all(v["planned_visual_count"] == 0 for v in payload["data"]["image"].values()))

    def test_active_anchor_visual_states(self):
        self.write("posts/e.md", "Intro\n<!-- illus:flow1 -->\nMore.\n")
        payload, code = self.run_cli("ready", "posts/e.md")
        self.assertEqual((payload["status"], code), ("blocked", 1))
        self.assertEqual(payload["data"]["image"][str(self.project / "posts/e.md")]["blockers"],
                         ["illus:flow1: no sidecar block"])
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["visual-unresolved"])
        cases = [("## illus:flow1\nselected: unresolved\n", 1),
                 ("## illus:flow1\npurpose: x\n", 1),
                 ("## illus:flow1\nselected: flowSvg\n", 0),
                 ("## illus:flow1\nselected: no-image\n## illus:stale\nselected: unresolved\n", 0)]
        for text, expected in cases:
            with self.subTest(text=text):
                self.sidecar("posts/e.md", text)
                _, code = self.run_cli("ready", "posts/e.md")
                self.assertEqual(code, expected)

    def test_anchor_in_frontmatter_or_removed_anchor_creates_no_obligation(self):
        self.write("e.md", "---\nnote: <!-- illus:fm -->\n---\nBody.\n")
        _, code = self.run_cli("ready", "e.md")
        self.assertEqual(code, 0)
        self.sidecar("e.md", "## illus:gone\nselected: unresolved\n")
        _, code = self.run_cli("ready", "e.md")
        self.assertEqual(code, 0)

    def test_adjacent_sidecar_is_used_in_adjacent_mode(self):
        self.write(".prosevoice/config.json", '{"schema_version": 1, "artifacts": {"location": "adjacent"}}')
        self.write("e.md", "<!-- illus:a1 -->\n")
        self.sidecar("e.md", "## illus:a1\nselected: unresolved\n")  # cache copy is ignored
        self.sidecar("e.md", "## illus:a1\nselected: aPng\n", adjacent=True)
        payload, code = self.run_cli("ready", "e.md")
        self.assertEqual(code, 0, payload)

    def test_needs_source_in_any_part_blocks_with_line(self):
        self.write("one.md", "Clean.\n")
        self.write("two.md", "---\nthesis: [needs-source] in frontmatter is ignored\n---\nA\nClaim [needs-source]\n")
        payload, code = self.run_cli("ready", "one.md", "two.md")
        self.assertEqual((payload["status"], code), ("blocked", 1))
        self.assertEqual(payload["data"]["source"]["locations"],
                         [{"file": str(self.project / "two.md"), "line": 5, "text": "Claim [needs-source]"}])
        self.assertEqual([d["code"] for d in payload["diagnostics"]], ["needs-source"])

    def test_ready_reports_mechanical_limitations_in_every_outcome(self):
        self.write("clear.md", "Plain prose.\n")
        self.write("flagged.md", "Claim [needs-source]\n")
        for essay, expected in (("clear.md", ("ok", 0)), ("flagged.md", ("blocked", 1))):
            with self.subTest(essay=essay):
                payload, code = self.run_cli("ready", essay)
                self.assertEqual((payload["status"], code), expected)
                limits = payload["data"]["limitations"]
                self.assertTrue(limits and all(isinstance(x, str) and x for x in limits))
                self.assertTrue(any("[needs-source]" in x for x in limits))
                self.assertTrue(any("illus:ID" in x for x in limits))

    def test_missing_part_is_an_error(self):
        payload, code = self.run_cli("ready", "absent.md")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "essay-missing")


class PremiseTests(RuntimeEnv):
    @staticmethod
    def digest(normalized):
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def fingerprint(self, text, name="p.md"):
        self.write(name, text)
        payload, code = self.run_cli("premise", name)
        self.assertEqual(code, 0)
        return payload["data"]["parts"][0]

    def test_thesis_field_exact_fingerprint(self):
        part = self.fingerprint('---\ntitle: The Case\nthesis: "Plans, fail!"\n---\nBody.\n')
        self.assertEqual(part["fingerprint"], "d03cd0013a34a7a2")
        self.assertEqual(part["fingerprint"], self.digest("the case plans fail"))
        self.assertEqual((part["region"], part["title"], part["normalized_len"]),
                         ("thesis-field", "The Case", "19"))

    def test_first_paragraph_fallback_skips_headings_images_comments(self):
        text = ("---\ntitle: 'Why It Works'\n---\n\n# Heading\n![img](a.png)\n<!-- illus:x -->\n"
                "First line,\nsecond LINE.\n\nLater paragraph.\n")
        part = self.fingerprint(text)
        self.assertEqual(part["region"], "first-body-paragraph")
        self.assertEqual(part["fingerprint"], self.digest("why it works first line second line"))

    def test_block_scalar_thesis_and_body_edits(self):
        base = "---\ntitle: T\nthesis: >-\n  Folded\n  thesis.\n---\n"
        first = self.fingerprint(base + "Body one.\n")
        self.assertEqual(first["fingerprint"], self.digest("t folded thesis"))
        second = self.fingerprint(base + "Entirely different body.\n")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        changed = self.fingerprint(base.replace("Folded", "Other") + "Body one.\n")
        self.assertNotEqual(first["fingerprint"], changed["fingerprint"])
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{16}$")

    def test_multipart_parts_keep_order(self):
        self.write("b.md", "---\ntitle: B\n---\nBee.\n")
        self.write("a.md", "---\ntitle: A\n---\nAy.\n")
        payload, _ = self.run_cli("premise", "b.md", "a.md")
        self.assertEqual([p["title"] for p in payload["data"]["parts"]], ["B", "A"])


class PolicyTests(RuntimeEnv):
    def test_policy_union_and_per_project_isolation(self):
        self.write(self.user / "dictionary.txt", "UserWord\n")
        self.write(self.user / "ignore-rules.txt", "UserRule\n")
        other = self.base / "other"
        for root, word in ((self.project, "One"), (other, "Two")):
            root.mkdir(exist_ok=True)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            self.write(root / ".prosevoice/dictionary.txt", f"{word}Word\n")
            self.write(root / ".prosevoice/ignore-rules.txt", f"{word}Rule\n")
            self.write(root / "ch/e.md", "Text\n")
        self.write(self.project / "ch/.harper-words", "LocalWord\n")
        explicit = self.write(self.base / "extra.txt", "ExtraWord\n")
        bundled = (SKILL / "harper/dictionary.txt").read_text(encoding="utf-8")
        results = {}
        for root in (self.project, other):
            out = self.base / f"{root.name}.dict"
            payload, code = self.run_cli("policy", root / "ch/e.md", "--out", out, "--user-dict", explicit,
                                         cwd=self.base)
            self.assertEqual(code, 0)
            results[root.name] = (set(out.read_text().splitlines()), payload["data"])
        one, two = results["project"], results["other"]
        self.assertTrue({"UserWord", "OneWord", "LocalWord", "ExtraWord"} <= one[0])
        self.assertTrue({"UserWord", "TwoWord", "ExtraWord"} <= two[0])
        self.assertFalse({"OneWord", "LocalWord"} & two[0])
        self.assertIn("TwoRule", two[1]["ignore_rule_list"])
        self.assertNotIn("OneRule", two[1]["ignore_rule_list"])
        self.assertIn(str(SKILL / "harper/dictionary.txt"), one[1]["sources"]["dictionary"])
        self.assertTrue(any(w in one[0] for w in bundled.splitlines() if w and not w.startswith("#")))

    def test_explicit_project_applies_to_every_essay(self):
        other = self.base / "other"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        self.write(other / ".prosevoice/dictionary.txt", "OtherWord\n")
        self.write(self.project / ".prosevoice/dictionary.txt", "MainWord\n")
        essay = self.write(other / "e.md", "x\n")
        out = self.base / "d.txt"
        payload, _ = self.run_cli("policy", essay, "--out", out, "--project", self.project)
        words = set(out.read_text().splitlines())
        self.assertIn("MainWord", words)
        self.assertNotIn("OtherWord", words)
        self.assertTrue(payload["data"]["sources"]["dictionary"])

    def test_temp_dictionary_is_reported_and_unreadable_input_errors(self):
        payload, code = self.run_cli("policy")
        self.assertEqual(code, 0)
        self.assertTrue(payload["data"]["dictionary_is_temporary"])
        Path(payload["data"]["dictionary"]).unlink()
        (self.project / ".prosevoice/dictionary.txt").mkdir(parents=True)
        payload, code = self.run_cli("policy")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.write(self.base / "bad.txt", "")
        (self.base / "bad.txt").write_bytes(b"\xff\xfe\x00bad")
        shutil.rmtree(self.project / ".prosevoice")
        payload, code = self.run_cli("policy", "--user-dict", self.base / "bad.txt")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "policy-unreadable")


class LintAndExtractTests(RuntimeEnv):
    def test_extract_back_map_offsets_and_regions(self):
        essay = self.write("e.md", '---\ntitle: "Héllo wrold"\ndek: >-\n  folded line\n---\n'
                           'Body é ![An alt txt](a.png "A titel") end\n\n```\nplain fence prose\n```\n\n'
                           "```python\n# a coment here\nx = 1\n```\n")
        out = self.base / "snippets.md"
        payload, code = self.run_cli("extract", "e.md", "--out-md", out)
        self.assertEqual(code, 0)
        data = payload["data"]
        self.assertEqual(out.read_text(encoding="utf-8").splitlines(),
                         ["Héllo wrold", "folded line", "An alt txt", "A titel", "plain fence prose", "a coment here"])
        expected = [(2, 8, "frontmatter:title", False), (3, 0, "frontmatter:dek", True),
                    (6, 9, "image-alt", False), (6, 28, "image-title", False),
                    (9, 0, "fenced-prose", False), (13, 2, "fenced-comment", False)]
        got = [(m["orig_line"], m["orig_col_offset"], m["region"], m["coarse"]) for m in data["map"].values()]
        self.assertEqual(got, expected)
        self.assertTrue(all(m["orig_path"] == "e.md" for m in data["map"].values()))
        source_line = essay.read_text(encoding="utf-8").splitlines()[5]
        self.assertEqual(source_line[9:9 + len("An alt txt")], "An alt txt")
        payload, _ = self.run_cli("extract", "e.md")
        self.assertTrue(payload["data"]["temp_is_temporary"])
        Path(payload["data"]["temp_md"]).unlink()

    def test_lint_spelling_restrictions_and_offset_guard(self):
        doc = self.write("doc.md", "é 🐈 alot Alot\n")
        lints = [
            {"kind": "Spelling", "rule": "SpellCheck", "priority": 63, "span": {"char_start": 4, "char_end": 8},
             "line": 1, "column": 5, "matched_text": "alot", "message": "typo",
             "suggestions": ["Replace with: “a lot”"]},
            {"kind": "Spelling", "rule": "SpellCheck", "priority": 63, "span": {"char_start": 9, "char_end": 13},
             "line": 1, "column": 10, "matched_text": "Alot", "message": "typo",
             "suggestions": ["Replace with: “A lot”"]},
            {"kind": "Spelling", "rule": "SpellCheck", "priority": 63, "span": {"char_start": 3, "char_end": 7},
             "line": 1, "column": 4, "matched_text": "alot", "message": "typo",
             "suggestions": ["Replace with: “a lot”"]},
        ]
        with patch.object(harper.shutil, "which", return_value="harper"), \
                patch.object(harper, "harper_version", return_value="harper 1"), \
                patch.object(harper, "lint_file", return_value=lints):
            payload, code = self.run_cli("lint", doc)
        self.assertEqual(code, 0)
        findings = {(f["char_start"], f["bucket"], f["fixable"], f["offset_guard"])
                    for f in payload["data"]["files"][0]["findings"]}
        self.assertEqual(findings, {(4, "spelling", True, True), (9, "name", False, True),
                                    (3, "spelling", False, False)})
        self.assertEqual(doc.read_text(encoding="utf-8"), "é 🐈 alot Alot\n")

    def test_lint_errors_use_envelope(self):
        self.write("doc.md", "x\n")
        with patch.object(harper.shutil, "which", return_value="harper"), \
                patch.object(harper, "harper_version", return_value="harper 1"), \
                patch.object(harper.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 1, "not json", "boom")):
            payload, code = self.run_cli("lint", "doc.md")
        self.assertEqual((payload["status"], code, payload["diagnostics"][0]["code"]),
                         ("error", 2, "harper-failed"))
        payload, code = self.run_cli("lint", "doc.md", "--dialect", "xx")
        self.assertEqual((code, payload["diagnostics"][0]["code"]), (2, "usage"))


class IsolatedLauncherTests(RuntimeEnv):
    def test_copied_skill_runs_ready_policy_lint_and_rule_without_siblings(self):
        copy = self.base / "installed/skills/prosevoice"
        shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
        self.assertEqual(sorted(p.name for p in copy.parent.iterdir()), ["prosevoice"])
        launcher = copy / "scripts/prosevoice.py"
        self.write("posts/e.md", "Text\n<!-- illus:a1 -->\n")
        payload, code = self.launch(launcher, "ready", "posts/e.md")
        self.assertEqual((payload["status"], code), ("blocked", 1))
        self.sidecar = self.write(".prosevoice/cache/posts/e.illustrations.md", "## illus:a1\nselected: no-image\n")
        payload, code = self.launch(launcher, "ready", "posts/e.md")
        self.assertEqual((payload["status"], code), ("ok", 0))
        out = self.base / "d.txt"
        payload, code = self.launch(launcher, "policy", "posts/e.md", "--out", out)
        self.assertEqual(code, 0)
        self.assertIn(str(copy / "harper/dictionary.txt"), payload["data"]["sources"]["dictionary"])
        self.assertIn(str(copy / "harper/ignore-rules.txt"), payload["data"]["sources"]["ignore_rules"])
        payload, code = self.launch(launcher, "premise", "posts/e.md")
        self.assertEqual(code, 0)
        payload, code = self.launch(launcher, "check")
        self.assertIn(code, (0, 1))
        self.assertEqual(payload["command"], "check")
        payload, code = self.launch(launcher, "version", cwd=self.base)
        self.assertEqual(payload["data"]["skill_root"], str(copy))

    def test_package_has_no_legacy_imports_or_paths(self):
        lib = SKILL / "scripts/prosevoice_lib"
        for path in lib.glob("*.py"):
            if path.name == "migration.py":
                continue  # the only module allowed to read legacy data and rule identities
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("pv-preflight", text)
                self.assertNotIn("pv_config", text)
                self.assertNotIn("importlib.util", text)
                self.assertNotIn('".prose-voice', text)
                self.assertNotIn("Path.home() / \".prose-voice", text)


if __name__ == "__main__":
    unittest.main()
