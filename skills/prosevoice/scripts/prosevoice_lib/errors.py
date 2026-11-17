"""Structured errors and diagnostics shared by every prosevoice command."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2


@dataclass
class Diagnostic:
    code: str
    message: str
    paths: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"code": self.code, "message": self.message, "paths": list(self.paths)}


def diagnostic(code: str, message: str, paths: list | tuple = ()) -> Diagnostic:
    return Diagnostic(code, message, [str(p) for p in paths])


class ProsevoiceError(Exception):
    """An invalid invocation, invalid configuration or operational failure (exit 2)."""

    def __init__(self, code: str, message: str, paths: list | tuple = ()):
        super().__init__(message)
        self.code = code
        self.message = message
        self.paths = [str(p) for p in paths]

    def to_diagnostic(self) -> Diagnostic:
        return Diagnostic(self.code, self.message, list(self.paths))


class ConfigError(ProsevoiceError):
    """Configuration could not be read or validated."""


class UsageError(ProsevoiceError):
    """The command line could not be parsed."""

    def __init__(self, message: str):
        super().__init__("usage", message)


def as_path_strings(paths: list[Path]) -> list[str]:
    return [str(p) for p in paths]
