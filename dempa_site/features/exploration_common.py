"""Shared rendering and repository helpers for exploration features."""

from __future__ import annotations

import html
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.config import SITE_TITLE_TOP
from dempa_site.site.layout import page_head, site_footer, site_header


def repository_root(catalog: SiteCatalog) -> Path:
    if not catalog.selected:
        raise ValueError("探索機能には1件以上の原稿が必要です")
    return catalog.selected[0][0].resolve().parents[2]


def rendered_exploration_page(
    *,
    title: str,
    eyebrow: str,
    description: str,
    canonical_path: str,
    body: str,
    prefix: str = "../",
    body_class: str = "exploration-page",
    current_navigation: str = "explore",
    extra_head: str = "",
) -> str:
    header = site_header(
        eyebrow_html=html.escape(eyebrow),
        title_html=html.escape(title),
        lead_html=html.escape(description),
        prefix=prefix,
        current_navigation=current_navigation,
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{title} — {SITE_TITLE_TOP}", description, canonical_path, f"{prefix}styles.css")}
{extra_head}</head>
<body class="{html.escape(body_class, quote=True)}">
  <a class="skip-link" href="#main-content">本文へ移動</a>
{header}
  <main id="main-content">
{body}
  </main>
{site_footer()}
</body>
</html>
"""
