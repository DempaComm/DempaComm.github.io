"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path

from dempa_site.catalog.metadata import grouped_tags
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import tag_href


def rendered_tag_index(selected: Sequence[tuple[Path, Paper]]) -> str:
    grouped = grouped_tags(selected)
    return "\n".join(
        f'      <a class="tag-index-item" href="{tag_href(tag)}">'
        f"<span>{html.escape(tag)}</span><span>{len(papers)}件</span></a>"
        for tag, papers in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    )


def rendered_year_groups(
    selected: Sequence[tuple[Path, Paper]], prefix: str = ""
) -> str:
    grouped: dict[int, list[Paper]] = {}
    for _, manifest in selected:
        grouped.setdefault(int(manifest["year"]), []).append(manifest)

    groups: list[str] = []
    for year in sorted(grouped, reverse=True):
        papers = grouped[year]
        article_links = "\n".join(
            "          <li>"
            f'<a href="{prefix}papers/{html.escape(paper["slug"], quote=True)}/">'
            f'<time datetime="{html.escape(str(paper["published_at"])[:10], quote=True)}">'
            f'{html.escape(str(paper["published_at"])[:10])}</time> '
            f'{html.escape(paper["title"])}</a></li>'
            for paper in papers
        )
        groups.append(
            f"""      <details class="year-group" id="year-{year}">
        <summary><span>{year}年</span><span>{len(papers)}件</span></summary>
        <ul>
{article_links}
        </ul>
      </details>"""
        )
    return "\n\n".join(groups)
