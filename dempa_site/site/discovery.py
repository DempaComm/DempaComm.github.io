"""Small machine-readable catalog for the discovery.js reading picker."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.manifests.model import Paper


def paper_summary_data(
    selected: Sequence[tuple[Path, Paper]],
) -> dict[str, object]:
    """Return the stable, public-only fields needed by the home-page picker."""
    papers = []
    for _, paper in selected:
        papers.append(
            {
                "slug": paper.slug,
                "title": paper.title,
                "published_at": paper.published_at_text[:10],
                "year": paper.year,
                "math_section": paper.math_section,
                "summary": paper.summary,
                "tags": list(paper.tags),
            }
        )
    return {"schema_version": 1, "papers": papers}
