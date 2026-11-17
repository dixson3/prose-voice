"""Regression checks for optional visual guidance and Markdown essay readiness.

Run with: uv run python -m unittest discover -s tests
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import config as cfg
from prosevoice_lib import essay as ready
from prosevoice_lib import rules
from prosevoice_lib.errors import ConfigError


class NarrativeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.root = base / "project"
        self.home = base / "home"
        self.user = base / "xdg/prosevoice"
        self.root.mkdir()
        self.home.mkdir()
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        env = patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(base / "xdg"),
                                      "GIT_CEILING_DIRECTORIES": str(base)})
        env.start()
        self.addCleanup(env.stop)

    def write(self, relative, text, base=None):
        path = (base or self.root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def config(self):
        return cfg.load_config(cwd=self.root)

    def test_optional_guidance_does_not_block_or_get_seeded(self):
        self.write(".prosevoice/VOICE.md", "# Voice\nPlain and direct.")
        self.write(".prosevoice/AUDIENCE.md", "# Audience\nCurious readers.")
        with patch.object(rules.shutil, "which", return_value="/tool"):
            report = rules.check(self.config(), self.home)
        self.assertTrue(report["ready"])
        self.assertIsNone(report["guidance"]["ILLUSTRATIONS.md"]["resolved"])
        seeded = cfg.init("project", cwd=self.root)
        self.assertEqual(len([p for p in seeded["kept"] if p.endswith(".md")]), 2)
        self.assertFalse((self.root / ".prosevoice/ILLUSTRATIONS.md").exists())

    def test_visual_guidance_uses_independent_project_global_fallback(self):
        global_path = self.write("ILLUSTRATIONS.md", "Use simple line drawings.", self.user)
        self.write(".prosevoice/VOICE.md", "Project voice")
        self.write("AUDIENCE.md", "Global audience", self.user)
        resolved = cfg.resolve_guidance(self.config())
        self.assertEqual(resolved["ILLUSTRATIONS.md"]["resolved"]["path"], str(global_path))
        self.assertEqual(resolved["AUDIENCE.md"]["resolved"]["level"], "user")
        local = self.write(".prosevoice/ILLUSTRATIONS.md", "Project palette")
        self.assertEqual(cfg.resolve_guidance(self.config())["ILLUSTRATIONS.md"]["resolved"]["path"], str(local))
        local.write_text("<!-- pv-template: unfilled -->", encoding="utf-8")
        self.assertEqual(cfg.resolve_guidance(self.config())["ILLUSTRATIONS.md"]["resolved"]["level"], "user")

    def test_plain_multi_part_essays_need_no_hero_or_section_images(self):
        config = self.config()
        parts = [self.write("opening.md", "# Why\n\n## Mechanism\nAn explanation."),
                 self.write("chapters/evidence.md", "## Evidence\nSupporting evidence.")]
        self.assertTrue(all(ready.check_image(config, p)["resolved"] for p in parts))
        self.assertTrue(ready.check_source(parts)["resolved"])
        self.assertFalse(any(ready.sidecar_path(config, p).exists() for p in parts))

    def test_only_anchored_visuals_need_resolved_selections(self):
        config = self.config()
        essay = self.write("explanation.md", "## Process\nSome prose.\n<!-- illus:flow1 -->\nMore prose.")
        self.assertFalse(ready.check_image(config, essay)["resolved"])
        sidecar = ready.sidecar_path(config, essay)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text("## illus:flow1\nselected: unresolved\n", encoding="utf-8")
        self.assertFalse(ready.check_image(config, essay)["resolved"])
        for selection in ("diagramSvg", "no-image"):
            sidecar.write_text(f"## illus:flow1\nselected: {selection}\n## illus:old\nselected: unresolved\n",
                               encoding="utf-8")
            self.assertTrue(ready.check_image(config, essay)["resolved"])
        essay.write_text("## Process\nNo longer needs a visual.", encoding="utf-8")
        self.assertTrue(ready.check_image(config, essay)["resolved"])

    def test_configured_guidance_precedes_standard_locations(self):
        self.write(".prosevoice/config.json", '{"schema_version":1,"guidance":{"AUDIENCE.md":["guides/reader.md"]}}')
        custom = self.write("guides/reader.md", "Specialized audience")
        self.write(".prosevoice/AUDIENCE.md", "Default audience")
        self.assertEqual(cfg.resolve_guidance(self.config())["AUDIENCE.md"]["resolved"]["path"], str(custom))
        custom.unlink()
        self.assertEqual(cfg.resolve_guidance(self.config())["AUDIENCE.md"]["resolved"]["level"], "project")

    def test_cache_paths_are_isolated_ignored_and_idempotent(self):
        essay = self.write("chapters/one.md", "Text")
        other = self.write("appendix/one.md", "More text")
        self.write(".prosevoice/.gitignore", "/scratch/\n")
        voice = self.write(".prosevoice/VOICE.md", "Keep the voice guidance")
        config_file = self.write(".prosevoice/config.json", '{"schema_version":1}')
        config = self.config()
        paths = cfg.prepare_artifacts(config, essay)["paths"]
        self.assertNotEqual(paths, cfg.artifact_paths(config, other))
        self.assertEqual(paths["illustrations"], self.root / ".prosevoice/cache/chapters/one.illustrations.md")
        paths["curmudgeon"].write_text("Review", encoding="utf-8")
        cfg.prepare_artifacts(config, essay)
        self.assertEqual((self.root / ".prosevoice/.gitignore").read_text(), "/scratch/\n/cache/\n")
        self.assertFalse((self.root / ".pv").exists())
        self.assertEqual(voice.read_text(), "Keep the voice guidance")
        versionable = subprocess.run(["git", "-C", str(self.root), "check-ignore", str(voice), str(config_file)],
                                     capture_output=True, check=False)
        self.assertEqual(versionable.returncode, 1)
        ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", str(paths["curmudgeon"])],
                                 capture_output=True, check=False)
        self.assertEqual(ignored.returncode, 0)

    def test_adjacent_mode_and_invalid_config(self):
        essay = self.write("essay.md", "<!-- illus:one -->")
        config_file = self.write(".prosevoice/config.json", '{"schema_version":1,"artifacts":{"location":"adjacent"}}')
        config = self.config()
        self.assertEqual(ready.sidecar_path(config, essay), self.root / "essay.illustrations.md")
        self.write("essay.illustrations.md", "## illus:one\nselected: oneSvg\n")
        self.assertTrue(ready.check_image(config, essay)["resolved"])
        config_file.write_text('{"schema_version":1,"artifacts":{"location":"typo"}}', encoding="utf-8")
        with self.assertRaises(ConfigError):
            self.config()

    def test_shared_global_install_targets_opencode_once(self):
        (self.home / ".agents/skills/prosevoice").mkdir(parents=True)
        (self.home / ".config/opencode").mkdir(parents=True)
        targets = rules.rule_targets(self.config(), self.home)
        self.assertEqual([t["harness"] for t in targets], ["opencode"])
        (self.home / ".config/opencode/skills/prosevoice").mkdir(parents=True)
        self.assertEqual(len(rules.rule_targets(self.config(), self.home)), 1)

    def test_source_flags_still_block_any_part(self):
        first = self.write("one.md", "An explanation.")
        second = self.write("two.md", "---\nstatus: ready\n---\nClaim [needs-source]\n")
        report = ready.check_source([first, second])
        self.assertFalse(report["resolved"])
        self.assertEqual(report["locations"][0]["line"], 4)


if __name__ == "__main__":
    unittest.main()
