# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Project configuration shared by prose-voice's installed helpers."""
import json
import subprocess
from pathlib import Path

GUIDANCE = ("VOICE.md", "AUDIENCE.md", "ILLUSTRATIONS.md")


def project_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip()).resolve()


def load_config(root: Path | None) -> dict:
    """Validate optional project config; never silently ignore invalid settings."""
    path = root / ".prose-voice/config.json" if root else None
    try:
        config = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read .prose-voice/config.json: {error}") from error
    if not isinstance(config, dict) or set(config) - {"guidance", "artifacts"}:
        raise ValueError(".prose-voice/config.json must contain only guidance and artifacts objects")
    guidance = config.get("guidance", {})
    if not isinstance(guidance, dict) or set(guidance) - set(GUIDANCE):
        raise ValueError("guidance keys must be VOICE.md, AUDIENCE.md or ILLUSTRATIONS.md")
    for name, paths in guidance.items():
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p.strip() for p in paths):
            raise ValueError(f"guidance.{name} must be an ordered list of file paths")
    artifacts = config.get("artifacts", {})
    if not isinstance(artifacts, dict) or set(artifacts) - {"location"}:
        raise ValueError("artifacts must contain only location")
    if artifacts.get("location", "cache") not in ("cache", "adjacent"):
        raise ValueError("artifacts.location must be cache or adjacent")
    return config


def extra_guidance(root: Path | None, name: str) -> list[Path]:
    config = load_config(root)
    paths = []
    for value in config.get("guidance", {}).get(name, []):
        path = Path(value).expanduser()
        if not path.is_absolute():
            if root is None:
                raise ValueError("relative guidance paths require a project root")
            path = root / path
        paths.append(path.resolve())
    return paths


def artifact_paths(essay: Path, root: Path | None = None) -> dict[str, Path]:
    essay = essay.resolve()
    root = root.resolve() if root else project_root(essay.parent)
    config = load_config(root)
    if config.get("artifacts", {}).get("location", "cache") == "adjacent":
        directory = essay.parent
    else:
        base = root or essay.parent
        try:
            relative = essay.relative_to(base)
        except ValueError as error:
            raise ValueError("essay must be inside the selected project") from error
        directory = base / ".prose-voice/cache" / relative.parent
    return {kind: directory / f"{essay.stem}.{kind}.md"
            for kind in ("curmudgeon", "steelman", "illustrations", "draft", "review", "ready",
                         "copyedit", "provenance", "fact-check", "footnoter", "red-team", "cold-read")}


def prepare_artifacts(essay: Path, root: Path | None = None) -> dict[str, Path]:
    """Create the chosen artifact directory and ignore cache content locally."""
    essay = essay.resolve()
    root = root.resolve() if root else project_root(essay.parent)
    paths = artifact_paths(essay, root)
    if load_config(root).get("artifacts", {}).get("location", "cache") == "cache":
        pv = (root or essay.parent) / ".prose-voice"
        pv.mkdir(parents=True, exist_ok=True)
        ignore = pv / ".gitignore"
        text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        if "/cache/" not in text.splitlines():
            ignore.write_text(text + ("\n" if text and not text.endswith("\n") else "") + "/cache/\n", encoding="utf-8")
    next(iter(paths.values())).parent.mkdir(parents=True, exist_ok=True)
    return paths
