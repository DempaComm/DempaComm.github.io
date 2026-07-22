from __future__ import annotations

import unittest
from pathlib import Path

from dempa_site.manifests.model import Paper
from dempa_site.site.layout import page_head, site_navigation
from dempa_site.site.feeds import rendered_feed
from dempa_site.site.rendering import (
    rendered_archive_page,
    rendered_home_page,
    rendered_math_page,
    rendered_math_section_page,
    rendered_not_found_page,
    rendered_paper_page,
    rendered_tag_page,
)
from dempa_site.site.sitemap import rendered_sitemap


def paper(
    slug: str,
    title: str,
    math_section: str = "その他",
    tags: list[str] | None = None,
) -> Paper:
    published_at = f"{slug[:10]}T12:00:00+09:00"
    sequence = int(slug[-2:])
    value = {
        "schema_version": 2,
        "slug": slug,
        "migration_record_id": f"fixture:{slug}",
        "legacy_slugs": [],
        "title": title,
        "published_at": published_at,
        "sequence": sequence,
        "year": int(slug[:4]),
        "kind": "ブログ本文のみ",
        "math_section": math_section,
        "summary": f"{title}の説明です。",
        "original_url": f"https://example.hatenablog.com/entry/{slug}",
        "order": int(slug[:10].replace("-", "") + f"{sequence:02d}"),
        "tags": tags or ["数学"],
        "keywords": [title],
        "build": {"enabled": False, "engine": ""},
        "files": [],
        "approved_changes": [],
        "privacy_reviews": [],
    }
    return Paper.from_dict(value, Path(slug) / "paper.json")


class PublicRenderingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.papers = [
            paper("2023-01-01-01", "代数記事", "代数・組合せ", ["数学", "代数"]),
            paper("2024-01-01-01", "位相記事", "位相・距離・幾何", ["数学", "位相空間"]),
            paper("2025-01-01-01", "解析記事", "解析・測度・確率", ["数学", "解析"]),
            paper("2026-01-01-01", "その他記事", "その他", ["数学", "読み物"]),
        ]
        self.selected = [
            (item.source_path, item) for item in self.papers
        ]

    def test_common_head_navigation_and_public_pages_render_without_io(self) -> None:
        head = page_head("題名", "説明", "/fixture/", "../styles.css")
        self.assertIn(
            '<link rel="canonical" href="https://dempacomm.github.io/fixture/">',
            head,
        )
        self.assertIn('href="../styles.css"', head)
        navigation = site_navigation("../", "archive")
        self.assertIn('aria-current="page">全原稿', navigation)

        home = rendered_home_page(self.selected)
        self.assertEqual(3, home.count('class="paper-card"'))
        self.assertNotIn("代数記事", home)
        archive = rendered_archive_page(self.selected)
        self.assertEqual(4, archive.count('class="paper-card"'))
        self.assertIn('id="year-2026"', archive)
        self.assertIn("タグ索引", archive)

        tag = rendered_tag_page("位相空間", [self.papers[1]])
        self.assertIn("位相空間", tag)
        self.assertIn('id="year-2024"', tag)
        math = rendered_math_page(self.selected)
        self.assertIn("数学記事総覧", math)
        section = rendered_math_section_page("代数・組合せ", [self.papers[0]])
        self.assertIn("代数記事", section)

        detail = rendered_paper_page(self.papers[0])
        self.assertIn("電波通信で読む", detail)
        self.assertIn("ブログ本文のみ", detail)
        not_found = rendered_not_found_page()
        self.assertIn("404 NOT FOUND", not_found)
        self.assertIn('content="noindex"', not_found)

    def test_feed_and_sitemap_are_rendered_from_the_same_typed_catalog(self) -> None:
        feed = rendered_feed(self.selected)
        self.assertEqual(4, feed.count("<item>"))
        self.assertLess(feed.index("その他記事"), feed.index("代数記事"))
        sitemap = rendered_sitemap(self.selected)
        self.assertIn(
            "https://dempacomm.github.io/papers/2026-01-01-01/", sitemap
        )
        self.assertIn(
            "https://dempacomm.github.io/tags/%E4%BD%8D%E7%9B%B8%E7%A9%BA%E9%96%93/",
            sitemap,
        )

    def test_compatibility_renderer_remains_a_thin_page_module_index(self) -> None:
        rendering = (
            Path(__file__).parents[1] / "dempa_site" / "site" / "rendering.py"
        ).read_text(encoding="utf-8")

        self.assertLess(len(rendering.splitlines()), 80)
        self.assertIn("dempa_site.site.pages.home", rendering)
        self.assertNotIn("<html", rendering)

if __name__ == "__main__":
    unittest.main()
