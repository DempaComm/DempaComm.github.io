"""Reusable paper cards and file actions."""

from __future__ import annotations

import html
from urllib.parse import quote

from dempa_site.config import BLOG_ONLY_KIND
from dempa_site.files import compact_json
from dempa_site.manifests.model import Paper


def has_pdf(manifest: Paper) -> bool:
    """Return whether staging will provide main.pdf for this paper."""
    if manifest.build.enabled:
        return True
    return any(entry.path == "published.pdf" for entry in manifest.files)


def public_file_actions(
    manifest: Paper, prefix: str, indent: str
) -> list[str]:
    """Render PDF/source actions, making a source primary when no PDF exists."""
    actions: list[str] = []
    pdf_available = has_pdf(manifest)
    if pdf_available:
        actions.append(
            f'{indent}<a class="primary-action" href="{prefix}main.pdf">PDFを読む</a>'
        )
    primary_source_added = False
    for entry in manifest.files:
        if not entry.public or not entry.label:
            continue
        relative = html.escape(entry.path, quote=True)
        label = html.escape(entry.label)
        primary = ""
        if not pdf_available and not primary_source_added and entry.role == "manuscript":
            primary = ' class="primary-action"'
            primary_source_added = True
        actions.append(f'{indent}<a{primary} href="{prefix}{relative}">{label}</a>')
    return actions


def original_article_action(
    manifest: Paper, indent: str, primary: bool = False
) -> str | None:
    if not manifest.original_url:
        return None
    original_url = html.escape(manifest.original_url, quote=True)
    class_attribute = ' class="primary-action"' if primary else ""
    label = "電波通信で読む" if manifest.kind == BLOG_ONLY_KIND else "元の記事"
    return f'{indent}<a{class_attribute} href="{original_url}">{label}</a>'


def tag_href(tag: str, prefix: str = "") -> str:
    return f"{prefix}tags/{quote(tag, safe='')}/"


def paper_card(manifest: Paper, prefix: str = "") -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = str(manifest["published_at"])[:10]
    year = int(manifest["year"])
    search_terms = " ".join(
        [
            manifest["title"],
            manifest["summary"],
            published_date,
            *manifest["tags"],
            *manifest["keywords"],
        ]
    )
    search_attribute = html.escape(search_terms.casefold(), quote=True)
    tags_attribute = html.escape(
        compact_json(manifest["tags"]), quote=True
    )
    tag_chips = "\n".join(
        f'          <a class="paper-tag" href="{tag_href(tag, prefix)}">{html.escape(tag)}</a>'
        for tag in manifest["tags"]
    )
    actions = public_file_actions(manifest, f"{prefix}papers/{slug}/", "          ")
    if manifest["kind"] == BLOG_ONLY_KIND:
        original_action = original_article_action(manifest, "          ", primary=True)
        if original_action:
            actions.append(original_action)
    actions.append(
        f'          <a href="{prefix}papers/{slug}/keywords.txt">検索語</a>'
    )
    if manifest["kind"] != BLOG_ONLY_KIND:
        original_action = original_article_action(manifest, "          ")
        if original_action:
            actions.append(original_action)
    actions_html = "\n".join(actions)
    aria_suffix = "ブログ記事へのリンク" if manifest["kind"] == BLOG_ONLY_KIND else "ファイル"
    aria = html.escape(f"{manifest['title']}の{aria_suffix}", quote=True)
    kind_badge = (
        f"\n          <span>{BLOG_ONLY_KIND}</span>"
        if manifest["kind"] == BLOG_ONLY_KIND
        else ""
    )
    year_href = f"#year-{year}" if prefix else f"archive/#year-{year}"
    return f"""      <article class="paper-card" id="paper-{slug}" data-search="{search_attribute}" data-tags="{tags_attribute}" data-year="{year}">
        <div class="paper-meta">
          <span>初出 <a class="paper-year-link" href="{year_href}" aria-label="{year}年の記事一覧">{published_date}</a></span>{kind_badge}
        </div>
        <h3><a href="{prefix}papers/{slug}/">{title}</a></h3>
        <p>{summary}</p>
        <div class="paper-tags" aria-label="電波通信のタグ">
{tag_chips}
        </div>
        <nav class="paper-actions" aria-label="{aria}">
{actions_html}
        </nav>
      </article>"""

