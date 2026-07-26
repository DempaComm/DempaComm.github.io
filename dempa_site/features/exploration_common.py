"""Shared rendering and repository helpers for exploration features."""

from __future__ import annotations

import html
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.config import (
    SITE_TITLE_ATTRIBUTE,
    SITE_TITLE_FORMAL,
    SITE_TITLE_TOP,
)
from dempa_site.site.layout import page_head, site_navigation


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
) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{title} — {SITE_TITLE_TOP}", description, canonical_path, f"{prefix}styles.css")}
</head>
<body class="{html.escape(body_class, quote=True)}">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">{html.escape(eyebrow)}</p>
      <h1>{html.escape(title)}</h1>
      <p class="lead">{html.escape(description)}</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation(prefix, "explore")}
      </nav>
    </div>
  </header>
  <main id="main-content">
{body}
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""
