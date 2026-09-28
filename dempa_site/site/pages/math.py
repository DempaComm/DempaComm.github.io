"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

from dempa_site.catalog.metadata import grouped_math_sections
from dempa_site.config import BLOG_ONLY_KIND, MathTopic, MATH_SECTION_DETAILS, MATH_SECTIONS, MATH_TOPICS, SITE_TITLE_TOP
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import has_pdf, is_pdf_alias
from dempa_site.site.layout import page_head, site_footer, site_header


def rendered_math_index_item(
    manifest: Paper, prefix: str = "../"
) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = html.escape(str(manifest["published_at"])[:10])
    file_links = (
        [f'<a href="{prefix}papers/{slug}/main.pdf">PDF</a>']
        if has_pdf(manifest)
        else []
    )
    for entry in manifest.files:
        if not entry.public or not entry.label:
            continue
        if is_pdf_alias(manifest, entry.path):
            continue
        path = html.escape(entry.path, quote=True)
        label = html.escape(entry.label)
        if manifest.build.enabled and entry.path == "published.pdf":
            label = "初出時のPDF"
        file_links.append(f'<a href="{prefix}papers/{slug}/{path}">{label}</a>')
    if manifest.html_version is not None:
        html_path = html.escape(manifest.html_version.path, quote=True)
        html_href = f"{prefix}papers/{slug}/{html_path}"
        if html_href not in "".join(file_links):
            file_links.append(f'<a href="{html_href}">HTML本文</a>')
        file_links.append(
            f'<a href="{prefix}statements/years/{slug[:4]}/?paper={slug}">定理等索引</a>'
        )
    if manifest["kind"] == BLOG_ONLY_KIND and manifest["original_url"]:
        original_url = html.escape(manifest["original_url"], quote=True)
        file_links.append(f'<a href="{original_url}">電波通信で読む</a>')
    tag_links = "\n".join(
        f'              <a class="paper-tag" href="{prefix}tags/{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    return f"""          <li class="math-index-item">
            <h3><a href="{prefix}papers/{slug}/">{title}</a></h3>
            <p>{summary}</p>
            <div class="math-index-meta">
              <time datetime="{published_date}">{published_date}</time>
              <span>{' · '.join(file_links)}</span>
            </div>
            <div class="math-index-tags" aria-label="電波通信のタグ">
{tag_links}
            </div>
          </li>"""


def representative_math_tags(papers: Sequence[Paper]) -> list[str]:
    counts: dict[str, int] = {}
    for paper in papers:
        for tag in paper["tags"]:
            if tag == "数学":
                continue
            counts[tag] = counts.get(tag, 0) + 1
    return [
        tag
        for tag, _ in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]


def papers_for_math_topic(topic: MathTopic, papers: Sequence[Paper]) -> list[Paper]:
    """Select a topic across primary sections using its subject tags."""
    tags = set(topic.tags)
    return [
        paper
        for paper in papers
        if tags.intersection(paper.tags)
    ]


def _rendered_topic_cards(
    papers: Sequence[Paper], *, section: str = "", prefix: str = "topics/"
) -> str:
    topics = [
        topic for topic in MATH_TOPICS if not section or topic.section == section
    ]
    return "\n".join(
        f"""      <a class="math-topic-card" href="{prefix}{topic.slug}/">
        <span class="section-number">TOPIC {index:02d}</span>
        <strong>{html.escape(topic.title)}</strong>
        <span>{html.escape(topic.description)}</span>
        <span class="math-topic-count">{len(papers_for_math_topic(topic, papers))}件</span>
      </a>"""
        for index, topic in enumerate(topics, start=1)
    )


def _rendered_year_sections(papers: Sequence[Paper], prefix: str) -> str:
    by_year: dict[int, list[Paper]] = {}
    for paper in papers:
        by_year.setdefault(paper.year, []).append(paper)
    if not by_year:
        return f"""      <section class="math-empty">
        <p>このテーマには、まだ公開原稿がありません。</p>
        <a href="{prefix}archive/">全原稿アーカイブを見る</a>
      </section>"""
    return "\n".join(
        f"""      <section class="math-index-section" aria-labelledby="year-{year}">
        <div class="math-index-heading">
          <h2 id="year-{year}">{year}年</h2>
          <span>{len(year_papers)}件</span>
        </div>
        <ul class="math-index-list">
{chr(10).join(rendered_math_index_item(paper, prefix) for paper in reversed(year_papers))}
        </ul>
      </section>"""
        for year, year_papers in sorted(by_year.items(), reverse=True)
    )


def rendered_math_page(selected: Sequence[tuple[Path, Paper]]) -> str:
    grouped = grouped_math_sections(selected)
    all_papers = [paper for _, paper in selected]
    directory_cards = "\n".join(
        f"""      <a class="math-directory-card" href="{MATH_SECTION_DETAILS[section]['slug']}/">
        <span class="section-number">{index:02d}</span>
        <strong>{html.escape(section)}</strong>
        <span>{html.escape(MATH_SECTION_DETAILS[section]['description'])}</span>
        <span class="math-directory-count">{len(grouped[section])}件</span>
        <span class="math-directory-tags">{
            " · ".join(html.escape(tag) for tag in representative_math_tags(grouped[section]))
            or "記事の追加待ち"
        }</span>
      </a>"""
        for index, section in enumerate(MATH_SECTIONS, start=1)
    )
    topic_cards = _rendered_topic_cards(all_papers)
    header = site_header(
        eyebrow_html="MATHEMATICS DIRECTORY",
        title_html="数学記事総覧",
        lead_html=f"分野別総覧への入口です。現在公開している全{len(selected)}原稿を、四つの主分類からたどれます。",
        prefix="../",
        current_navigation="math",
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"数学記事総覧 — {SITE_TITLE_TOP}", f"{SITE_TITLE_TOP}の数学記事を分野別総覧へ案内する総合目次です。", "/math/", "../styles.css")}
</head>
<body class="math-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
    <nav class="math-directory-grid" aria-label="数学分野別総覧">
{directory_cards}
    </nav>
    <section class="math-topic-directory" aria-labelledby="math-topics-title">
      <div class="section-heading">
        <h2 id="math-topics-title">テーマから探す</h2>
        <p>主分類をまたいで、電波通信のタグから原稿を集めています。一つの原稿が複数のテーマに現れることがあります。</p>
      </div>
      <nav class="math-topic-grid" aria-label="数学テーマ別総覧">
{topic_cards}
      </nav>
    </section>
    <section class="archive-note" aria-labelledby="math-guide-title">
      <p class="section-number">GUIDE</p>
      <h2 id="math-guide-title">分類について</h2>
      <p>各原稿は主分類を一つ持ちます。分野別ページでは公開年ごとの一覧と、電波通信から引き継いだタグを併記しています。</p>
    </section>
  </main>
{site_footer()}
</body>
</html>
"""


def rendered_math_section_page(
    section: str, papers: Sequence[Paper], all_papers: Sequence[Paper] | None = None
) -> str:
    details = MATH_SECTION_DETAILS[section]
    year_sections = _rendered_year_sections(papers, "../../")
    section_topics = ""
    if any(topic.section == section for topic in MATH_TOPICS):
        section_topics = f"""    <section class="math-topic-directory" aria-labelledby="section-topics-title">
      <div class="section-heading">
        <h2 id="section-topics-title">この分野のテーマ</h2>
        <p>関連テーマから探せます。テーマ別一覧には、ほかの主分類の原稿も含まれます。</p>
      </div>
      <nav class="math-topic-grid" aria-label="{html.escape(section)}のテーマ">
{_rendered_topic_cards(all_papers if all_papers is not None else papers, section=section, prefix="../topics/")}
      </nav>
    </section>"""
    description = str(details["description"])
    slug = str(details["slug"])
    header = site_header(
        eyebrow_html="MATHEMATICS SECTION",
        title_html=html.escape(section),
        lead_html=f"{html.escape(description)} 現在{len(papers)}件です。",
        prefix="../../",
        current_navigation="math",
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{section}の記事総覧 — {SITE_TITLE_TOP}", description, f"/math/{slug}/", "../../styles.css")}
</head>
<body class="math-page math-section-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
    <p class="directory-back"><a href="../">数学記事総覧へ戻る</a></p>
{section_topics}
{year_sections}
  </main>
{site_footer()}
</body>
</html>
"""


def rendered_math_topic_page(topic: MathTopic, papers: Sequence[Paper]) -> str:
    title = topic.title
    description = topic.description
    slug = topic.slug
    section = topic.section
    section_slug = str(MATH_SECTION_DETAILS[section]["slug"])
    header = site_header(
        eyebrow_html="MATHEMATICS TOPIC",
        title_html=html.escape(title),
        lead_html=f"{html.escape(description)} 現在{len(papers)}件です。",
        prefix="../../../",
        current_navigation="math",
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{title}の記事総覧 — {SITE_TITLE_TOP}", description, f"/math/topics/{slug}/", "../../../styles.css")}
</head>
<body class="math-page math-topic-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
    <p class="directory-back"><a href="../../">数学記事総覧へ戻る</a> · 関連分野：<a href="../../{section_slug}/">{html.escape(section)}</a></p>
    <p>このテーマのタグを持つ原稿を、主分類に関係なく掲載しています。</p>
{_rendered_year_sections(papers, "../../../")}
  </main>
{site_footer()}
</body>
</html>
"""
