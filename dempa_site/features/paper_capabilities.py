"""Shared derived capabilities used by multiple exploration features."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.statements import KIND_ORDER, indexed_statements


@dataclass(frozen=True)
class PaperCapabilities:
    html_path: str
    statement_counts: Mapping[str, int]
    correction_count: int

    @property
    def statement_count(self) -> int:
        return sum(self.statement_counts.values())


def paper_capabilities(catalog: SiteCatalog) -> Mapping[str, PaperCapabilities]:
    """Return one stable enrichment record per paper."""
    counts: dict[str, Counter[str]] = {}
    for statement in indexed_statements(catalog):
        counts.setdefault(statement.paper_slug, Counter())[statement.kind] += 1
    result = {}
    for _, paper in catalog.selected:
        version = paper.html_version
        result[paper.slug] = PaperCapabilities(
            html_path=version.path if version is not None else "",
            statement_counts=MappingProxyType(
                {kind: counts.get(paper.slug, Counter())[kind] for kind in KIND_ORDER}
            ),
            correction_count=len(paper.corrections),
        )
    return MappingProxyType(result)
