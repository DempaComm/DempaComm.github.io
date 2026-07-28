"""Render the Pagefind-backed full-text search page."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.config import (
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
)
from dempa_site.manifests.model import Paper
from dempa_site.site.layout import page_head, site_navigation


def rendered_full_text_search_page(
    selected: Sequence[tuple[Path, Paper]],
) -> str:
    indexed = sum(bool(paper.html_versions) for _, paper in selected)
    description = (
        f"{SITE_TITLE_TOP}のLaTeXML HTML版{indexed}件を本文、節見出し、"
        "定理名、参考文献から検索します。"
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"本文全文検索 — {SITE_TITLE_TOP}", description, "/search/", "../styles.css")}
</head>
<body class="fulltext-search-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">FULL-TEXT SEARCH</p>
      <h1>本文全文検索</h1>
      <p class="lead">LaTeXML HTML版{indexed}件の本文をPagefindで検索します。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "search")}
      </nav>
    </div>
  </header>

  <main id="main-content">
    <section class="fulltext-search-panel" aria-labelledby="fulltext-title">
      <div class="section-heading">
        <div>
          <p class="section-number">01</p>
          <h2 id="fulltext-title">HTML版の本文を検索</h2>
        </div>
        <p>題名だけでなく、本文、節見出し、定理名、参考文献に含まれる語を探せます。</p>
      </div>

      <form id="fulltext-search-form" class="fulltext-search-form" role="search">
        <label for="fulltext-query">検索語</label>
        <div>
          <input id="fulltext-query" name="q" type="search" placeholder="本文に含まれる語" autocomplete="off" required>
          <button type="submit">検索</button>
        </div>
      </form>
      <p id="fulltext-status" class="fulltext-status" aria-live="polite">検索語を入力してください。</p>
      <ol id="fulltext-results" class="fulltext-results"></ol>
      <noscript><p class="paper-empty">本文全文検索にはJavaScriptが必要です。</p></noscript>
    </section>

    <aside class="fulltext-search-note">
      <h2>検索範囲</h2>
      <p>検索対象は主HTML版だけです。HTML版がない記事は<a href="../archive/">全原稿アーカイブ</a>の題名・タグ・キーワード検索を利用してください。</p>
    </aside>
  </main>

  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
  <script src="../full-text-search.js" defer></script>
</body>
</html>
"""
