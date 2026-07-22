"""Collect reusable site metadata without rendering pages or touching files."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dempa_site.config import MATH_SECTIONS
from dempa_site.manifests.model import Paper


PaperSource = tuple[Path, Paper]


@dataclass(frozen=True)
class SiteCatalog:
    """The validated papers and their derived navigation groupings."""

    selected: tuple[PaperSource, ...]
    tags: Mapping[str, tuple[Paper, ...]]
    math_sections: Mapping[str, tuple[Paper, ...]]


def grouped_tags(selected: Sequence[PaperSource]) -> dict[str, list[Paper]]:
    grouped: dict[str, list[Paper]] = {}
    for _, paper in selected:
        for tag in paper.tags:
            grouped.setdefault(tag, []).append(paper)
    return grouped


def grouped_math_sections(selected: Sequence[PaperSource]) -> dict[str, list[Paper]]:
    grouped: dict[str, list[Paper]] = {section: [] for section in MATH_SECTIONS}
    for _, paper in selected:
        section = paper.math_section.strip() or "その他"
        grouped[section].append(paper)
    return grouped


def collect_metadata(selected: Sequence[PaperSource]) -> SiteCatalog:
    """Build immutable groupings once for publication and feature stages."""
    selected_tuple = tuple(selected)
    tags = {
        tag: tuple(papers)
        for tag, papers in grouped_tags(selected_tuple).items()
    }
    math_sections = {
        section: tuple(papers)
        for section, papers in grouped_math_sections(selected_tuple).items()
    }
    return SiteCatalog(
        selected=selected_tuple,
        tags=MappingProxyType(tags),
        math_sections=MappingProxyType(math_sections),
    )


def rendered_keywords(paper: Paper | Mapping[str, Any]) -> str:
    lines = [
        "# タイトル",
        str(paper["title"]),
        "",
        "# 電波通信のタグ",
        *paper["tags"],
        "",
        "# 検索キーワード",
        *paper["keywords"],
        "",
    ]
    return "\n".join(lines)
