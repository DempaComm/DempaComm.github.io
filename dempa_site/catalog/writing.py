"""Write the same generated catalog files from CLI and local administration."""

from collections.abc import Sequence
from pathlib import Path

from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.manifests.model import Paper
from dempa_site.paths import RepositoryPaths
from dempa_site.site.rendering import rendered_home_page


def write_catalog(
    paths: RepositoryPaths,
    papers: Sequence[tuple[Path, Paper]],
    *,
    home_page: str | None = None,
) -> None:
    paths.index.write_text(
        rendered_home_page(papers) if home_page is None else home_page,
        encoding="utf-8",
    )
    for manifest_path, paper in papers:
        (manifest_path.parent / "keywords.txt").write_text(
            rendered_keywords(paper), encoding="utf-8"
        )
