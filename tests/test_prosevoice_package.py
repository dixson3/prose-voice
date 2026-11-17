"""prosevoice package, resource lookup and CLI envelope tests.

Run with uv run python -m unittest discover -s tests.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import _prosevoice_path  # noqa: F401  (adds the source skill to sys.path)
import prosevoice_lib
from prosevoice_lib import cli
from prosevoice_lib.errors import ProsevoiceError

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/prosevoice"
SCRIPTS = SKILL / "scripts"
LAUNCHER = SCRIPTS / "prosevoice.py"

FILLED = "# Guide\n\nFilled guidance.\n"
ENVELOPE_KEYS = {"schema_version", "command", "status", "data", "diagnostics"}


class IsolatedEnv(unittest.TestCase):
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
        self.unrelated = self.root / "unrelated"
        self.unrelated.mkdir()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.xdg),
                    "GIT_CEILING_DIRECTORIES": str(self.root)}
        patcher = patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *argv, cwd=None):
        """Run in-process from ``cwd``; return (payload, exit code)."""
        old = Path.cwd()
        os.chdir(cwd or self.project)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cli.main(list(argv))
        finally:
            os.chdir(old)
        payload = json.loads(out.getvalue())
        self.assertEqual(set(payload), ENVELOPE_KEYS)
        self.assertEqual(payload["schema_version"], 1)
        for diag in payload["diagnostics"]:
            self.assertEqual(set(diag), {"code", "message", "paths"})
        return payload, code

    def run_launcher(self, launcher, *argv, cwd=None, python=sys.executable):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        env.update(self.env)
        proc = subprocess.run([python, "-I", str(launcher), *argv], cwd=cwd or self.unrelated,
                              capture_output=True, text=True, env=env, check=False)
        return proc


class ResourceLookupTests(IsolatedEnv):
    def test_source_skill_root_and_templates(self):
        self.assertEqual(prosevoice_lib.skill_root(), SKILL)
        self.assertEqual(prosevoice_lib.resource_mode(), "source")
        for name in ("VOICE.md", "AUDIENCE.md", "ILLUSTRATIONS.md"):
            path = prosevoice_lib.resource("templates", name)
            self.assertEqual(path, SKILL / "templates" / name)
            self.assertIn("pv-template: unfilled", path.read_text(encoding="utf-8"))

    def test_lookup_ignores_cwd(self):
        old = Path.cwd()
        os.chdir(self.unrelated)
        try:
            self.write(self.unrelated / "templates/VOICE.md", "decoy")
            self.assertEqual(prosevoice_lib.resource("templates", "VOICE.md"), SKILL / "templates/VOICE.md")
        finally:
            os.chdir(old)

    def test_missing_resource_raises(self):
        with self.assertRaises(ProsevoiceError) as caught:
            prosevoice_lib.resource("templates", "NOPE.md")
        self.assertEqual(caught.exception.code, "resource-missing")

    def test_packaged_skill_directory_is_preferred(self):
        site = self.root / "site"
        shutil.copytree(SCRIPTS / "prosevoice_lib", site / "prosevoice_lib",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(SKILL / "templates", site / "prosevoice_lib/_skill/templates")
        code = ("import json, prosevoice_lib as p; "
                "print(json.dumps([str(p.skill_root()), p.resource_mode(), "
                "str(p.resource('templates', 'VOICE.md'))]))")
        env = dict(os.environ, PYTHONPATH=str(site))
        proc = subprocess.run([sys.executable, "-c", code], cwd=self.unrelated, env=env,
                              capture_output=True, text=True, check=True)
        root, mode, voice = json.loads(proc.stdout)
        packaged = site / "prosevoice_lib/_skill"
        self.assertEqual((Path(root), mode), (packaged, "packaged"))
        self.assertEqual(Path(voice), packaged / "templates/VOICE.md")

    def test_package_version_matches_repository_version(self):
        self.assertEqual(prosevoice_lib.__version__, (ROOT / "VERSION").read_text().strip())


class LauncherTests(IsolatedEnv):
    def test_launcher_runs_from_unrelated_cwd(self):
        proc = self.run_launcher(LAUNCHER, "version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["command"], "version")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["skill_root"], str(SKILL))
        self.assertEqual(payload["data"]["resource_mode"], "source")

    @unittest.skipUnless(shutil.which("uv"), "uv not installed")
    def test_launcher_runs_through_uv_script(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
        proc = subprocess.run(["uv", "run", "--quiet", "--script", str(LAUNCHER), "version"],
                              cwd=self.unrelated, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["data"]["version"], prosevoice_lib.__version__)

    def test_copied_skill_tree_runs_without_siblings(self):
        copy = self.root / "installed/skills/prosevoice"
        shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
        self.assertFalse((copy.parent / "pv-preflight").exists())
        proc = self.run_launcher(copy / "scripts/prosevoice.py", "version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["data"]["skill_root"], str(copy))
        proc = self.run_launcher(copy / "scripts/prosevoice.py", "init", "--project", str(self.unrelated))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        seeded = (self.unrelated / ".prosevoice/VOICE.md").read_text(encoding="utf-8")
        self.assertEqual(seeded, (copy / "templates/VOICE.md").read_text(encoding="utf-8"))


class EnvelopeAndExitTests(IsolatedEnv):
    def test_version_ok(self):
        payload, code = self.run_cli("version")
        self.assertEqual((payload["status"], code), ("ok", 0))
        self.assertEqual(payload["diagnostics"], [])

    def test_usage_errors_use_envelope_and_exit_2(self):
        cases = [
            ((), None),
            (("bogus",), None),
            (("config", "--nope"), "config"),
            (("artifacts",), "artifacts"),
            (("artifacts", "e.md", "--kind", "summary"), "artifacts"),
            (("init", "--scope", "everywhere"), "init"),
        ]
        for argv, command in cases:
            with self.subTest(argv=argv):
                payload, code = self.run_cli(*argv)
                self.assertEqual((payload["status"], code), ("error", 2))
                self.assertEqual(payload["command"], command)
                self.assertEqual(payload["diagnostics"][0]["code"], "usage")

    def test_config_errors_exit_2(self):
        payload, code = self.run_cli("config", "--set", "guidance.NOTES.md=[]")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "override-unknown-key")
        self.write(self.project / ".prosevoice/config.json", '{"schema_version": 1, "x": 1}')
        for command in ("config", "resolve", "init"):
            payload, code = self.run_cli(command)
            self.assertEqual((payload["command"], payload["status"], code), (command, "error", 2))
            self.assertIn(str(self.project / ".prosevoice/config.json"), payload["diagnostics"][0]["paths"])
        payload, code = self.run_cli("version", "--project", str(self.root / "missing"))
        self.assertEqual((payload["status"], code), ("ok", 0))  # version reads no config
        payload, code = self.run_cli("config", "--project", str(self.root / "missing"))
        self.assertEqual(payload["diagnostics"][0]["code"], "project-missing")
        self.assertEqual(code, 2)

    def test_relative_xdg_is_an_error_envelope(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "rel"}):
            payload, code = self.run_cli("config")
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "xdg-not-absolute")

    def test_config_reports_effective_values_and_provenance(self):
        payload, code = self.run_cli("config", "--set", 'artifacts.location="adjacent"', cwd=self.project)
        self.assertEqual(code, 0)
        data = payload["data"]
        self.assertEqual(data["effective"]["artifacts"]["location"], "adjacent")
        self.assertEqual(data["provenance"]["artifacts.location"]["tier"], "cli")
        self.assertEqual(data["provenance"]["guidance.VOICE.md"]["tier"], "builtin")
        self.assertEqual(data["roots"]["project"], str(self.project))
        self.assertEqual(data["roots"]["user_dir"], str(self.xdg / "prosevoice"))

    def test_resolve_blocked_then_ok(self):
        payload, code = self.run_cli("resolve")
        self.assertEqual((payload["status"], code), ("blocked", 1))
        self.assertEqual(sorted(d["code"] for d in payload["diagnostics"]), ["guide-unresolved"] * 2)
        self.write(self.project / ".prosevoice/VOICE.md", FILLED)
        self.write(self.xdg / "prosevoice/AUDIENCE.md", FILLED)
        payload, code = self.run_cli("resolve")
        self.assertEqual((payload["status"], code), ("ok", 0))
        self.assertEqual(payload["data"]["guidance"]["AUDIENCE.md"]["resolved"]["level"], "user")
        self.assertIsNone(payload["data"]["guidance"]["ILLUSTRATIONS.md"]["resolved"])

    def test_init_cli_is_idempotent(self):
        first, code = self.run_cli("init", "--illustrations")
        self.assertEqual(code, 0)
        self.assertEqual(len(first["data"]["created"]), 4)
        second, code = self.run_cli("init", "--illustrations")
        self.assertEqual((second["status"], code, second["data"]["created"]), ("ok", 0, []))
        _, code = self.run_cli("resolve")
        self.assertEqual(code, 1)  # seeded blanks stay unfilled

    def test_artifacts_preview_kind_and_apply(self):
        payload, code = self.run_cli("artifacts", "posts/e.md", "--kind", "fact-check")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["paths"],
                         {"fact-check": str(self.project / ".prosevoice/cache/posts/e.fact-check.md")})
        self.assertFalse((self.project / ".prosevoice").exists())
        payload, code = self.run_cli("artifacts", "posts/e.md", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["data"]["paths"]), 12)
        self.assertTrue(payload["data"]["ignore_updated"])
        self.assertTrue((self.project / ".prosevoice/cache/posts").is_dir())
        # A non-Git essay without --project keeps its cache beside it.
        payload, code = self.run_cli("artifacts", str(self.unrelated / "x.md"), "--kind", "draft")
        self.assertEqual((payload["status"], code), ("ok", 0))
        self.assertEqual(payload["data"]["paths"],
                         {"draft": str(self.unrelated / ".prosevoice/cache/x.draft.md")})
        payload, code = self.run_cli("artifacts", str(self.unrelated / "x.md"), "--project", str(self.project))
        self.assertEqual((payload["status"], code), ("error", 2))
        self.assertEqual(payload["diagnostics"][0]["code"], "essay-outside-project")

    def test_help_is_conventional_text(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            cli.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("usage: prosevoice", out.getvalue())
        with redirect_stdout(io.StringIO()) as sub, self.assertRaises(SystemExit):
            cli.main(["artifacts", "--help"])
        self.assertIn("--kind", sub.getvalue())


if __name__ == "__main__":
    unittest.main()
