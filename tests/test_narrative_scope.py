"""Regression checks for optional visual guidance and Markdown essay readiness.

Run with: uv run python -m unittest discover -s tests
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/pv-preflight/scripts"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load("preflight", "skills/pv-preflight/scripts/preflight.py")
ready = load("ready", "skills/pv-prosevoice/scripts/ready_preconditions.py")


class NarrativeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "project"
        self.home = Path(self.temp.name).resolve() / "home"
        self.root.mkdir()
        self.home.mkdir()
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def write(self, relative, text, base=None):
        path = (base or self.root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_optional_guidance_does_not_block_or_get_seeded(self):
        self.write(".prose-voice/VOICE.md", "# Voice\nPlain and direct.")
        self.write(".prose-voice/AUDIENCE.md", "# Audience\nCurious readers.")
        with patch.object(preflight.shutil, "which", return_value="/tool"):
            report = preflight.cmd_check(self.root)
        self.assertTrue(report["ready"])
        self.assertIsNone(report["voice"]["ILLUSTRATIONS.md"]["resolved"])
        seeded = preflight.cmd_seed(self.root, "project", True)
        self.assertEqual(len(seeded["files"]), 2)
        self.assertFalse((self.root / ".prose-voice/ILLUSTRATIONS.md").exists())

    def test_visual_guidance_uses_independent_project_global_fallback(self):
        global_path = self.write(".prose-voice/ILLUSTRATIONS.md", "Use simple line drawings.", self.home)
        self.write(".prose-voice/VOICE.md", "Project voice")
        self.write(".prose-voice/AUDIENCE.md", "Global audience", self.home)
        resolved = preflight.resolve(self.root)
        self.assertEqual(resolved["ILLUSTRATIONS.md"]["resolved"]["path"], str(global_path))
        self.assertEqual(resolved["AUDIENCE.md"]["resolved"]["level"], "global")
        local = self.write(".prose-voice/ILLUSTRATIONS.md", "Project palette")
        self.assertEqual(preflight.resolve(self.root)["ILLUSTRATIONS.md"]["resolved"]["path"], str(local))
        local.write_text("<!-- pv-template: unfilled -->", encoding="utf-8")
        self.assertEqual(preflight.resolve(self.root)["ILLUSTRATIONS.md"]["resolved"]["level"], "global")

    def test_plain_multi_part_essays_need_no_hero_or_section_images(self):
        parts = [self.write("opening.md", "# Why\n\n## Mechanism\nAn explanation."),
                 self.write("chapters/evidence.md", "## Evidence\nSupporting evidence.")]
        self.assertTrue(all(ready.check_image(p)["resolved"] for p in parts))
        self.assertTrue(ready.check_source(parts)["resolved"])
        self.assertFalse(any(ready.sidecar_path(p).exists() for p in parts))

    def test_only_anchored_visuals_need_resolved_selections(self):
        essay = self.write("explanation.md", "## Process\nSome prose.\n<!-- illus:flow1 -->\nMore prose.")
        self.assertFalse(ready.check_image(essay)["resolved"])
        sidecar = ready.sidecar_path(essay)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text("## illus:flow1\nselected: unresolved\n", encoding="utf-8")
        self.assertFalse(ready.check_image(essay)["resolved"])
        for selection in ("diagramSvg", "no-image"):
            sidecar.write_text(f"## illus:flow1\nselected: {selection}\n## illus:old\nselected: unresolved\n", encoding="utf-8")
            self.assertTrue(ready.check_image(essay)["resolved"])
        essay.write_text("## Process\nNo longer needs a visual.", encoding="utf-8")
        self.assertTrue(ready.check_image(essay)["resolved"])

    def test_configured_guidance_precedes_standard_locations(self):
        self.write(".pv/config.json", '{"guidance":{"AUDIENCE.md":["guides/reader.md"]}}')
        custom = self.write("guides/reader.md", "Specialized audience")
        self.write(".prose-voice/AUDIENCE.md", "Default audience")
        self.assertEqual(preflight.resolve(self.root)["AUDIENCE.md"]["resolved"]["path"], str(custom))
        custom.unlink()
        self.assertEqual(preflight.resolve(self.root)["AUDIENCE.md"]["resolved"]["level"], "project")

    def test_cache_paths_are_isolated_ignored_and_idempotent(self):
        essay = self.write("chapters/one.md", "Text")
        other = self.write("appendix/one.md", "More text")
        paths = preflight.prepare_artifacts(essay, self.root)
        self.assertNotEqual(paths, preflight.artifact_paths(other, self.root))
        self.assertEqual(paths["illustrations"], self.root / ".pv/cache/chapters/one.illustrations.md")
        paths["curmudgeon"].write_text("Review", encoding="utf-8")
        preflight.prepare_artifacts(essay, self.root)
        self.assertEqual((self.root / ".pv/.gitignore").read_text(), "/cache/\n")
        ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", str(paths["curmudgeon"])], capture_output=True, check=False)
        self.assertEqual(ignored.returncode, 0)

    def test_adjacent_mode_and_invalid_config(self):
        essay = self.write("essay.md", "<!-- illus:one -->")
        config = self.write(".pv/config.json", '{"artifacts":{"location":"adjacent"}}')
        self.assertEqual(ready.sidecar_path(essay), self.root / "essay.illustrations.md")
        self.write("essay.illustrations.md", "## illus:one\nselected: oneSvg\n")
        self.assertTrue(ready.check_image(essay)["resolved"])
        config.write_text('{"artifacts":{"location":"typo"}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            preflight.artifact_paths(essay, self.root)

    def test_source_flags_still_block_any_part(self):
        first = self.write("one.md", "An explanation.")
        second = self.write("two.md", "---\nstatus: ready\n---\nClaim [needs-source]\n")
        report = ready.check_source([first, second])
        self.assertFalse(report["resolved"])
        self.assertEqual(report["locations"][0]["line"], 4)


if __name__ == "__main__":
    unittest.main()
