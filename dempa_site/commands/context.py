"""Explicit repository context shared by command adapters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.errors import PaperToolError
from dempa_site.manifests.loader import load_manifest_directory
from dempa_site.manifests.model import Paper
from dempa_site.paths import RepositoryPaths, safe_relative_path
from dempa_site.protection.hashes import protected_file_errors
from dempa_site.site.rendering import rendered_home_page


@dataclass(frozen=True)
class CommandContext:
    paths: RepositoryPaths
    code_root: Path
    review_root: Path

    def manifests(self, slugs: Iterable[str] | None = None) -> list[tuple[Path, Paper]]:
        return load_manifest_directory(self.paths.papers, slugs, PaperToolError)

    def verify_one(self, manifest_path: Path, paper: Paper) -> list[str]:
        return protected_file_errors(manifest_path, paper, PaperToolError)

    def safe_relative_path(self, value: str) -> Path:
        return safe_relative_path(value, PaperToolError)

    def rendered_index(self) -> str:
        return rendered_home_page(self.manifests())
