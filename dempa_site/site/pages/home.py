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
from dempa_site.site.layout import page_head, site_navigation


def rendered_home_page(selected: Sequence[tuple[Path, Paper]]) -> str:
    newest = [manifest for _, manifest in selected[-HOME_PAPER_LIMIT:]][::-1]
    cards = "\n\n".join(paper_card(manifest) for manifest in newest)
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
<body>
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
    <section class="portal-grid" aria-label="記事を探す">
      <a class="portal-card portal-card-primary" href="archive/">
        <span class="section-number">ALL PAPERS</span>
        <strong>全原稿を検索</strong>
        <span>{len(selected)}件の原稿を、語句・タグ・公開年から探せます。</span>
      </a>
      <a class="portal-card" href="math/">
        <span class="section-number">MATHEMATICS</span>
        <strong>数学記事総覧</strong>
        <span>数学分野ごとの独立した総覧へ案内します。</span>
      </a>
      <a class="portal-card" href="archive/#years-title">
        <span class="section-number">YEARS</span>
        <strong>公開年から探す</strong>
        <span>記事を初出年ごとにたどれます。</span>
      </a>
      <a class="portal-card" href="archive/#tags-title">
        <span class="section-number">TAGS</span>
        <strong>タグから探す</strong>
        <span>電波通信の元タグを引き継いだ索引です。</span>
      </a>
    </section>

    <section class="latest-papers" aria-labelledby="papers-title">
      <div class="section-heading">
        <div>
          <p class="section-number">LATEST</p>
          <h2 id="papers-title">新着原稿</h2>
        </div>
        <p>公開日の新しいものから{len(newest)}件を表示しています。<a href="archive/">全{len(selected)}件を見る</a></p>
      </div>
      <div class="paper-list">
{START_MARKER}
{cards}
    {END_MARKER}
      </div>
    </section>

    <section class="archive-note" aria-labelledby="archive-note-title">
      <p class="section-number">ABOUT</p>
      <h2 id="archive-note-title">このアーカイブについて</h2>
      <p>記事本文への入口に加えて、公開可能なTeX原稿、PDF、BibTeX、図版などを原稿単位で保存しています。元記事は引き続き、はてなブログ「電波通信」から参照できます。</p>
    </section>
  </main>

  <footer>
    <p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p>
  </footer>
</body>
</html>
"""
