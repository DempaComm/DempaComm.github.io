"""Repository paths and portable relative-path handling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Type

from .errors import DempaSiteError


@dataclass(frozen=True)
class RepositoryPaths:
    """Paths derived from a replaceable repository root."""

    root: Path

    @classmethod
    def from_environment(
        cls, environment_variable: str, script_file: str
    ) -> "RepositoryPaths":
        default_root = Path(script_file).resolve().parents[1]
        root = Path(os.environ.get(environment_variable, default_root)).resolve()
        return cls(root=root)

    @property
    def papers(self) -> Path:
        return self.root / "papers"

    @property
    def index(self) -> Path:
        return self.root / "index.html"

    @property
    def search_script(self) -> Path:
        return self.root / "search.js"

    @property
    def privacy_review(self) -> Path:
        return self.root / ".privacy-review"


def safe_relative_path(
    value: str, error_type: Type[DempaSiteError] = DempaSiteError
) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise error_type(f"unsafe relative path: {value}")
    return path


def is_safe_relative_path(value: str, *, allow_empty: bool = False) -> bool:
    if not value:
        return allow_empty
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts

