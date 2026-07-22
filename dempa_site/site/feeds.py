"""Render the RSS feed for validated papers."""

from __future__ import annotations

from datetime import timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from dempa_site.config import SITE_TITLE_TOP, SITE_URL
from dempa_site.dates import parse_iso_datetime
from dempa_site.manifests.model import Paper


def rendered_feed(selected: list[tuple[Path, Paper]]) -> str:
    items = []
    for _, manifest in reversed(selected):
        published = parse_iso_datetime(manifest["published_at"])
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        slug = quote(str(manifest["slug"]), safe="")
        url = f"{SITE_URL}/papers/{slug}/"
        items.append(
            f"""    <item>
      <title>{xml_escape(str(manifest["title"]))}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{format_datetime(published)}</pubDate>
      <description>{xml_escape(str(manifest["summary"]))}</description>
    </item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{SITE_TITLE_TOP}</title>
    <link>{SITE_URL}/</link>
    <description>{SITE_TITLE_TOP}で公開する数学原稿とPDFの更新情報</description>
    <language>ja</language>
{chr(10).join(items)}
  </channel>
</rss>
"""

