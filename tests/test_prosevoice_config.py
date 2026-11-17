"""prosevoice layered configuration tests. Run with uv run python -m unittest discover -s tests."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
from prosevoice_lib import config as cfg
from prosevoice_lib.errors import ConfigError, ProsevoiceError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/prosevoice/scripts"

FILLED = "# Voice\n\nFilled guidance.\n"
UNFILLED = "# Voice\n\n<!-- pv-template: unfilled -->\n"


class IsolatedCase(unittest.TestCase):
    """Temporary home, XDG directory, Git project and an unrelated non-Git directory."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.xdg = self.root / "xdg"
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "-C", str(self.project), "init", "-q"], check=True)
        self.plain = self.root / "plain"
        self.plain.mkdir()
        env = patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.xdg),
                                      "GIT_CEILING_DIRECTORIES": str(self.root)})
        env.start()
        self.addCleanup(env.stop)

    @property
    def user_dir(self):
        return self.xdg / "prosevoice"

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, path, data):
        return self.write(path, json.dumps(data))

    def user_config(self, data):
        return self.write_json(self.user_dir / "config.json", data)

    def project_config(self, data):
        return self.write_json(self.project / ".prosevoice/config.json", data)

    def load(self, **kw):
        kw.setdefault("cwd", self.project)
        return cfg.load_config(**kw)

    def snapshot(self, base=None):
        base = base or self.root
        return sorted(str(p.relative_to(base)) for p in base.rglob("*") if ".git" not in p.parts)


class TierAndProvenanceTests(IsolatedCase):
    def test_builtin_defaults_have_explicit_provenance(self):
        config = self.load()
        self.assertEqual(config.effective(), {
            "schema_version": 1,
            "guidance": {"VOICE.md": [], "AUDIENCE.md": [], "ILLUSTRATIONS.md": []},
            "artifacts": {"location": "cache"},
        })
        prov = config.provenance()
        self.assertEqual(set(prov), {"guidance.VOICE.md", "guidance.AUDIENCE.md",
                                     "guidance.ILLUSTRATIONS.md", "artifacts.location"})
        for leaf in prov.values():
            self.assertEqual(leaf["tier"], "builtin")
            self.assertIsNone(leaf["source"])
        report = config.report()
        self.assertFalse(report["sources"]["user"]["present"])
        self.assertFalse(report["sources"]["project"]["present"])
        self.assertEqual(report["sources"]["cli"]["overrides"], [])
        self.assertEqual(report["roots"]["project"], str(self.project))
        self.assertEqual(report["roots"]["user_dir"], str(self.user_dir))

    def test_each_tier_wins_over_lower_tiers_with_provenance(self):
        user = self.user_config({"schema_version": 1, "guidance": {"VOICE.md": ["u-voice.md"]},
                                 "artifacts": {"location": "adjacent"}})
        project = self.project_config({"schema_version": 1, "guidance": {"VOICE.md": ["p-voice.md"]},
                                       "artifacts": {"location": "cache"}})
        config = self.load()
        prov = config.provenance()
        self.assertEqual(prov["guidance.VOICE.md"]["tier"], "project")
        self.assertEqual(prov["guidance.VOICE.md"]["source"], str(project))
        self.assertEqual(prov["artifacts.location"]["tier"], "project")
        self.assertEqual(config.artifacts_location, "cache")
        self.assertTrue(config.report()["sources"]["user"]["present"])
        self.assertEqual(config.report()["sources"]["user"]["path"], str(user))

        cwd = self.project / "sub"
        cwd.mkdir()
        config = self.load(cwd=cwd, overrides=['guidance.VOICE.md=["c-voice.md"]',
                                               'artifacts.location="adjacent"'])
        prov = config.provenance()
        self.assertEqual(prov["guidance.VOICE.md"]["tier"], "cli")
        self.assertEqual(prov["guidance.VOICE.md"]["source"], "--set guidance.VOICE.md")
        self.assertEqual(prov["artifacts.location"]["tier"], "cli")
        self.assertEqual(config.artifacts_location, "adjacent")
        self.assertEqual(config.guidance_candidates("VOICE.md"), [cwd / "c-voice.md"])
        self.assertEqual(config.report()["sources"]["cli"]["overrides"],
                         ["artifacts.location", "guidance.VOICE.md"])

    def test_user_only_values_keep_user_provenance(self):
        self.user_config({"schema_version": 1, "artifacts": {"location": "adjacent"}})
        self.project_config({"schema_version": 1, "guidance": {"AUDIENCE.md": ["a.md"]}})
        prov = self.load().provenance()
        self.assertEqual(prov["artifacts.location"]["tier"], "user")
        self.assertEqual(prov["guidance.AUDIENCE.md"]["tier"], "project")
        self.assertEqual(prov["guidance.VOICE.md"]["tier"], "builtin")

    def test_list_replacement_is_per_filename_without_losing_other_guides(self):
        self.user_config({"schema_version": 1, "guidance": {
            "VOICE.md": ["u1.md", "u2.md"], "AUDIENCE.md": ["ua.md"], "ILLUSTRATIONS.md": ["ui.md"]}})
        self.project_config({"schema_version": 1, "guidance": {"VOICE.md": ["p1.md"]}})
        config = self.load(overrides=['guidance.ILLUSTRATIONS.md=[]'])
        self.assertEqual(config.guidance_candidates("VOICE.md"), [self.project / "p1.md"])
        self.assertEqual(config.guidance_candidates("AUDIENCE.md"), [self.user_dir / "ua.md"])
        self.assertEqual(config.guidance_candidates("ILLUSTRATIONS.md"), [])
        prov = config.provenance()
        self.assertEqual([prov[f"guidance.{n}"]["tier"] for n in cfg.GUIDES], ["project", "user", "cli"])

    def test_empty_project_list_clears_user_candidates(self):
        self.user_config({"schema_version": 1, "guidance": {"VOICE.md": ["u.md"]}})
        self.project_config({"schema_version": 1, "guidance": {"VOICE.md": []}})
        config = self.load()
        self.assertEqual(config.guidance_candidates("VOICE.md"), [])
        self.assertEqual(config.provenance()["guidance.VOICE.md"]["tier"], "project")

    def test_relative_paths_anchor_to_their_tier_and_tilde_expands(self):
        self.user_config({"schema_version": 1, "guidance": {"VOICE.md": ["guides/v.md", "~/home-v.md"]}})
        self.project_config({"schema_version": 1, "guidance": {"AUDIENCE.md": ["docs/a.md", str(self.root / "abs.md")]}})
        config = self.load(cwd=self.plain, project=self.project,
                           overrides=['guidance.ILLUSTRATIONS.md=["pics/i.md", "~/i.md"]'])
        self.assertEqual(config.guidance_candidates("VOICE.md"),
                         [self.user_dir / "guides/v.md", self.home / "home-v.md"])
        self.assertEqual(config.guidance_candidates("AUDIENCE.md"),
                         [self.project / "docs/a.md", self.root / "abs.md"])
        self.assertEqual(config.guidance_candidates("ILLUSTRATIONS.md"),
                         [self.plain / "pics/i.md", self.home / "i.md"])
        prov = config.provenance()
        self.assertEqual(prov["guidance.VOICE.md"]["anchor"], str(self.user_dir))
        self.assertEqual(prov["guidance.AUDIENCE.md"]["anchor"], str(self.project))
        self.assertEqual(prov["guidance.ILLUSTRATIONS.md"]["anchor"], str(self.plain))
        self.assertEqual(config.report()["resolved"]["guidance"]["VOICE.md"],
                         [str(self.user_dir / "guides/v.md"), str(self.home / "home-v.md")])


class LocationTests(IsolatedCase):
    def test_xdg_absolute_is_used(self):
        self.assertEqual(cfg.user_config_dir(), self.xdg / "prosevoice")

    def test_xdg_unset_or_empty_falls_back_to_home_config(self):
        expected = self.home / ".config/prosevoice"
        self.assertEqual(cfg.user_config_dir({}), expected)
        self.assertEqual(cfg.user_config_dir({"XDG_CONFIG_HOME": ""}), expected)
        with patch.dict(os.environ, {}, clear=False):
            del os.environ["XDG_CONFIG_HOME"]
            self.write_json(expected / "config.json", {"schema_version": 1, "artifacts": {"location": "adjacent"}})
            config = self.load()
            self.assertEqual(config.user_config, expected / "config.json")
            self.assertEqual(config.provenance()["artifacts.location"]["tier"], "user")

    def test_relative_xdg_is_rejected(self):
        with self.assertRaises(ConfigError) as caught:
            cfg.user_config_dir({"XDG_CONFIG_HOME": "relative/xdg"})
        self.assertEqual(caught.exception.code, "xdg-not-absolute")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative/xdg"}), self.assertRaises(ConfigError):
            self.load()

    def test_project_selection_explicit_git_and_cwd(self):
        nested = self.project / "a/b"
        nested.mkdir(parents=True)
        config = self.load(cwd=nested)
        self.assertEqual((config.project_root, config.project_selection), (self.project, "git"))
        config = self.load(cwd=self.plain)
        self.assertEqual((config.project_root, config.project_selection), (self.plain, "cwd"))
        config = self.load(cwd=nested, project=self.plain)
        self.assertEqual((config.project_root, config.project_selection), (self.plain, "explicit"))
        config = self.load(cwd=self.root, project="plain")
        self.assertEqual(config.project_root, self.plain)
        self.assertEqual(config.project_config, self.plain / ".prosevoice/config.json")

    def test_explicit_project_must_exist(self):
        for value in (self.root / "missing", "missing-relative"):
            with self.assertRaises(ConfigError) as caught:
                self.load(cwd=self.root, project=value)
            self.assertEqual(caught.exception.code, "project-missing")
        self.write(self.root / "file.txt", "x")
        with self.assertRaises(ConfigError):
            self.load(project=self.root / "file.txt")

    def test_legacy_directories_are_never_discovered(self):
        self.write_json(self.project / ".prose-voice/config.json",
                        {"guidance": {"VOICE.md": ["old.md"]}, "artifacts": {"location": "adjacent"}})
        self.write(self.project / ".prose-voice/VOICE.md", FILLED)
        self.write(self.home / ".prose-voice/AUDIENCE.md", FILLED)
        config = self.load()
        self.assertEqual(config.artifacts_location, "cache")
        resolved = cfg.resolve_guidance(config)
        self.assertIsNone(resolved["VOICE.md"]["resolved"])
        self.assertIsNone(resolved["AUDIENCE.md"]["resolved"])
        tried = [t["path"] for n in cfg.GUIDES for t in resolved[n]["tried"]]
        self.assertFalse([p for p in tried if ".prose-voice" in p])


class StrictValidationTests(IsolatedCase):
    def assert_config_error(self, text, code=None, tier="project"):
        path = (self.project / ".prosevoice/config.json") if tier == "project" else (self.user_dir / "config.json")
        self.write(path, text)
        with self.assertRaises(ConfigError) as caught:
            self.load()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertIn(str(path), caught.exception.paths)
        path.unlink()

    def test_rejections(self):
        cases = [
            ('{"schema_version": 1, "schema_version": 1}', "config-malformed"),
            ('{"schema_version": 1, "guidance": {"VOICE.md": [], "VOICE.md": []}}', "config-malformed"),
            ('{"schema_version": 1,', "config-malformed"),
            ('{"schema_version": 1, "x": NaN}', "config-malformed"),
            ("[]", "config-invalid"),
            ("{}", "config-invalid"),
            ('{"schema_version": 2}', "config-schema-version"),
            ('{"schema_version": "1"}', "config-schema-version"),
            ('{"schema_version": true}', "config-schema-version"),
            ('{"schema_version": 1, "extra": 1}', "config-unknown-key"),
            ('{"schema_version": 1, "guidance": {"NOTES.md": []}}', "config-unknown-key"),
            ('{"schema_version": 1, "artifacts": {"location": "cache", "dir": "x"}}', "config-unknown-key"),
            ('{"schema_version": 1, "guidance": []}', "config-invalid"),
            ('{"schema_version": 1, "guidance": {"VOICE.md": "v.md"}}', "config-invalid"),
            ('{"schema_version": 1, "guidance": {"VOICE.md": [""]}}', "config-invalid"),
            ('{"schema_version": 1, "guidance": {"VOICE.md": ["  "]}}', "config-invalid"),
            ('{"schema_version": 1, "guidance": {"VOICE.md": [3]}}', "config-invalid"),
            ('{"schema_version": 1, "artifacts": []}', "config-invalid"),
            ('{"schema_version": 1, "artifacts": {"location": "elsewhere"}}', "config-invalid"),
            ('{"schema_version": 1, "artifacts": {"location": ["cache"]}}', "config-invalid"),
        ]
        for tier in ("project", "user"):
            for text, code in cases:
                with self.subTest(tier=tier, text=text):
                    self.assert_config_error(text, code, tier)

    def test_invalid_higher_or_lower_tier_never_falls_through(self):
        self.user_config({"schema_version": 1, "artifacts": {"location": "adjacent"}})
        self.write(self.project / ".prosevoice/config.json", "{not json")
        with self.assertRaises(ConfigError):
            self.load()
        self.project_config({"schema_version": 1})
        self.write(self.user_dir / "config.json", '{"schema_version": 1, "bogus": true}')
        with self.assertRaises(ConfigError):
            self.load()

    def test_config_directory_or_undecodable_file_is_an_error(self):
        (self.project / ".prosevoice/config.json").mkdir(parents=True)
        with self.assertRaises(ConfigError) as caught:
            self.load()
        self.assertEqual(caught.exception.code, "config-unreadable")
        (self.project / ".prosevoice/config.json").rmdir()
        (self.project / ".prosevoice/config.json").write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(ConfigError) as caught:
            self.load()
        self.assertEqual(caught.exception.code, "config-unreadable")

    def test_override_rejections(self):
        cases = [
            ("guidance.NOTES.md=[]", "override-unknown-key"),
            ("guidance=[]", "override-unknown-key"),
            ("artifacts.dir=\"x\"", "override-unknown-key"),
            ("schema_version=1", "override-unknown-key"),
            ("artifacts.location", "override-invalid"),
            ("artifacts.location=cache", "override-invalid"),
            ('artifacts.location="nowhere"', "config-invalid"),
            ('guidance.VOICE.md="v.md"', "config-invalid"),
            ('guidance.VOICE.md=[""]', "config-invalid"),
        ]
        for item, code in cases:
            with self.subTest(item=item):
                with self.assertRaises(ConfigError) as caught:
                    self.load(overrides=[item])
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(ConfigError) as caught:
            self.load(overrides=['artifacts.location="cache"', 'artifacts.location="adjacent"'])
        self.assertEqual(caught.exception.code, "override-duplicate")

    def test_guidance_key_with_filename_suffix_is_one_key(self):
        config = self.load(overrides=['guidance.AUDIENCE.md=["x/a.md"]'])
        self.assertEqual(config.guidance_candidates("AUDIENCE.md"), [self.project / "x/a.md"])
        self.assertEqual(config.effective()["guidance"]["AUDIENCE.md"], ["x/a.md"])


class GuidanceResolutionTests(IsolatedCase):
    def test_order_configured_project_user_and_first_usable_wins(self):
        self.project_config({"schema_version": 1, "guidance": {"VOICE.md": ["c1.md", "c2.md"]}})
        self.write(self.project / "c1.md", UNFILLED)
        self.write(self.project / "c2.md", FILLED)
        self.write(self.project / ".prosevoice/VOICE.md", FILLED)
        self.write(self.user_dir / "VOICE.md", FILLED)
        result = cfg.resolve_guidance(self.load())["VOICE.md"]
        self.assertEqual(result["resolved"], {"level": "configured", "path": str(self.project / "c2.md")})
        self.assertEqual([(t["level"], t["state"]) for t in result["tried"]],
                         [("configured", "unfilled"), ("configured", "ok"), ("project", "ok"), ("user", "ok")])
        self.assertTrue(result["required"])

    def test_each_guide_falls_back_independently(self):
        self.write(self.project / ".prosevoice/VOICE.md", "  \n")
        self.write(self.user_dir / "VOICE.md", FILLED)
        self.write(self.project / ".prosevoice/AUDIENCE.md", FILLED)
        self.write(self.user_dir / "AUDIENCE.md", UNFILLED)
        result = cfg.resolve_guidance(self.load())
        self.assertEqual(result["VOICE.md"]["resolved"]["level"], "user")
        self.assertEqual(result["VOICE.md"]["tried"][0]["state"], "empty")
        self.assertEqual(result["AUDIENCE.md"]["resolved"]["level"], "project")
        self.assertIsNone(result["ILLUSTRATIONS.md"]["resolved"])
        self.assertFalse(result["ILLUSTRATIONS.md"]["required"])
        self.assertEqual({t["state"] for t in result["ILLUSTRATIONS.md"]["tried"]}, {"absent"})

    def test_empty_and_unfilled_everywhere_resolve_nothing(self):
        self.project_config({"schema_version": 1, "guidance": {"VOICE.md": ["missing.md"]}})
        self.write(self.project / ".prosevoice/VOICE.md", "")
        self.write(self.user_dir / "VOICE.md", UNFILLED)
        result = cfg.resolve_guidance(self.load())["VOICE.md"]
        self.assertIsNone(result["resolved"])
        self.assertEqual([t["state"] for t in result["tried"]], ["absent", "empty", "unfilled"])

    def test_resolution_and_config_never_write(self):
        before = self.snapshot()
        config = self.load()
        config.report()
        cfg.resolve_guidance(config)
        cfg.artifact_paths(config, self.project / "essay.md")
        self.assertEqual(self.snapshot(), before)


class ArtifactTests(IsolatedCase):
    def test_cache_paths_for_all_twelve_kinds_preserve_relative_directories(self):
        self.assertEqual(len(cfg.ARTIFACT_KINDS), 12)
        essay = self.write(self.project / "posts/2026/deep/essay.md", FILLED)
        paths = cfg.artifact_paths(self.load(), essay)
        self.assertEqual(list(paths), list(cfg.ARTIFACT_KINDS))
        for kind, path in paths.items():
            self.assertEqual(path, self.project / ".prosevoice/cache/posts/2026/deep" / f"essay.{kind}.md")

    def test_relative_essay_is_anchored_to_cwd(self):
        cwd = self.project / "posts"
        cwd.mkdir()
        paths = cfg.artifact_paths(self.load(cwd=cwd), Path("e.md"))
        self.assertEqual(paths["review"], self.project / ".prosevoice/cache/posts/e.review.md")

    def test_adjacent_paths_keep_existing_names(self):
        self.project_config({"schema_version": 1, "artifacts": {"location": "adjacent"}})
        essay = self.project / "posts/essay.md"
        paths = cfg.artifact_paths(self.load(), essay)
        for kind, path in paths.items():
            self.assertEqual(path, self.project / "posts" / f"essay.{kind}.md")
        outside = self.plain / "x.md"
        self.assertEqual(cfg.artifact_paths(self.load(), outside)["draft"], self.plain / "x.draft.md")

    def test_cache_mode_rejects_essay_outside_project(self):
        with self.assertRaises(ProsevoiceError) as caught:
            cfg.artifact_paths(self.load(), self.plain / "x.md")
        self.assertEqual(caught.exception.code, "essay-outside-project")

    def test_prepare_creates_directory_and_ignore_idempotently(self):
        config = self.load()
        essay = self.project / "posts/essay.md"
        first = cfg.prepare_artifacts(config, essay)
        self.assertTrue(first["ignore_written"])
        self.assertTrue((self.project / ".prosevoice/cache/posts").is_dir())
        ignore = self.project / ".prosevoice/.gitignore"
        self.assertEqual(ignore.read_text(), "/cache/\n")
        second = cfg.prepare_artifacts(config, essay)
        self.assertFalse(second["ignore_written"])
        self.assertEqual(ignore.read_text(), "/cache/\n")

    def test_prepare_retains_custom_ignore_content(self):
        ignore = self.write(self.project / ".prosevoice/.gitignore", "*.tmp\n# keep\nnotes")
        cfg.prepare_artifacts(self.load(), self.project / "e.md")
        self.assertEqual(ignore.read_text(), "*.tmp\n# keep\nnotes\n/cache/\n")
        for existing in ("cache/\n", "/cache\n", "  cache/**  \n"):
            ignore.write_text("*.tmp\n" + existing)
            cfg.prepare_artifacts(self.load(), self.project / "e.md")
            self.assertEqual(ignore.read_text(), "*.tmp\n" + existing)

    def test_prepare_in_adjacent_mode_writes_no_ignore(self):
        self.project_config({"schema_version": 1, "artifacts": {"location": "adjacent"}})
        result = cfg.prepare_artifacts(self.load(), self.project / "posts/e.md")
        self.assertFalse(result["ignore_written"])
        self.assertFalse((self.project / ".prosevoice/.gitignore").exists())
        self.assertTrue((self.project / "posts").is_dir())


class InitTests(IsolatedCase):
    def test_project_init_seeds_config_guides_and_ignore(self):
        result = cfg.init("project", cwd=self.project)
        pv = self.project / ".prosevoice"
        self.assertEqual(sorted(result["created"]),
                         sorted(str(pv / n) for n in ("config.json", "VOICE.md", "AUDIENCE.md")))
        self.assertTrue(result["ignore_updated"])
        self.assertEqual(json.loads((pv / "config.json").read_text()), {"schema_version": 1})
        self.assertFalse((pv / "ILLUSTRATIONS.md").exists())
        self.assertIn(cfg.UNFILLED, (pv / "VOICE.md").read_text())
        self.assertEqual((pv / ".gitignore").read_text(), "/cache/\n")
        # Seeded blanks are not usable guidance.
        resolved = cfg.resolve_guidance(self.load())
        self.assertIsNone(resolved["VOICE.md"]["resolved"])
        self.assertEqual(resolved["VOICE.md"]["tried"][0]["state"], "unfilled")
        # The seeded config is itself valid.
        self.assertTrue(self.load().report()["sources"]["project"]["present"])

    def test_illustrations_require_explicit_flag(self):
        result = cfg.init("project", cwd=self.project, illustrations=True)
        self.assertIn(str(self.project / ".prosevoice/ILLUSTRATIONS.md"), result["created"])
        self.assertTrue(result["illustrations"])

    def test_init_is_idempotent_and_never_overwrites(self):
        pv = self.project / ".prosevoice"
        self.write(pv / "VOICE.md", FILLED)
        self.write(pv / ".gitignore", "custom\n")
        first = cfg.init("project", cwd=self.project)
        self.assertIn(str(pv / "VOICE.md"), first["kept"])
        self.assertEqual((pv / "VOICE.md").read_text(), FILLED)
        self.assertEqual((pv / ".gitignore").read_text(), "custom\n/cache/\n")
        before = {p: p.read_bytes() for p in pv.rglob("*")}
        second = cfg.init("project", cwd=self.project)
        self.assertEqual(second["created"], [])
        self.assertFalse(second["ignore_updated"])
        self.assertEqual({p: p.read_bytes() for p in pv.rglob("*")}, before)

    def test_init_refuses_invalid_existing_config_without_writing(self):
        self.write(self.project / ".prosevoice/config.json", '{"schema_version": 9}')
        before = self.snapshot()
        with self.assertRaises(ConfigError):
            cfg.init("project", cwd=self.project)
        self.assertEqual(self.snapshot(), before)

    def test_user_init_and_explicit_non_git_project(self):
        result = cfg.init("user", cwd=self.plain)
        self.assertEqual(result["directory"], str(self.user_dir))
        self.assertTrue((self.user_dir / "config.json").is_file())
        self.assertTrue((self.user_dir / "AUDIENCE.md").is_file())
        self.assertFalse((self.user_dir / ".gitignore").exists())
        self.assertFalse((self.plain / ".prosevoice").exists())
        result = cfg.init("project", cwd=self.root, project=self.plain)
        self.assertEqual(result["directory"], str(self.plain / ".prosevoice"))
        self.assertTrue((self.plain / ".prosevoice/config.json").is_file())


if __name__ == "__main__":
    unittest.main()
