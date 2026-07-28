"""Render the archive directory and its year pages without performing I/O."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.config import SITE_TITLE_ATTRIBUTE, SITE_TITLE_FORMAL, SITE_TITLE_TOP
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import paper_card
from dempa_site.site.layout import page_head, site_navigation
from dempa_site.site.pages.common import rendered_tag_index


def grouped_archive_years(
    selected: Sequence[tuple[Path, Paper]],
) -> dict[int, list[Paper]]:
    grouped: dict[int, list[Paper]] = {}
    for _, paper in selected:
        grouped.setdefault(int(paper.year), []).append(paper)
    return dict(sorted(grouped.items(), reverse=True))


def _year_directory(selected: Sequence[tuple[Path, Paper]]) -> str:
    return "\n".join(
        f'''      <a class="explore-card" href="{year}/">
        <span class="section-number">{year}</span>
        <strong>{year}年</strong>
        <span>{len(papers)}件</span>
      </a>'''
        for year, papers in grouped_archive_years(selected).items()
    )


def rendered_archive_page(selected: Sequence[tuple[Path, Paper]]) -> str:
    """Render the compact archive hub; papers live on individual year pages."""
    description = (
        f"{SITE_TITLE_TOP}で公開している全{len(selected)}原稿を、"
        "公開年とタグからたどる総合アーカイブです。"
    )
    return f'''<!doctype html>
<html lang="ja">
<head>
{page_head(f"全原稿アーカイブ — {SITE_TITLE_TOP}", description, "/archive/", "../styles.css")}
</head>
<body class="archive-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">COMPLETE ARCHIVE</p>
      <h1>全原稿アーカイブ</h1>
      <p class="lead">全{len(selected)}原稿を、公開年またはタグからたどれます。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "archive")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <section class="year-directory" aria-labelledby="years-title">
      <div class="section-heading"><div><p class="section-number">01</p><h2 id="years-title">公開年から選ぶ</h2></div><p>各年のページで、その年の原稿だけを検索できます。</p></div>
      <nav class="explore-grid archive-year-grid" aria-label="公開年別記事一覧">
{_year_directory(selected)}
      </nav>
    </section>
    <section class="tag-directory" aria-labelledby="tags-title">
      <div class="section-heading"><div><p class="section-number">02</p><h2 id="tags-title">タグ索引</h2></div><p>タグごとの専用ページへ移動します。</p></div>
      <nav class="tag-index" aria-label="タグ索引">
{rendered_tag_index(selected).replace('href="tags/', 'href="../tags/')}
      </nav>
    </section>
    <section aria-labelledby="archive-search-title">
      <div class="section-heading"><div><p class="section-number">03</p><h2 id="archive-search-title">全文から探す</h2></div><p>年をまたぐ検索には全文検索を利用できます。</p></div>
      <p><a class="primary-action" href="../search/">全文検索を開く</a></p>
    </section>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
'''


def rendered_archive_year_page(year: int, papers: Sequence[Paper]) -> str:
    """Render one searchable year of the archive."""
    cards = "\n\n".join(paper_card(paper, "../../") for paper in reversed(papers))
    description = f"{year}年に公開した{len(papers)}件の原稿一覧です。"
    return f'''<!doctype html>
<html lang="ja">
<head>
{page_head(f"{year}年の原稿 — {SITE_TITLE_TOP}", description, f"/archive/{year}/", "../../styles.css")}
</head>
<body class="archive-page archive-year-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header"><div class="header-inner">
    <p class="eyebrow">YEAR ARCHIVE</p><h1>{year}年の原稿</h1><p class="lead">{description}</p>
    <nav class="site-navigation" aria-label="主要ページ">{site_navigation("../../", "archive")}</nav>
  </div></header>
  <main id="main-content">
    <p class="breadcrumb"><a href="../">全原稿アーカイブ</a> / {year}年</p>
    <section aria-labelledby="papers-title">
      <div class="section-heading"><div><p class="section-number">{year}</p><h2 id="papers-title">公開原稿</h2></div><p>{len(papers)}件</p></div>
      <form class="paper-search" role="search" aria-label="{year}年の公開原稿を絞り込む" onsubmit="return false">
        <label for="paper-query">この年の原稿を検索</label>
        <div class="paper-search-controls"><input id="paper-query" type="search" placeholder="タイトル・タグ・キーワード" autocomplete="off"><select id="paper-tag" aria-label="タグで絞り込む"><option value="">すべてのタグ</option></select><select id="paper-year" aria-label="公開年"><option value="{year}">{year}年</option></select><button id="paper-reset" type="button">絞り込みを解除</button></div>
        <p id="paper-count" class="paper-count" aria-live="polite"></p><div id="paper-empty" class="paper-empty" hidden><p>条件に一致する原稿はありません。</p><button type="button" data-reset-papers>絞り込みを解除</button></div>
      </form>
      <div class="paper-list">{cards}</div>
    </section>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
  <script src="../../search.js"></script>
</body>
</html>
'''
