"""Shared HTML head and site navigation."""

from __future__ import annotations

import html

from dempa_site.config import SITE_TITLE_TOP, SITE_URL


def site_navigation(prefix: str, current: str = "") -> str:
    home_href = prefix or "./"
    links = (
        ("home", home_href, "トップ"),
        ("archive", f"{prefix}archive/", "全原稿"),
        ("math", f"{prefix}math/", "数学記事総覧"),
        ("tags", f"{prefix}archive/#tags-title", "タグ索引"),
    )
    rendered = []
    for key, href, label in links:
        current_attribute = ' aria-current="page"' if key == current else ""
        rendered.append(
            f'        <a href="{href}"{current_attribute}>{label}</a>'
        )
    rendered.append(
        '        <a href="https://concious4410.hatenablog.com/">'
        'はてなブログ <span aria-hidden="true">↗</span></a>'
    )
    return "\n".join(rendered)


def page_head(
    title: str,
    description: str,
    canonical_path: str,
    stylesheet: str,
) -> str:
    escaped_title = html.escape(title, quote=True)
    escaped_description = html.escape(description, quote=True)
    canonical = f"{SITE_URL}{canonical_path}"
    return f"""  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <meta name="description" content="{escaped_description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_TITLE_TOP}">
  <meta property="og:title" content="{escaped_title}">
  <meta property="og:description" content="{escaped_description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{SITE_URL}/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="数識電収の電波と放電を表す紋章">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{SITE_URL}/og-image.png">
  <meta name="theme-color" content="#17324d">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="alternate" type="application/rss+xml" title="{SITE_TITLE_TOP} RSS" href="{SITE_URL}/feed.xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@400;500;600&amp;family=Zen+Kaku+Gothic+New:wght@400;500;700&amp;family=Zen+Kurenaido&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{stylesheet}">"""

