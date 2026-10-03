"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.config import (
    END_MARKER,
    HOME_PAPER_LIMIT,
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
    START_MARKER,
)
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import paper_card
from dempa_site.site.layout import CONTENT_LICENSE_NOTICE, page_head, site_navigation


def rendered_home_page(selected: Sequence[tuple[Path, Paper]]) -> str:
    newest = [manifest for _, manifest in selected[-HOME_PAPER_LIMIT:]][::-1]
    cards = "\n\n".join(paper_card(manifest, compact=True) for manifest in newest)
    description = (
        f"『{SITE_TITLE_TOP}』の数学原稿、PDF、TeXソースを保存・公開する"
        "数学記事アーカイブです。"
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{SITE_TITLE_TOP} — 数学原稿アーカイブ", description, "/", "styles.css")}
  <meta name="google-site-verification" content="7hjNDoj7EFF3W9aH81po0C0Sk38Uf9vIh2161O2aCDs" />
</head>
<body class="home-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS ARCHIVE</p>
      <h1>{SITE_TITLE_TOP}</h1>
      <p class="subtitle"><span>{SITE_TITLE_FORMAL}</span><span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p>
      <p class="lead">数学記事の原稿と、原稿から生成したPDFを保存・公開するアーカイブです。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("", "home")}
      </nav>
    </div>
  </header>

  <main id="main-content">
    <section class="home-search" aria-label="記事を探す">
      <form class="fulltext-search-form" role="search" action="archive/" method="get">
        <label for="home-query">全{len(selected)}原稿を検索</label>
        <div><input id="home-query" name="q" type="search" placeholder="題名・説明・タグ・キーワード"><button type="submit">検索</button></div>
      </form>
      <nav class="home-browse-links" aria-label="探し方を選ぶ">
        <a href="archive/">全原稿</a><a href="math/">数学記事総覧</a>
        <a href="archive/#years-title">公開年</a><a href="archive/#tags-title">タグ</a>
        <a href="graph/">関係図を開く</a>
        <a href="explore/">読書経路・関係図</a>
      </nav>
    </section>

    <section class="latest-papers" aria-labelledby="papers-title">
      <div class="section-heading">
        <div><p class="section-number">LATEST</p><h2 id="papers-title">新着原稿</h2></div>
        <p>初出日の新しいものから{len(newest)}件。<a href="archive/">全{len(selected)}件を見る</a></p>
      </div>
      <div class="paper-list paper-list-compact">
{START_MARKER}
{cards}
    {END_MARKER}
      </div>
    </section>

    <section class="paper-discovery" aria-labelledby="discovery-title">
      <div class="section-heading">
        <div>
          <p class="section-number">SERENDIPITY</p>
          <h2 id="discovery-title">この日・ランダム記事</h2>
        </div>
        <p>公開日や分野から、思いがけない原稿へ案内します。</p>
      </div>
      <div class="discovery-grid">
        <article class="discovery-card" aria-live="polite">
          <p class="section-number">ON THIS DAY</p>
          <div id="today-paper"><p class="discovery-note">この日の記事を選んでいます…</p></div>
        </article>
        <article class="discovery-card" aria-live="polite">
          <p class="section-number">RANDOM PAPER</p>
          <div class="discovery-controls">
            <label for="random-paper-scope">選ぶ範囲</label>
            <select id="random-paper-scope">
              <option value="all">全原稿</option>
              <option value="substantial">断片ではないもの</option>
              <option value="代数・組合せ">代数・組合せ</option>
              <option value="位相・距離・幾何">位相・距離・幾何</option>
              <option value="解析・測度・確率">解析・測度・確率</option>
              <option value="その他">その他</option>
            </select>
            <button id="random-paper-button" type="button">別の記事を選ぶ</button>
          </div>
          <div id="random-paper"><p class="discovery-note">ランダム記事を選んでいます…</p></div>
        </article>
      </div>
      <noscript><p><a href="archive/">JavaScriptを使わず全原稿から探す</a></p></noscript>
    </section>

    <section class="archive-note" aria-labelledby="archive-note-title">
      <p class="section-number">ABOUT</p>
      <h2 id="archive-note-title">このアーカイブについて</h2>
      <p>記事本文への入口に加えて、公開可能なTeX原稿、PDF、BibTeX、図版などを原稿単位で保存しています。元記事は引き続き、はてなブログ「電波通信」から参照できます。</p>
    </section>
  </main>

  <footer>
    <p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p>
  {CONTENT_LICENSE_NOTICE}</footer>
  <script src="discovery.js" defer></script>
</body>
</html>
"""
