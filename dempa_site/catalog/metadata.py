"""Collect reusable site metadata without rendering pages or touching files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dempa_site.config import MATH_SECTIONS
from dempa_site.manifests.model import Paper


PaperSource = tuple[Path, Paper]


@dataclass(frozen=True)
class SiteCatalog:
    """The validated papers and their derived navigation groupings."""

    selected: list[PaperSource]
    tags: dict[str, list[Paper]]
    math_sections: dict[str, list[Paper]]


def grouped_tags(selected: list[PaperSource]) -> dict[str, list[Paper]]:
    grouped: dict[str, list[Paper]] = {}
    for _, paper in selected:
        for tag in paper.tags:
            grouped.setdefault(tag, []).append(paper)
    return grouped


def grouped_math_sections(selected: list[PaperSource]) -> dict[str, list[Paper]]:
    grouped: dict[str, list[Paper]] = {section: [] for section in MATH_SECTIONS}
    for _, paper in selected:
        section = paper.math_section.strip() or "その他"
        grouped[section].append(paper)
    return grouped


def collect_metadata(selected: list[PaperSource]) -> SiteCatalog:
    """Build all groupings once for the later publication stages."""
    return SiteCatalog(
        selected=selected,
        tags=grouped_tags(selected),
        math_sections=grouped_math_sections(selected),
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
