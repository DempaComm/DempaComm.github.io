"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

from dempa_site.config import SITE_TITLE_TOP
from dempa_site.site.layout import page_head, site_footer, site_header


def rendered_not_found_page() -> str:
    description = "指定されたページは見つかりませんでした。数識電収の各索引から原稿を探せます。"
    header = site_header(
        eyebrow_html="404 NOT FOUND",
        title_html="ページが見つかりません",
        lead_html="URLが変更されたか、原稿がまだ公開されていないようです。別の入口から探してみてください。",
        prefix="/",
        current_navigation="",
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"ページが見つかりません — {SITE_TITLE_TOP}", description, "/404.html", "/styles.css")}
  <meta name="robots" content="noindex">
</head>
<body class="not-found-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
    <section class="not-found-guide">
      <p class="section-number">WAYFINDER</p>
      <h2>原稿への入口</h2>
      <p>題名やキーワードが分かる場合は全原稿検索、数学分野からたどる場合は数学記事総覧が便利です。</p>
      <nav class="paper-actions" aria-label="ページが見つからないときの案内">
        <a class="primary-action" href="/archive/">全原稿を検索</a>
        <a href="/">トップへ戻る</a>
        <a href="/math/">数学記事総覧</a>
        <a href="/archive/#tags-title">タグ索引</a>
      </nav>
    </section>
  </main>
{site_footer()}
</body>
</html>
"""
