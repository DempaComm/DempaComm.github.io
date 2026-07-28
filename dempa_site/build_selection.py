"""Select the smallest safe set of manifest-approved TeX builds."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import PurePosixPath

from dempa_site.manifests.model import Paper


def changed_paper_slugs(paths: Iterable[str]) -> set[str] | None:
    """Return affected paper slugs, or ``None`` when every paper must rebuild.

    An empty set means that an exact PDF cache may be used without compiling.
    Paths outside ``papers/<slug>/`` conservatively invalidate the whole build.
    """
    slugs: set[str] = set()
    for raw_path in paths:
        path = PurePosixPath(raw_path.strip())
        if not raw_path.strip():
            continue
        if len(path.parts) < 3 or path.parts[0] != "papers":
            return None
        slugs.add(path.parts[1])
    return slugs


def selected_build_papers(
    papers: Sequence[Paper], changed_paths: Iterable[str] | None = None
) -> list[Paper]:
    """Filter build-enabled papers by an optional Git change list."""
    changed = None if changed_paths is None else changed_paper_slugs(changed_paths)
    return [
        paper
        for paper in papers
        if paper.build.enabled and (changed is None or paper.slug in changed)
    ]
