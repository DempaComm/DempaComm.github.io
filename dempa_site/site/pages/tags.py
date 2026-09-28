"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

import html
from collections.abc import Sequence
from urllib.parse import quote

from dempa_site.config import BLOG_ONLY_KIND, SITE_TITLE_TOP
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import (
    original_article_action,
    public_file_actions,
)
from dempa_site.site.layout import page_head, site_footer, site_header


def rendered_tag_page_paper(manifest: Paper) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    published_date = html.escape(str(manifest["published_at"])[:10])
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    year = int(manifest["year"])
    tag_chips = "\n".join(
        f'            <a class="paper-tag" href="../{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    actions = public_file_actions(
        manifest, f"../../papers/{slug}/", "            "
    )
    original_action = original_article_action(
        manifest, "            ", primary=manifest["kind"] == BLOG_ONLY_KIND
    )
    if original_action:
        actions.append(original_action)
    kind_badge = (
        f"<span>{BLOG_ONLY_KIND}</span>"
        if manifest["kind"] == BLOG_ONLY_KIND
        else ""
    )
    action_label = "ブログ記事へのリンク" if manifest["kind"] == BLOG_ONLY_KIND else "ファイル"
    return f"""        <article class="tag-page-paper">
          <div class="paper-meta"><span>初出 <a class="paper-year-link" href="../../archive/{year}/" aria-label="{year}年の記事一覧">{published_date}</a></span>{kind_badge}</div>
          <h3><a href="../../papers/{slug}/">{title}</a></h3>
          <p>{summary}</p>
          <div class="paper-tags" aria-label="電波通信のタグ">
{tag_chips}
          </div>
          <nav class="paper-actions" aria-label="{html.escape(manifest['title'], quote=True)}の{action_label}">
{chr(10).join(actions)}
          </nav>
        </article>"""


def rendered_tag_page(tag: str, papers: Sequence[Paper]) -> str:
    by_year: dict[int, list[Paper]] = {}
    for paper in papers:
        by_year.setdefault(int(paper["year"]), []).append(paper)
    year_sections = "\n".join(
        f"""      <section class="tag-year-section" aria-labelledby="year-{year}">
        <h2 id="year-{year}">{year}年 <span>{len(year_papers)}件</span></h2>
        <div class="tag-page-papers">
{chr(10).join(rendered_tag_page_paper(paper) for paper in year_papers)}
        </div>
      </section>"""
        for year, year_papers in sorted(by_year.items(), reverse=True)
    )
    escaped_tag = html.escape(tag)
    description = f"電波通信のタグ「{tag}」が付いた公開原稿の一覧です。"
    header = site_header(
        eyebrow_html="TAG ARCHIVE",
        title_html=escaped_tag,
        lead_html=f"電波通信でこのタグが付けられていた公開原稿、全{len(papers)}件。",
        prefix="../../",
        current_navigation="tags",
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{tag}の記事 — {SITE_TITLE_TOP}", description, f"/tags/{quote(tag, safe='')}/", "../../styles.css")}
</head>
<body class="tag-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
{year_sections}
  </main>
{site_footer()}
</body>
</html>
"""
