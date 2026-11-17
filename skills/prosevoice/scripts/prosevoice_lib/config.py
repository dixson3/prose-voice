"""Strict layered configuration, guidance resolution, artifact paths and initialization.

Tiers, lowest to highest: builtin < user < project < CLI.

* user:    ``$XDG_CONFIG_HOME/prosevoice/config.json`` (``XDG_CONFIG_HOME`` must be absolute
           when set), else ``~/.config/prosevoice/config.json``
* project: ``<project>/.prosevoice/config.json``; the project is ``--project``, else the
           nearest Git root of the invocation directory, else the invocation directory.
           Essay commands without ``--project`` instead use the essay's nearest Git root,
           else the essay's directory (see :func:`config_for_essay`).
* CLI:     repeatable ``--set KEY=JSON`` overrides

Guidance merges per filename: the highest tier that sets a filename replaces that
filename's whole list; other filenames keep their own winning tier. ``artifacts.location``
merges as a scalar leaf. Relative guidance paths anchor to the user config directory
(user tier), the project root (project tier) or the invocation directory (CLI tier).
Malformed or invalid configuration is an error; a lower tier is never used instead.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import resource
from .errors import ConfigError, ProsevoiceError

SCHEMA_VERSION = 1
CONFIG_NAME = "config.json"
PROJECT_DIR = ".prosevoice"
APP_DIR = "prosevoice"
GUIDES = ("VOICE.md", "AUDIENCE.md", "ILLUSTRATIONS.md")
REQUIRED_GUIDES = ("VOICE.md", "AUDIENCE.md")
ARTIFACT_LOCATIONS = ("cache", "adjacent")
ARTIFACT_KINDS = (
    "curmudgeon", "steelman", "illustrations", "draft", "review", "ready",
    "copyedit", "provenance", "fact-check", "footnoter", "red-team", "cold-read",
)
TOP_LEVEL_KEYS = ("schema_version", "guidance", "artifacts")
ARTIFACT_KEYS = ("location",)
OVERRIDE_KEYS = tuple(f"guidance.{name}" for name in GUIDES) + ("artifacts.location",)
TIERS = ("builtin", "user", "project", "cli")
UNFILLED = "pv-template: unfilled"
CACHE_IGNORE = "/cache/"
CACHE_IGNORE_EQUIVALENTS = frozenset({"/cache/", "cache/", "/cache", "cache", "/cache/*", "cache/*", "/cache/**", "cache/**"})


# --------------------------------------------------------------------------- locations


def user_config_dir(env: Mapping[str, str] | None = None) -> Path:
    """The prosevoice user directory: holds the user config and user guides."""
    source: Mapping[str, str] = os.environ if env is None else env
    xdg = source.get("XDG_CONFIG_HOME")
    if xdg is not None and xdg != "":
        base = Path(xdg)
        if not base.is_absolute():
            raise ConfigError(
                "xdg-not-absolute",
                f"XDG_CONFIG_HOME must be an absolute path, got {xdg!r}",
                paths=[xdg],
            )
        return base / APP_DIR
    return Path.home() / ".config" / APP_DIR


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(out).resolve() if out else None


def select_project(explicit: str | Path | None, cwd: Path) -> tuple[Path, str]:
    """Return ``(project_root, how)`` where ``how`` is ``explicit``, ``git`` or ``cwd``."""
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = cwd / path
        if not path.is_dir():
            raise ConfigError("project-missing", f"--project {explicit} is not an existing directory", paths=[path])
        return path.resolve(), "explicit"
    root = git_root(cwd)
    if root is not None:
        return root, "git"
    return cwd.resolve(), "cwd"


# --------------------------------------------------------------------------- strict JSON


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name: str):
    raise ValueError(f"non-standard JSON constant {name}")


def loads_strict(text: str):
    """Parse JSON, rejecting duplicate keys and NaN/Infinity; every failure is a ValueError."""
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
    except (TypeError, RecursionError) as error:
        raise ValueError(str(error)) from error


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_guidance_list(value, where: str, path: Path | str | None) -> list[str]:
    paths = [path] if path else []
    if not isinstance(value, list):
        raise ConfigError("config-invalid", f"{where} must be a list of path strings", paths=paths)
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError("config-invalid", f"{where} entries must be nonempty path strings", paths=paths)
    return list(value)


def validate_location(value, where: str, path: Path | str | None) -> str:
    if value not in ARTIFACT_LOCATIONS or not isinstance(value, str):
        raise ConfigError(
            "config-invalid", f"{where} must be one of {', '.join(ARTIFACT_LOCATIONS)}",
            paths=[path] if path else [],
        )
    return value


def validate_document(data, path: Path) -> dict:
    """Validate one parsed config file and return it unchanged."""
    if not isinstance(data, dict):
        raise ConfigError("config-invalid", "config must be a JSON object", paths=[path])
    unknown = sorted(set(data) - set(TOP_LEVEL_KEYS))
    if unknown:
        raise ConfigError("config-unknown-key", f"unknown config keys: {', '.join(unknown)}", paths=[path])
    if "schema_version" not in data:
        raise ConfigError("config-invalid", "schema_version is required", paths=[path])
    version = data["schema_version"]
    if not _is_int(version) or version != SCHEMA_VERSION:
        raise ConfigError(
            "config-schema-version", f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}",
            paths=[path],
        )
    guidance = data.get("guidance", {})
    if not isinstance(guidance, dict):
        raise ConfigError("config-invalid", "guidance must be an object", paths=[path])
    unknown = sorted(set(guidance) - set(GUIDES))
    if unknown:
        raise ConfigError(
            "config-unknown-key", f"unknown guidance keys: {', '.join(unknown)}; allowed: {', '.join(GUIDES)}",
            paths=[path],
        )
    for name, value in guidance.items():
        validate_guidance_list(value, f"guidance.{name}", path)
    artifacts = data.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ConfigError("config-invalid", "artifacts must be an object", paths=[path])
    unknown = sorted(set(artifacts) - set(ARTIFACT_KEYS))
    if unknown:
        raise ConfigError("config-unknown-key", f"unknown artifacts keys: {', '.join(unknown)}", paths=[path])
    if "location" in artifacts:
        validate_location(artifacts["location"], "artifacts.location", path)
    return data


def read_config_file(path: Path) -> dict | None:
    """Return the validated config at ``path``, ``None`` when absent, or raise."""
    if not path.exists():
        return None
    if not path.is_file():
        raise ConfigError("config-unreadable", "config path is not a regular file", paths=[path])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigError("config-unreadable", f"cannot read config: {error}", paths=[path]) from error
    try:
        data = loads_strict(text)
    except ValueError as error:
        raise ConfigError("config-malformed", f"malformed config JSON: {error}", paths=[path]) from error
    return validate_document(data, path)


def parse_overrides(items: list[str] | None) -> dict[str, object]:
    """Parse ``KEY=JSON`` overrides into ``{dotted_key: value}``; unknown keys fail."""
    out: dict[str, object] = {}
    for item in items or []:
        key, sep, raw = item.partition("=")
        if not sep:
            raise ConfigError("override-invalid", f"--set {item!r} must have the form KEY=JSON")
        if key not in OVERRIDE_KEYS:
            raise ConfigError(
                "override-unknown-key", f"unknown --set key {key!r}; allowed: {', '.join(OVERRIDE_KEYS)}",
            )
        if key in out:
            raise ConfigError("override-duplicate", f"--set {key} is given more than once")
        try:
            value = loads_strict(raw)
        except ValueError as error:
            raise ConfigError("override-invalid", f"--set {key}: value is not valid JSON: {error}") from error
        if key == "artifacts.location":
            validate_location(value, f"--set {key}", None)
        else:
            validate_guidance_list(value, f"--set {key}", None)
        out[key] = value
    return out


# --------------------------------------------------------------------------- effective config


def expand_anchor(value: str, anchor: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = anchor / path
    return path.resolve()


@dataclass
class Leaf:
    value: object
    tier: str
    source: str | None
    anchor: str | None = None


@dataclass
class Config:
    cwd: Path
    project_root: Path
    project_selection: str
    user_dir: Path
    user_config: Path
    project_config: Path
    sources: dict[str, dict] = field(default_factory=dict)
    leaves: dict[str, Leaf] = field(default_factory=dict)
    overrides: list[str] = field(default_factory=list)
    env: Mapping[str, str] | None = None

    @property
    def project_dir(self) -> Path:
        return self.project_root / PROJECT_DIR

    @property
    def cache_dir(self) -> Path:
        return self.project_dir / "cache"

    @property
    def artifacts_location(self) -> str:
        return str(self.leaves["artifacts.location"].value)

    def guidance_values(self, name: str) -> list[str]:
        value = self.leaves[f"guidance.{name}"].value
        return [str(v) for v in value] if isinstance(value, list) else []

    def guidance_candidates(self, name: str) -> list[Path]:
        leaf = self.leaves[f"guidance.{name}"]
        anchor = Path(leaf.anchor) if leaf.anchor else self.cwd
        return [expand_anchor(value, anchor) for value in self.guidance_values(name)]

    def effective(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "guidance": {name: self.guidance_values(name) for name in GUIDES},
            "artifacts": {"location": self.artifacts_location},
        }

    def provenance(self) -> dict:
        return {
            key: {"tier": leaf.tier, "source": leaf.source, "anchor": leaf.anchor}
            for key, leaf in self.leaves.items()
        }

    def report(self) -> dict:
        return {
            "effective": self.effective(),
            "provenance": self.provenance(),
            "sources": self.sources,
            "roots": {
                "cwd": str(self.cwd),
                "project": str(self.project_root),
                "project_selection": self.project_selection,
                "user_dir": str(self.user_dir),
            },
            "resolved": {
                "guidance": {name: [str(p) for p in self.guidance_candidates(name)] for name in GUIDES},
                "project_dir": str(self.project_dir),
                "cache_dir": str(self.cache_dir),
            },
        }


def load_config(
    project: str | Path | None = None,
    overrides: list[str] | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """Resolve roots, read user and project config, apply overrides and record provenance."""
    cwd = (cwd or Path.cwd()).resolve()
    user_dir = user_config_dir(env)
    root, how = select_project(project, cwd)
    user_data = read_config_file(user_dir / CONFIG_NAME)
    project_data = read_config_file(root / PROJECT_DIR / CONFIG_NAME)
    return build_config(cwd, root, how, user_dir, user_data, project_data, overrides, env)


def build_config(
    cwd: Path,
    root: Path,
    how: str,
    user_dir: Path,
    user_data: dict | None,
    project_data: dict | None,
    overrides: list[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """Merge already-validated tier documents; ``load_config`` reads them from disk.

    Migration uses this directly to evaluate a translated project document before it is
    written, through the same precedence and anchoring rules as ordinary commands.
    """
    user_path = user_dir / CONFIG_NAME
    project_path = root / PROJECT_DIR / CONFIG_NAME
    parsed_overrides = parse_overrides(overrides)

    leaves: dict[str, Leaf] = {f"guidance.{name}": Leaf([], "builtin", None) for name in GUIDES}
    leaves["artifacts.location"] = Leaf("cache", "builtin", None)
    tiers = (
        ("user", user_data, str(user_path), user_dir),
        ("project", project_data, str(project_path), root),
    )
    for tier, data, source, anchor in tiers:
        if data is None:
            continue
        for name, value in data.get("guidance", {}).items():
            leaves[f"guidance.{name}"] = Leaf(list(value), tier, source, str(anchor))
        if "location" in data.get("artifacts", {}):
            leaves["artifacts.location"] = Leaf(data["artifacts"]["location"], tier, source)
    for key, value in parsed_overrides.items():
        anchor = str(cwd) if key.startswith("guidance.") else None
        leaves[key] = Leaf(value if not isinstance(value, list) else list(value), "cli", f"--set {key}", anchor)

    sources = {
        "user": {"path": str(user_path), "present": user_data is not None},
        "project": {"path": str(project_path), "present": project_data is not None},
        "cli": {"overrides": sorted(parsed_overrides)},
    }
    return Config(cwd, root, how, user_dir, user_path, project_path, sources, leaves,
                  list(overrides or []), env)


def config_for_essay(config: Config, essay: Path) -> Config:
    """The configuration governing one essay.

    An explicit ``--project`` applies to every essay. Otherwise the essay's own nearest Git
    root selects its project, so essays in different projects keep separate project
    configuration and policy; an essay outside any Git repository uses its own directory as
    the project, so its cache sits beside it in ``.prosevoice/cache/``. The derived essay
    directory may not exist yet (``artifacts --apply`` creates it), so it is not validated
    like ``--project``. CLI guidance overrides stay anchored to the invocation directory.
    """
    if config.project_selection == "explicit":
        return config
    essay = (essay if essay.is_absolute() else config.cwd / essay).resolve()
    start = essay.parent
    while not start.is_dir() and start != start.parent:
        start = start.parent  # the essay or its directory may not exist yet
    root = git_root(start)
    how = "essay-git" if root is not None else "essay-dir"
    if root is None:
        root = essay.parent
    if root == config.project_root:
        return config
    project_data = read_config_file(root / PROJECT_DIR / CONFIG_NAME)
    user_data = read_config_file(config.user_config)
    return build_config(config.cwd, root, how, config.user_dir, user_data, project_data,
                        config.overrides, config.env)


# --------------------------------------------------------------------------- guidance


def text_state(text: str) -> str:
    """``empty``, ``unfilled`` or ``ok`` for guide text that was read successfully."""
    if not text.strip():
        return "empty"
    if UNFILLED in text:
        return "unfilled"
    return "ok"


def file_state(path: Path) -> str:
    """``absent``, ``unreadable``, ``empty``, ``unfilled`` or ``ok``."""
    if not path.is_file():
        return "absent"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unreadable"
    return text_state(text)


def guide_candidates(config: Config, name: str) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = [("configured", p) for p in config.guidance_candidates(name)]
    out.append(("project", config.project_dir / name))
    out.append(("user", config.user_dir / name))
    return out


def resolve_guidance(config: Config, state_of=None) -> dict:
    """Per guide, the first usable candidate plus every path tried and its state.

    ``state_of`` replaces :func:`file_state`; migration passes one that also sees staged
    bytes so a preview can be checked through this same resolver.
    """
    state_of = state_of or file_state
    result = {}
    for name in GUIDES:
        tried, chosen = [], None
        for level, path in guide_candidates(config, name):
            state = state_of(path)
            tried.append({"level": level, "path": str(path), "state": state})
            if state == "ok" and chosen is None:
                chosen = {"level": level, "path": str(path)}
        result[name] = {"required": name in REQUIRED_GUIDES, "resolved": chosen, "tried": tried}
    return result


# --------------------------------------------------------------------------- artifacts


def artifact_paths(config: Config, essay: Path) -> dict[str, Path]:
    """Intermediate artifact paths for ``essay``; never touches the filesystem."""
    essay = (essay if essay.is_absolute() else config.cwd / essay).resolve()
    if config.artifacts_location == "adjacent":
        directory = essay.parent
    else:
        try:
            relative = essay.relative_to(config.project_root)
        except ValueError as error:
            raise ProsevoiceError(
                "essay-outside-project",
                "cache artifacts require the essay to be inside the selected project",
                paths=[essay, config.project_root],
            ) from error
        directory = config.cache_dir / relative.parent
    return {kind: directory / f"{essay.stem}.{kind}.md" for kind in ARTIFACT_KINDS}


def ensure_cache_ignore(project_dir: Path) -> bool:
    """Merge the cache ignore line into ``.prosevoice/.gitignore``; True when written."""
    ignore = project_dir / ".gitignore"
    text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    if any(line.strip() in CACHE_IGNORE_EQUIVALENTS for line in text.splitlines()):
        return False
    project_dir.mkdir(parents=True, exist_ok=True)
    sep = "\n" if text and not text.endswith("\n") else ""
    ignore.write_text(f"{text}{sep}{CACHE_IGNORE}\n", encoding="utf-8")
    return True


def prepare_artifacts(config: Config, essay: Path) -> dict:
    """Create the artifact directory; in cache mode also ensure the ignore rule."""
    paths = artifact_paths(config, essay)
    ignore_written = False
    if config.artifacts_location == "cache":
        ignore_written = ensure_cache_ignore(config.project_dir)
    next(iter(paths.values())).parent.mkdir(parents=True, exist_ok=True)
    return {"paths": paths, "ignore_written": ignore_written}


# --------------------------------------------------------------------------- init


def init(config_scope: str, *, project: str | Path | None = None, overrides: list[str] | None = None,
         illustrations: bool = False, cwd: Path | None = None,
         env: Mapping[str, str] | None = None) -> dict:
    """Seed missing config and blank guides without overwriting anything.

    Existing configuration must be valid before anything is written.
    """
    config = load_config(project, overrides, cwd, env)
    if config_scope == "project":
        dest, config_path = config.project_dir, config.project_config
    elif config_scope == "user":
        dest, config_path = config.user_dir, config.user_config
    else:
        raise ProsevoiceError("usage", f"unknown init scope {config_scope!r}")
    names = list(REQUIRED_GUIDES) + (["ILLUSTRATIONS.md"] if illustrations else [])
    templates = {name: resource("templates", name) for name in names}
    created: list[str] = []
    kept: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        kept.append(str(config_path))
    else:
        config_path.write_text(json.dumps({"schema_version": SCHEMA_VERSION}, indent=2) + "\n", encoding="utf-8")
        created.append(str(config_path))
    for name in names:
        target = dest / name
        if target.exists():
            kept.append(str(target))
        else:
            shutil.copyfile(templates[name], target)
            created.append(str(target))
    ignore_written = False
    if config_scope == "project":
        ignore_written = ensure_cache_ignore(dest)
    return {
        "scope": config_scope,
        "directory": str(dest),
        "created": created,
        "kept": kept,
        "ignore_updated": ignore_written,
        "illustrations": illustrations,
    }
