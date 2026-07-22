"""Render the public sitemap for validated papers."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from dempa_site.catalog.metadata import grouped_tags
from dempa_site.config import MATH_SECTION_DETAILS, MATH_SECTIONS, SITE_URL
from dempa_site.manifests.model import Paper


def rendered_sitemap(selected: list[tuple[Path, Paper]]) -> str:
    urls: list[tuple[str, str | None]] = [
        (f"{SITE_URL}/", None),
        (f"{SITE_URL}/archive/", None),
        (f"{SITE_URL}/math/", None),
    ]
    for section in MATH_SECTIONS:
        section_slug = MATH_SECTION_DETAILS[section]["slug"]
        urls.append((f"{SITE_URL}/math/{section_slug}/", None))
    for tag in grouped_tags(selected):
        urls.append((f"{SITE_URL}/tags/{quote(tag, safe='')}/", None))
    for _, manifest in selected:
        urls.append(
            (
                f"{SITE_URL}/papers/{quote(str(manifest['slug']), safe='')}/",
                str(manifest["published_at"])[:10],
            )
        )
    entries = []
    for location, last_modified in urls:
        lastmod = f"\n    <lastmod>{last_modified}</lastmod>" if last_modified else ""
        entries.append(
            f"""  <url>
    <loc>{xml_escape(location)}</loc>{lastmod}
  </url>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(entries)}
</urlset>
"""
