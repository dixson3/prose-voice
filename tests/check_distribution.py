#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Developer distribution check for the prosevoice skill and package.

Run from the source repository with ``uv run tests/check_distribution.py``. Everything
happens in a temporary directory with an isolated ``HOME`` and ``XDG_CONFIG_HOME``; the
real home, installed tooling and operator projects are never touched. Three surfaces are
exercised:

1. wheel   - build with uv/Hatchling, install into an isolated uv environment and run the
             ``prosevoice`` console command from an unrelated directory;
2. copy    - copy only ``skills/prosevoice`` and run its thin PEP 723 launcher;
3. install - ``npx skills add <source-repo> -s prosevoice -a claude-code -a pi -y`` in a
             scratch Git repository, then run the installed helper (check, resolve, rule
             preview/apply, READY) against filled fixture guides.

Exit status: 0 when every check passed, 1 when any check failed, 2 when nothing failed but
a surface could not be verified (missing dependency or network failure). Unverified is
never reported as a pass. Command output is printed for every failure.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills/prosevoice"
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
KINDS = ("curmudgeon", "steelman", "illustrations", "draft", "review", "ready",
         "copyedit", "provenance", "fact-check", "footnoter", "red-team", "cold-read")
AGENTS = ("cold-read", "copy-editor", "curmudgeon", "fact-checker", "footnoter", "grammar-check",
          "illustrator", "provenance", "readability-critic", "red-team", "steelman-response",
          "voice-stylist")
RESOURCES = ("SKILL.md", "PROSEVOICE-PROTOCOL.md", "harper/dictionary.txt", "harper/ignore-rules.txt",
             "templates/VOICE.md", "templates/AUDIENCE.md", "templates/ILLUSTRATIONS.md",
             *(f"agents/{name}.md" for name in AGENTS))
LEGACY = ("pv-prosevoice", "pv-preflight", "PV-PROTOCOL")
NETWORK = re.compile(r"ENOTFOUND|EAI_AGAIN|ETIMEDOUT|ECONNREFUSED|ECONNRESET|getaddrinfo|"
                     r"network|Failed to fetch|Could not connect|dns error|offline", re.IGNORECASE)
BEGIN = "<!-- BEGIN prosevoice (managed by prosevoice rule; edits are overwritten) -->"


class Unverified(Exception):
    """A dependency or the network was unavailable; the surface could not be checked."""


class Failed(Exception):
    """A command or assertion failed; the surface stops at the first failure."""


class Checker:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []
        self.unverified: list[str] = []
        self.surface = ""

    def ok(self, condition: bool, message: str, detail: object = None) -> None:
        if condition:
            self.passed += 1
            return
        text = f"[{self.surface}] {message}"
        if detail is not None:
            text += "\n" + (detail if isinstance(detail, str) else json.dumps(detail, indent=2, default=str))
        raise Failed(text)

    def surface_run(self, name: str, fn) -> None:
        self.surface = name
        print(f"\n== {name}", flush=True)
        try:
            fn()
            print(f"   {name}: passed", flush=True)
        except Unverified as error:
            self.unverified.append(f"[{name}] {error}")
            print(f"   {name}: UNVERIFIED - {error}", flush=True)
        except Failed as error:
            self.failures.append(str(error))
            print(f"   {name}: FAILED\n{error}", flush=True)
        except Exception as error:  # noqa: BLE001 - an unexpected payload shape is a failure, never a pass
            import traceback
            self.failures.append(f"[{name}] unexpected {type(error).__name__}: {error}")
            print(f"   {name}: FAILED\n{traceback.format_exc()}", flush=True)


CHECK = Checker()


def run(argv, *, cwd: Path, env: dict, timeout: int = 300, network: bool = False) -> subprocess.CompletedProcess:
    """Run a command, echoing it; raise Unverified when the tool is missing."""
    argv = [str(a) for a in argv]
    print(f"   $ {' '.join(argv)}   (cwd {cwd})", flush=True)
    if shutil.which(argv[0], path=env.get("PATH")) is None and not Path(argv[0]).is_file():
        raise Unverified(f"required tool not found: {argv[0]}")
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                              check=False)
    except subprocess.TimeoutExpired as error:
        raise Failed(f"[{CHECK.surface}] timed out after {timeout}s: {' '.join(argv)}") from error
    if proc.returncode != 0 and network and NETWORK.search(proc.stdout + proc.stderr):
        raise Unverified(f"network unavailable for {' '.join(argv)}:\n{proc.stdout}{proc.stderr}")
    return proc


def must(proc: subprocess.CompletedProcess, what: str) -> subprocess.CompletedProcess:
    CHECK.ok(proc.returncode == 0, f"{what} exited {proc.returncode}", f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


class Helper:
    """Runs one helper entry point and decodes its JSON envelope."""

    def __init__(self, prefix: list, env: dict, cwd: Path):
        self.prefix, self.env, self.cwd = prefix, env, cwd

    def __call__(self, *argv, expect: tuple | None = None, cwd: Path | None = None) -> dict:
        proc = run([*self.prefix, *argv], cwd=cwd or self.cwd, env=self.env)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            CHECK.ok(False, f"{argv[0]} did not print one JSON envelope (exit {proc.returncode})",
                     f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
            raise AssertionError("unreachable: CHECK.ok(False, ...) raises Failed")
        CHECK.ok(set(payload) == {"schema_version", "command", "status", "data", "diagnostics"}
                 and payload["schema_version"] == 1 and payload["command"] == argv[0],
                 f"{argv[0]} envelope shape", payload)
        exit_for = {"ok": 0, "blocked": 1, "error": 2}
        CHECK.ok(exit_for.get(payload["status"]) == proc.returncode,
                 f"{argv[0]} status {payload['status']} does not match exit {proc.returncode}", payload)
        if expect is not None:
            CHECK.ok((payload["status"], proc.returncode) == expect,
                     f"{' '.join(map(str, argv))}: expected {expect}, got {(payload['status'], proc.returncode)}",
                     {"payload": payload, "stderr": proc.stderr})
        return payload


# ------------------------------------------------------------------------- environment


def isolated_env(base: Path) -> dict:
    """Minimal environment: isolated HOME/XDG, no harness or virtualenv variables.

    Tool caches (uv, npm) point at the developer's existing caches so that dependency
    downloads are not repeated; they hold no harness or skill state.
    """
    home, xdg = base / "home", base / "xdg"
    home.mkdir(parents=True, exist_ok=True)
    xdg.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "XDG_CONFIG_HOME": str(xdg),
           "GIT_CEILING_DIRECTORIES": str(base), "LANG": "C.UTF-8", "TERM": "dumb", "NO_COLOR": "1",
           "DO_NOT_TRACK": "1", "DISABLE_TELEMETRY": "1", "UV_NO_CONFIG": "1", "UV_PYTHON_DOWNLOADS": "never",
           "GIT_CONFIG_NOSYSTEM": "1"}
    for name, command in (("UV_CACHE_DIR", ["uv", "cache", "dir"]),
                          ("UV_PYTHON_INSTALL_DIR", ["uv", "python", "dir"]),
                          ("npm_config_cache", ["npm", "config", "get", "cache"])):
        if name in os.environ:
            env[name] = os.environ[name]
        elif shutil.which(command[0]):
            out = subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()
            if out:
                env[name] = out
    return env


def git_init(path: Path, env: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    must(run(["git", "init", "-q"], cwd=path, env=env), "git init")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def tree_files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def skill_dir_block() -> str:
    """The documented SKILL_DIR resolver from SKILL.md, without the pv() definition."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## SKILL_DIR", 1)[1]
    block = section.split("```bash\n", 1)[1].split("```", 1)[0]
    lines = [line for line in block.splitlines() if not line.startswith("pv()")]
    CHECK.ok(any("SKILL_DIR=" in line for line in lines), "SKILL.md carries a SKILL_DIR block", block)
    return "\n".join(lines)


# ---------------------------------------------------------------- shared runtime checks


def fill_guides(directory: Path) -> None:
    for name in ("VOICE.md", "AUDIENCE.md"):
        text = (REPO / "examples" / name).read_text(encoding="utf-8")
        CHECK.ok("pv-template: unfilled" not in text, f"examples/{name} is filled")
        write(directory / name, text)


def exercise_runtime(pv: Helper, project: Path, skill_root: Path, *, apply_rules: bool = False) -> None:
    """init/template lookup, config, resolve, policy, artifacts and READY on one project."""
    pf = ["--project", project]
    config = pv("config", *pf, expect=("ok", 0))
    roots = config["data"]["roots"]
    CHECK.ok(Path(roots["project"]) == project.resolve() and roots["project_selection"] == "explicit",
             "config selects the explicit project", roots)
    CHECK.ok(all(v["tier"] == "builtin" for v in config["data"]["provenance"].values()),
             "fresh config reports builtin provenance", config["data"]["provenance"])
    bad = pv("config", *pf, "--set", "guidance.NOTES.md=[]", expect=("error", 2))
    CHECK.ok(bool(bad["diagnostics"]), "unknown --set key reports a diagnostic", bad)

    init = pv("init", *pf, expect=("ok", 0))
    pvdir = project.resolve() / ".prosevoice"
    CHECK.ok(sorted(Path(p).name for p in init["data"]["created"]) == ["AUDIENCE.md", "VOICE.md", "config.json"],
             "init seeds config and required guides only", init["data"])
    for name in ("VOICE.md", "AUDIENCE.md"):
        CHECK.ok((pvdir / name).read_bytes() == (skill_root / "templates" / name).read_bytes()
                 == (SKILL / "templates" / name).read_bytes(),
                 f"init seeded {name} from the bundled template")
    CHECK.ok("/cache/" in (pvdir / ".gitignore").read_text(encoding="utf-8").splitlines(),
             "init adds the cache ignore line")
    again = pv("init", *pf, expect=("ok", 0))
    CHECK.ok(again["data"]["created"] == [] and len(again["data"]["kept"]) == 3, "init is idempotent", again["data"])
    blocked = pv("resolve", *pf, expect=("blocked", 1))
    CHECK.ok(blocked["data"]["guidance"]["VOICE.md"]["tried"][0]["state"] == "unfilled",
             "unfilled template is not usable guidance", blocked["data"])

    fill_guides(pvdir)
    resolved = pv("resolve", *pf, expect=("ok", 0))
    for name in ("VOICE.md", "AUDIENCE.md"):
        CHECK.ok(resolved["data"]["guidance"][name]["resolved"] == {"level": "project", "path": str(pvdir / name)},
                 f"{name} resolves to the project guide", resolved["data"])
    CHECK.ok(resolved["data"]["guidance"]["ILLUSTRATIONS.md"]["resolved"] is None,
             "optional illustrations stay unresolved without blocking")

    write(pvdir / "dictionary.txt", "Distcheckword\n")
    write(project / "posts/2026/.harper-words", "Sidecarword\n")
    plain = write(project / "posts/2026/plain.md",
                  "---\nstatus: draft\nintent: explanatory\n---\n# Queues\n\nShared queues reduce delay.\n")
    out = project.parent / "policy-dict.txt"
    policy = pv("policy", plain, "--out", out, *pf, expect=("ok", 0))
    words = out.read_text(encoding="utf-8").splitlines()
    CHECK.ok({"Distcheckword", "Sidecarword"} <= set(words), "policy unions project and essay-local words",
             policy["data"])
    CHECK.ok(str(skill_root / "harper/dictionary.txt") in policy["data"]["sources"]["dictionary"]
             and str(skill_root / "harper/ignore-rules.txt") in policy["data"]["sources"]["ignore_rules"],
             "policy uses the bundled Harper policy of this installation", policy["data"]["sources"])
    CHECK.ok(not any(marker in json.dumps(policy) for marker in LEGACY + (".prose-voice",)),
             "policy has no legacy inputs", policy["data"]["sources"])

    artifacts = pv("artifacts", plain, *pf, expect=("ok", 0))
    cache = pvdir / "cache/posts/2026"
    CHECK.ok(artifacts["data"]["paths"] == {k: str(cache / f"plain.{k}.md") for k in KINDS},
             "artifacts route all 12 kinds into the nested cache", artifacts["data"])
    adjacent = pv("artifacts", plain, "--kind", "review", "--set", 'artifacts.location="adjacent"', *pf,
                  expect=("ok", 0))
    CHECK.ok(adjacent["data"]["paths"] == {"review": str(plain.parent.resolve() / "plain.review.md")},
             "adjacent mode keeps the sidecar beside the essay", adjacent["data"])

    ready = pv("ready", plain, *pf, expect=("ok", 0))
    CHECK.ok(ready["data"]["ready"] is True and ready["data"]["limitations"], "plain essay is READY-clear", ready)
    flagged = write(project / "posts/flagged.md", "# Claim\n\nQueues halve delay [needs-source].\n")
    multi = pv("ready", plain, flagged, *pf, expect=("blocked", 1))
    CHECK.ok([d["code"] for d in multi["diagnostics"]] == ["needs-source"]
             and multi["data"]["source"]["locations"][0]["line"] == 3,
             "needs-source in a later part blocks with its line", multi)
    visual = write(project / "posts/visual.md", "# Flow\n\nIntro.\n\n<!-- illus:flow1 -->\n\nMore.\n")
    unresolved = pv("ready", visual, *pf, expect=("blocked", 1))
    CHECK.ok([d["code"] for d in unresolved["diagnostics"]] == ["visual-unresolved"],
             "active anchor without a decision blocks", unresolved)
    sidecar = pv("artifacts", visual, "--kind", "illustrations", "--apply", *pf, expect=("ok", 0))
    write(Path(sidecar["data"]["paths"]["illustrations"]), "## illus:flow1\nselected: no-image\n")
    pv("ready", visual, *pf, expect=("ok", 0))
    pv("ready", project / "posts/absent.md", *pf, expect=("error", 2))
    premise = pv("premise", plain, *pf, expect=("ok", 0))
    parts = premise["data"]["parts"]
    CHECK.ok(len(parts) == 1 and re.fullmatch(r"[0-9a-f]{16}", parts[0]["fingerprint"]) is not None,
             "premise reports a 16-character fingerprint", premise["data"])


def check_resources(root: Path, label: str) -> None:
    missing = [r for r in RESOURCES if not (root / r).is_file()]
    CHECK.ok(not missing, f"{label} ships required resources", missing)
    for resource in RESOURCES:
        CHECK.ok((root / resource).read_bytes() == (SKILL / resource).read_bytes(),
                 f"{label} {resource} matches the source skill")


# ----------------------------------------------------------------------------- surfaces


def wheel_surface(base: Path) -> None:
    env = isolated_env(base)
    dist = base / "dist"
    proc = run(["uv", "build", "--wheel", "--out-dir", dist, REPO], cwd=base, env=env, timeout=600, network=True)
    must(proc, "uv build --wheel")
    wheels = sorted(dist.glob("prosevoice-*.whl"))
    CHECK.ok(len(wheels) == 1 and wheels[0].name.startswith(f"prosevoice-{VERSION}-"),
             f"one prosevoice {VERSION} wheel was built", [w.name for w in wheels])
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        entry = next((archive.read(n).decode() for n in names if n.endswith("entry_points.txt")), "")
    missing = [r for r in RESOURCES if f"prosevoice_lib/_skill/{r}" not in names]
    CHECK.ok(not missing, "wheel contains SKILL, agent, protocol, policy and template resources", missing)
    CHECK.ok("prosevoice = prosevoice_lib.cli:main" in entry, "wheel declares the prosevoice console command", entry)
    CHECK.ok(not [n for n in names if any(m in n for m in LEGACY)], "wheel contains no legacy skill files")

    venv = base / "venv"
    must(run(["uv", "venv", "--quiet", venv], cwd=base, env=env, network=True), "uv venv")
    python = venv / "bin/python"
    must(run(["uv", "pip", "install", "--quiet", "--offline", "--python", python, wheels[0]], cwd=base, env=env),
         "uv pip install wheel")
    console = venv / "bin/prosevoice"
    CHECK.ok(console.is_file(), "console command is installed", str(console))

    elsewhere = base / "unrelated"
    elsewhere.mkdir()
    help_proc = must(run([console, "--help"], cwd=elsewhere, env=env), "prosevoice --help")
    for command in ("version", "config", "init", "check", "resolve", "artifacts", "rule", "policy", "lint",
                    "extract", "premise", "ready", "migrate"):
        CHECK.ok(command in help_proc.stdout, f"--help lists {command}", help_proc.stdout)
    pv = Helper([console], env, elsewhere)
    version = pv("version", expect=("ok", 0))
    root = Path(version["data"]["skill_root"])
    CHECK.ok(version["data"]["version"] == VERSION and version["data"]["resource_mode"] == "packaged",
             "installed wheel reports its version and packaged resources", version["data"])
    CHECK.ok(root.is_relative_to(venv.resolve()) or root.is_relative_to(venv),
             "packaged resources come from the installed environment, not the checkout", str(root))
    check_resources(root, "installed wheel")
    project = base / "project"
    git_init(project, env)
    exercise_runtime(pv, project, root)


def copy_surface(base: Path) -> None:
    env = isolated_env(base)
    copy = base / "installed/skills/prosevoice"
    shutil.copytree(SKILL, copy, ignore=shutil.ignore_patterns("__pycache__"))
    CHECK.ok([p.name for p in copy.parent.iterdir()] == ["prosevoice"], "copied tree holds only prosevoice")
    elsewhere = base / "unrelated"
    elsewhere.mkdir()
    pv = Helper(["uv", "run", "--script", copy / "scripts/prosevoice.py"], env, elsewhere)
    version = pv("version", expect=("ok", 0))
    CHECK.ok(Path(version["data"]["skill_root"]) == copy.resolve() and version["data"]["resource_mode"] == "source",
             "copied launcher uses its own skill tree", version["data"])
    check_resources(copy, "copied skill")
    project = base / "project"
    git_init(project, env)
    exercise_runtime(pv, project, copy.resolve())


def install_surface(base: Path) -> None:
    env = isolated_env(base)
    home = Path(env["HOME"])
    repo = base / "writing"
    git_init(repo, env)
    agents_md = write(repo / "AGENTS.md", "# Writing project\n\nKeep this note.\n")
    original_agents = agents_md.read_bytes()
    proc = run(["npx", "-y", "skills", "add", REPO, "-s", "prosevoice", "-a", "claude-code", "-a", "pi", "-y"],
               cwd=repo, env=env, timeout=600, network=True)
    must(proc, "npx skills add")

    shared = repo / ".agents/skills/prosevoice"
    claude = repo / ".claude/skills/prosevoice"
    CHECK.ok(shared.is_dir() and claude.is_dir(), "installer created .agents and .claude skill paths",
             proc.stdout)
    CHECK.ok(claude.resolve() == shared.resolve(), "Claude Code path resolves to the shared install")
    for parent in (repo / ".agents/skills", repo / ".claude/skills"):
        CHECK.ok(sorted(p.name for p in parent.iterdir()) == ["prosevoice"], f"{parent} holds only prosevoice")
    installed = tree_files(shared)
    source = tree_files(SKILL)
    CHECK.ok(installed == source, "installed skill matches the source skill tree",
             sorted(set(installed) ^ set(source)) or [k for k in source if installed.get(k) != source[k]])
    stray = [str(p) for p in home.rglob("*") if p.name in ("prosevoice", *LEGACY)]
    CHECK.ok(not stray, "project install wrote nothing into the isolated HOME", stray)

    resolver = skill_dir_block() + '\nprintf %s "$SKILL_DIR"\n'
    found = must(run(["sh", "-c", resolver], cwd=repo, env=env), "SKILL.md SKILL_DIR block").stdout
    CHECK.ok(bool(found) and Path(found).resolve() == shared.resolve(),
             "SKILL.md SKILL_DIR block finds the installed skill", found)

    pv = Helper(["uv", "run", "--script", Path(found) / "scripts/prosevoice.py"], env, repo)
    version = pv("version", expect=("ok", 0))
    CHECK.ok(Path(version["data"]["skill_root"]).resolve() == shared.resolve(),
             "installed helper uses the installed skill resources", version["data"])
    before = pv("check", expect=("blocked", 1))
    CHECK.ok(before["data"]["ready"] is False and before["data"]["actions"], "check reports setup actions", before)

    pv("init", expect=("ok", 0))
    fill_guides(repo / ".prosevoice")
    resolved = pv("resolve", expect=("ok", 0))
    CHECK.ok(all(resolved["data"]["guidance"][n]["resolved"] for n in ("VOICE.md", "AUDIENCE.md")),
             "installed helper resolves the filled guides", resolved["data"])

    rule_file = repo / ".claude/rules/PROSEVOICE-PROTOCOL.md"
    preview = pv("rule", expect=("ok", 0))
    targets = {(t["kind"], t["path"]) for t in preview["data"]["targets"]}
    CHECK.ok(targets == {("file", str(rule_file.resolve())), ("block", str(agents_md.resolve()))}
             and preview["data"]["applied"] is False,
             "rule preview plans the Claude rule file and the AGENTS.md block", preview["data"])
    CHECK.ok(not rule_file.exists() and agents_md.read_bytes() == original_agents, "rule preview writes nothing")
    pv("rule", "--apply", expect=("ok", 0))
    protocol = (SKILL / "PROSEVOICE-PROTOCOL.md").read_text(encoding="utf-8").strip("\n")
    CHECK.ok(rule_file.read_text(encoding="utf-8").strip("\n") == protocol, "rule file holds the protocol")
    agents_text = agents_md.read_bytes()
    CHECK.ok(agents_text.startswith(original_agents) and BEGIN.encode() in agents_text
             and protocol.encode() in agents_text, "AGENTS.md keeps its content and gains the managed block")
    again = pv("rule", "--apply", expect=("ok", 0))
    CHECK.ok(again["data"]["changed"] == [] and agents_md.read_bytes() == agents_text,
             "rule --apply is idempotent", again["data"])
    after = pv("check", expect=("ok", 0))
    CHECK.ok(after["data"]["ready"] is True and all(r["state"] == "current" for r in after["data"]["rules"]),
             "check is ready with current rules", after["data"])

    essay = write(repo / "posts/essay.md", "# Essay\n\nA claim [needs-source].\n\n<!-- illus:map -->\n")
    blocked = pv("ready", essay, expect=("blocked", 1))
    CHECK.ok(sorted(d["code"] for d in blocked["diagnostics"]) == ["needs-source", "visual-unresolved"],
             "installed READY reports source and visual blockers", blocked)
    sidecar = pv("artifacts", essay, "--kind", "illustrations", "--apply", expect=("ok", 0))
    write(Path(sidecar["data"]["paths"]["illustrations"]), "## illus:map\nselected: no-image\n")
    essay.write_text("# Essay\n\nA sourced claim.[^1]\n\n<!-- illus:map -->\n\n[^1]: Source.\n", encoding="utf-8")
    clear = pv("ready", essay, expect=("ok", 0))
    CHECK.ok(clear["data"]["ready"] is True, "installed READY clears after resolution", clear["data"])


def main() -> int:
    print(f"prosevoice distribution check: source {REPO} (version {VERSION})")
    with tempfile.TemporaryDirectory(prefix="prosevoice-dist-") as temp:
        base = Path(temp).resolve()
        CHECK.surface_run("wheel", lambda: wheel_surface(base / "wheel"))
        CHECK.surface_run("copy", lambda: copy_surface(base / "copy"))
        CHECK.surface_run("install", lambda: install_surface(base / "install"))
    print(f"\nassertions passed: {CHECK.passed}; surfaces failed: {len(CHECK.failures)}; "
          f"unverified: {len(CHECK.unverified)}")
    for line in CHECK.failures:
        print(f"FAILED {line.splitlines()[0]}")
    for line in CHECK.unverified:
        print(f"UNVERIFIED {line.splitlines()[0]}")
    if CHECK.failures:
        return 1
    if CHECK.unverified:
        return 2
    print("all distribution checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
