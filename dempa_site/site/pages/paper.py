"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

import html
from urllib.parse import quote

from dempa_site.config import (
    BLOG_ONLY_KIND,
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
)
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import (
    original_article_action,
    public_file_actions,
)
from dempa_site.site.layout import page_head, site_navigation


def rendered_paper_page(manifest: Paper) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = html.escape(str(manifest["published_at"])[:10])
    year = int(manifest["year"])
    tag_chips = "\n".join(
        f'          <a class="paper-tag" href="../../tags/{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    keyword_chips = "\n".join(
        f'          <span class="keyword-chip">{html.escape(keyword)}</span>'
        for keyword in manifest["keywords"]
    )
    actions = public_file_actions(manifest, "", "          ")
    if manifest["kind"] == BLOG_ONLY_KIND:
        original_action = original_article_action(manifest, "          ", primary=True)
        if original_action:
            actions.append(original_action)
    actions.append('          <a href="keywords.txt">検索語テキスト</a>')
    if manifest["kind"] != BLOG_ONLY_KIND:
        original_action = original_article_action(manifest, "          ")
        if original_action:
            actions.append(original_action)
    eyebrow = "BLOG ARTICLE LINK" if manifest["kind"] == BLOG_ONLY_KIND else "PUBLIC MANUSCRIPT"
    section_number = "ARTICLE" if manifest["kind"] == BLOG_ONLY_KIND else "FILES"
    section_title = "ブログ記事へのリンク" if manifest["kind"] == BLOG_ONLY_KIND else "公開ファイル"
    action_label = "ブログ記事へのリンク" if manifest["kind"] == BLOG_ONLY_KIND else "公開ファイル"
    kind_badge = (
        f"\n        <span>{BLOG_ONLY_KIND}</span>"
        if manifest["kind"] == BLOG_ONLY_KIND
        else ""
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{manifest['title']} — {SITE_TITLE_TOP}", manifest["summary"], f"/papers/{slug}/", "../../styles.css")}
</head>
<body class="paper-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p class="lead">{summary}</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <article class="paper-detail">
      <div class="paper-meta">
        <span>初出 <a class="paper-year-link" href="../../archive/#year-{year}" aria-label="{year}年の記事一覧">{published_date}</a></span>
        <span>原稿番号 {slug}</span>{kind_badge}
      </div>
      <section aria-labelledby="files-title">
        <p class="section-number">{section_number}</p>
        <h2 id="files-title">{section_title}</h2>
        <nav class="paper-actions" aria-label="{html.escape(manifest['title'], quote=True)}の{action_label}">
{chr(10).join(actions)}
        </nav>
      </section>
      <section aria-labelledby="paper-tags-title">
        <p class="section-number">TAGS</p>
        <h2 id="paper-tags-title">電波通信のタグ</h2>
        <div class="paper-tags">
{tag_chips}
        </div>
      </section>
      <section aria-labelledby="keywords-title">
        <p class="section-number">KEYWORDS</p>
        <h2 id="keywords-title">検索キーワード</h2>
        <div class="keyword-list">
{keyword_chips}
        </div>
      </section>
    </article>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""
