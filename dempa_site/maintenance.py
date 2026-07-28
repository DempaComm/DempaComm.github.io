"""Find and remove reproducible local artifacts without touching paper sources."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.manifests.model import Paper


TEX_INTERMEDIATE_PATTERNS = (
    "*.aux",
    "*.bbl",
    "*.blg",
    "*.dvi",
    "*.fdb_latexmk",
    "*.fls",
    "*.log",
    "*.out",
    "*.synctex.gz",
    "*.toc",
)
APPROVED_PRIVACY_STATUSES = frozenset({"reviewed", "overridden"})


@dataclass(frozen=True)
class CleanupGroup:
    name: str
    paths: tuple[Path, ...]
    bytes: int


@dataclass(frozen=True)
class LocalCleanupPlan:
    groups: tuple[CleanupGroup, ...]

    @property
    def path_count(self) -> int:
        return sum(len(group.paths) for group in self.groups)

    @property
    def bytes(self) -> int:
        return sum(group.bytes for group in self.groups)


def _path_size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(
        candidate.lstat().st_size
        for candidate in path.rglob("*")
        if candidate.is_file() or candidate.is_symlink()
    )


def _cleanup_group(name: str, paths: Iterable[Path]) -> CleanupGroup:
    selected = tuple(sorted(set(paths)))
    return CleanupGroup(
        name=name,
        paths=selected,
        bytes=sum(_path_size(path) for path in selected),
    )


def _reviewed_privacy_directories(
    review_root: Path, papers: Iterable[Paper]
) -> tuple[Path, ...]:
    reviewed_hashes = {
        review.source_sha256
        for paper in papers
        for review in paper.privacy_reviews
        if review.status in APPROVED_PRIVACY_STATUSES
    }
    if not review_root.is_dir():
        return ()
    return tuple(
        path
        for path in review_root.iterdir()
        if path.is_dir() and path.name in reviewed_hashes
    )


def local_cleanup_plan(
    root: Path,
    papers: Iterable[Paper],
    *,
    include_experiments: bool = False,
) -> LocalCleanupPlan:
    root = root.resolve()
    paper_root = root / "papers"
    numbered_sites = (
        path
        for path in root.iterdir()
        if path.is_dir() and re.fullmatch(r"_site [0-9]+", path.name)
    )
    tex_intermediates = (
        path
        for pattern in TEX_INTERMEDIATE_PATTERNS
        for path in paper_root.rglob(pattern)
        if path.is_file()
    )
    disposable_files = (
        path
        for path in (root / ".DS_Store", paper_root / ".DS_Store")
        if path.is_file()
    )
    temporary_dirs = (
        path for path in (root / "tmp",) if path.is_dir()
    )
    groups = [
        _cleanup_group("numbered-site-copies", numbered_sites),
        _cleanup_group("tex-intermediates", tex_intermediates),
        _cleanup_group(
            "approved-privacy-reports",
            _reviewed_privacy_directories(root / ".privacy-review", papers),
        ),
        _cleanup_group("disposable-files", disposable_files),
        _cleanup_group("temporary-directories", temporary_dirs),
    ]
    experiments = root / "_experiments"
    if include_experiments and experiments.is_dir():
        groups.append(_cleanup_group("experiment-output", (experiments,)))
    return LocalCleanupPlan(tuple(group for group in groups if group.paths))


def apply_local_cleanup(plan: LocalCleanupPlan) -> None:
    for group in plan.groups:
        for path in group.paths:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
        value /= 1024
    raise AssertionError("unreachable")
