"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.config import (
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
)
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import paper_card
from dempa_site.site.layout import page_head, site_navigation
from dempa_site.site.pages.common import rendered_tag_index, rendered_year_groups


def rendered_archive_page(selected: Sequence[tuple[Path, Paper]]) -> str:
    cards = "\n\n".join(
        paper_card(manifest, "../") for _, manifest in reversed(selected)
    )
    description = (
        f"{SITE_TITLE_TOP}で公開している全{len(selected)}原稿を検索し、"
        "タグと公開年から絞り込める総合アーカイブです。"
    )
    return f"""<!doctype html>
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
      <p class="lead">{SITE_TITLE_TOP}で公開している全{len(selected)}原稿を横断検索できます。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "archive")}
      </nav>
    </div>
  </header>

  <main id="main-content">
    <section aria-labelledby="papers-title">
      <div class="section-heading">
        <div>
          <p class="section-number">01</p>
          <h2 id="papers-title">公開原稿を検索</h2>
        </div>
        <p>題名、説明、タグ、検索キーワード、公開年を横断検索します。</p>
      </div>

      <form class="paper-search" role="search" aria-label="公開原稿を絞り込む" onsubmit="return false">
        <label for="paper-query">原稿を検索</label>
        <div class="paper-search-controls">
          <input id="paper-query" type="search" placeholder="タイトル・タグ・キーワード" autocomplete="off">
          <select id="paper-tag" aria-label="電波通信のタグで絞り込む">
            <option value="">すべてのタグ</option>
          </select>
          <select id="paper-year" aria-label="公開年で絞り込む">
            <option value="">すべての年</option>
          </select>
          <button id="paper-reset" type="button">絞り込みを解除</button>
        </div>
        <p id="paper-count" class="paper-count" aria-live="polite"></p>
        <div id="paper-empty" class="paper-empty" hidden>
          <p>条件に一致する原稿はありません。</p>
          <button type="button" data-reset-papers>絞り込みを解除</button>
        </div>
      </form>

      <div class="paper-list">
{cards}
      </div>
    </section>

    <section class="year-directory" aria-labelledby="years-title">
      <div class="section-heading">
        <div>
          <p class="section-number">02</p>
          <h2 id="years-title">公開年別記事一覧</h2>
        </div>
        <p>公開年ごとに原稿をまとめています。</p>
      </div>
      <div class="year-groups">
{rendered_year_groups(selected, "../")}
      </div>
    </section>

    <section class="tag-directory" aria-labelledby="tags-title">
      <div class="section-heading">
        <div>
          <p class="section-number">03</p>
          <h2 id="tags-title">タグ索引</h2>
        </div>
        <p>タグを選ぶと、公開年ごとにまとめた専用ページへ移動します。</p>
      </div>
      <nav class="tag-index" aria-label="タグ索引">
{rendered_tag_index(selected).replace('href="tags/', 'href="../tags/')}
      </nav>
    </section>
  </main>

  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
  <script src="../search.js"></script>
</body>
</html>
"""
