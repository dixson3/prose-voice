"""prosevoice support package: configuration, resources and the JSON command line."""

from __future__ import annotations

from pathlib import Path

__version__ = "1.1.0"

_PACKAGE_DIR = Path(__file__).resolve().parent


def skill_root() -> Path:
    """Return the directory holding the skill's bundled resources.

    A wheel installs those resources under ``prosevoice_lib/_skill/``; a source or
    copied skill tree keeps them two levels above this package
    (``skills/prosevoice/scripts/prosevoice_lib`` -> ``skills/prosevoice``). The
    current working directory is never consulted.
    """
    packaged = _PACKAGE_DIR / "_skill"
    if packaged.is_dir():
        return packaged
    return _PACKAGE_DIR.parents[1]


def resource_mode() -> str:
    """``packaged`` when resources come from the wheel's ``_skill/`` tree, else ``source``."""
    return "packaged" if (_PACKAGE_DIR / "_skill").is_dir() else "source"


def resource(*parts: str) -> Path:
    """Return a bundled resource path, raising when the resource is not shipped."""
    from .errors import ProsevoiceError

    path = skill_root().joinpath(*parts)
    if not path.exists():
        raise ProsevoiceError(
            "resource-missing",
            f"bundled resource {'/'.join(parts)} is missing from {skill_root()}",
            paths=[path],
        )
    return path
