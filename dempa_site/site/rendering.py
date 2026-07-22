"""Render the archive's public HTML pages without performing I/O."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from dempa_site.catalog.metadata import grouped_math_sections, grouped_tags
from dempa_site.config import (
    BLOG_ONLY_KIND,
    HOME_PAPER_LIMIT,
    MATH_SECTION_DETAILS,
    MATH_SECTIONS,
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
    START_MARKER,
    END_MARKER,
)
from dempa_site.manifests.model import Paper
from dempa_site.site.cards import (
    has_pdf,
    original_article_action,
    paper_card,
    public_file_actions,
    tag_href,
)
from dempa_site.site.layout import page_head, site_navigation


def rendered_tag_index(selected: list[tuple[Path, Paper]]) -> str:
    grouped = grouped_tags(selected)
    return "\n".join(
        f'      <a class="tag-index-item" href="{tag_href(tag)}">'
        f"<span>{html.escape(tag)}</span><span>{len(papers)}件</span></a>"
        for tag, papers in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    )


def rendered_year_groups(
    selected: list[tuple[Path, Paper]], prefix: str = ""
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


def rendered_home_page(selected: list[tuple[Path, Paper]]) -> str:
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


def rendered_archive_page(selected: list[tuple[Path, Paper]]) -> str:
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
          <div class="paper-meta"><span>初出 <a class="paper-year-link" href="../../archive/#year-{year}" aria-label="{year}年の記事一覧">{published_date}</a></span>{kind_badge}</div>
          <h3><a href="../../papers/{slug}/">{title}</a></h3>
          <p>{summary}</p>
          <div class="paper-tags" aria-label="電波通信のタグ">
{tag_chips}
          </div>
          <nav class="paper-actions" aria-label="{html.escape(manifest['title'], quote=True)}の{action_label}">
{chr(10).join(actions)}
          </nav>
        </article>"""


def rendered_tag_page(tag: str, papers: list[Paper]) -> str:
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
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{tag}の記事 — {SITE_TITLE_TOP}", description, f"/tags/{quote(tag, safe='')}/", "../../styles.css")}
</head>
<body class="tag-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">TAG ARCHIVE</p>
      <h1>{escaped_tag}</h1>
      <p class="lead">電波通信でこのタグが付けられていた公開原稿、全{len(papers)}件。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../", "tags")}
      </nav>
    </div>
  </header>
  <main id="main-content">
{year_sections}
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


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
        path = html.escape(entry.path, quote=True)
        label = html.escape(entry.label)
        file_links.append(f'<a href="{prefix}papers/{slug}/{path}">{label}</a>')
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


def representative_math_tags(papers: list[Paper]) -> list[str]:
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


def rendered_math_page(selected: list[tuple[Path, Paper]]) -> str:
    grouped = grouped_math_sections(selected)
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
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"数学記事総覧 — {SITE_TITLE_TOP}", f"{SITE_TITLE_TOP}の数学記事を分野別総覧へ案内する総合目次です。", "/math/", "../styles.css")}
</head>
<body class="math-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS DIRECTORY</p>
      <h1>数学記事総覧</h1>
      <p class="lead">分野別総覧への入口です。現在公開している全{len(selected)}原稿を、四つの主分類からたどれます。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "math")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <nav class="math-directory-grid" aria-label="数学分野別総覧">
{directory_cards}
    </nav>
    <section class="archive-note" aria-labelledby="math-guide-title">
      <p class="section-number">GUIDE</p>
      <h2 id="math-guide-title">分類について</h2>
      <p>各原稿は主分類を一つ持ちます。分野別ページでは公開年ごとの一覧と、電波通信から引き継いだタグを併記しています。</p>
    </section>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_math_section_page(
    section: str, papers: list[Paper]
) -> str:
    details = MATH_SECTION_DETAILS[section]
    by_year: dict[int, list[Paper]] = {}
    for paper in papers:
        by_year.setdefault(int(paper["year"]), []).append(paper)
    if by_year:
        year_sections = "\n".join(
            f"""      <section class="math-index-section" aria-labelledby="year-{year}">
        <div class="math-index-heading">
          <h2 id="year-{year}">{year}年</h2>
          <span>{len(year_papers)}件</span>
        </div>
        <ul class="math-index-list">
{chr(10).join(rendered_math_index_item(paper, "../../") for paper in reversed(year_papers))}
        </ul>
      </section>"""
            for year, year_papers in sorted(by_year.items(), reverse=True)
        )
    else:
        year_sections = """      <section class="math-empty">
        <p>この分野には、まだ公開原稿がありません。</p>
        <a href="../../archive/">全原稿アーカイブを見る</a>
      </section>"""
    description = str(details["description"])
    slug = str(details["slug"])
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{section}の記事総覧 — {SITE_TITLE_TOP}", description, f"/math/{slug}/", "../../styles.css")}
</head>
<body class="math-page math-section-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS SECTION</p>
      <h1>{html.escape(section)}</h1>
      <p class="lead">{html.escape(description)} 現在{len(papers)}件です。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../", "math")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <p class="directory-back"><a href="../">数学記事総覧へ戻る</a></p>
{year_sections}
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


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


def rendered_not_found_page() -> str:
    description = "指定されたページは見つかりませんでした。数識電収の各索引から原稿を探せます。"
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"ページが見つかりません — {SITE_TITLE_TOP}", description, "/404.html", "/styles.css")}
  <meta name="robots" content="noindex">
</head>
<body class="not-found-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">404 NOT FOUND</p>
      <h1>ページが見つかりません</h1>
      <p class="lead">URLが変更されたか、原稿がまだ公開されていないようです。別の入口から探してみてください。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("/", "")}
      </nav>
    </div>
  </header>
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
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""
