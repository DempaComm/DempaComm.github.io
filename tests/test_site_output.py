from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "paper_tool.py"


def run_tool(environment: dict[str, str], *arguments: str, check: bool = True):
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments],
        check=check,
        capture_output=True,
        text=True,
        env=environment,
    )


def prepare_root(root: Path) -> dict[str, str]:
    (root / "papers").mkdir()
    (root / "index.html").write_text(
        "\n".join(
            [
                "<!-- GENERATED:PAPERS:START -->",
                "<!-- GENERATED:PAPERS:END -->",
                "<!-- GENERATED:TAGS:START -->",
                "<!-- GENERATED:TAGS:END -->",
                "<!-- GENERATED:YEARS:START -->",
                "<!-- GENERATED:YEARS:END -->",
            ]
        ),
        encoding="utf-8",
    )
    (root / "styles.css").write_text("/* fixture */\n", encoding="utf-8")
    (root / "search.js").write_text("// fixture\n", encoding="utf-8")
    for asset in (
        "favicon.ico",
        "favicon-16.png",
        "favicon-32.png",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "og-image.png",
    ):
        (root / asset).write_bytes(b"test image placeholder")
    (root / "site.webmanifest").write_text(
        '{"name":"Test","start_url":"/"}', encoding="utf-8"
    )
    return {**os.environ, "PAPER_REPO_ROOT": str(root)}


def add_review_receipt(root: Path, source: Path) -> None:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    review = root / ".privacy-review" / digest
    review.mkdir(parents=True, exist_ok=True)
    file_type = source.suffix.removeprefix(".")
    rendered_pages = ["page-1.png"] if file_type == "pdf" else []
    if rendered_pages:
        (review / rendered_pages[0]).write_bytes(b"test image placeholder")
    (review / "report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sha256": digest,
                "file_type": file_type,
                "manual_review_required": True,
                "rendered_pages": rendered_pages,
                "inspection_status": "completed",
            }
        ),
        encoding="utf-8",
    )


def import_fixture_paper(
    root: Path,
    environment: dict[str, str],
    name: str,
    spec: dict,
    files: dict[str, bytes] | None = None,
) -> None:
    files = files or {}
    if files:
        source_dir = root / f"incoming-{name}"
        source_dir.mkdir()
        for relative, content in files.items():
            source = source_dir / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(content)
            if source.suffix.casefold() in {".tex", ".pdf"}:
                add_review_receipt(root, source)
        spec["source_dir"] = str(source_dir)
    spec_path = root / f"{name}.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    arguments = ["import-paper", str(spec_path)]
    if any(Path(relative).suffix.casefold() in {".tex", ".pdf"} for relative in files):
        arguments.append("--privacy-reviewed")
    run_tool(environment, *arguments)


class SiteOutputContractTest(unittest.TestCase):
    """Lock the routes and visible structure that later refactors must preserve."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.environment = prepare_root(cls.root)

        import_fixture_paper(
            cls.root,
            cls.environment,
            "normal",
            {
                "title": "通常原稿",
                "published_at": "2023-04-04T10:00:00+09:00",
                "sequence": 1,
                "migration_record_id": "fixture:0000000000000001",
                "legacy_slugs": ["old-normal-paper"],
                "kind": "図や参照を含むTeX",
                "math_section": "位相・距離・幾何",
                "summary": "PDF、TeX、補助資料を持つ通常原稿です。",
                "original_url": "https://example.hatenablog.com/entry/normal",
                "tags": ["数学", "位相空間"],
                "keywords": ["通常原稿", "位相"],
                "build_enabled": False,
                "files": [
                    {
                        "source": "article.tex",
                        "path": "article.tex",
                        "role": "manuscript",
                        "label": "TeX原稿",
                        "public": True,
                    },
                    {
                        "source": "article.pdf",
                        "path": "published.pdf",
                        "role": "published-pdf",
                        "label": "",
                        "public": True,
                    },
                    {
                        "source": "図版_日本語.txt",
                        "path": "図版_日本語.txt",
                        "role": "supporting-file",
                        "label": "日本語名の補助資料",
                        "public": True,
                    },
                ],
            },
            {
                "article.tex": b"\\documentclass{article}\n",
                "article.pdf": b"%PDF-1.4\n%%EOF\n",
                "図版_日本語.txt": "日本語名の公開ファイル\n".encode(),
            },
        )
        import_fixture_paper(
            cls.root,
            cls.environment,
            "blog",
            {
                "title": "ブログ本文だけの記事",
                "published_at": "2024-05-05T11:00:00+09:00",
                "sequence": 1,
                "migration_record_id": "fixture:0000000000000002",
                "kind": "ブログ本文のみ",
                "math_section": "その他",
                "summary": "公開ファイルを持たない記事です。",
                "original_url": "https://example.hatenablog.com/entry/blog",
                "tags": ["数学", "読み物"],
                "keywords": ["ブログ本文"],
                "build_enabled": False,
                "files": [],
            },
        )
        import_fixture_paper(
            cls.root,
            cls.environment,
            "pdf",
            {
                "title": "PDFだけの原稿",
                "published_at": "2025-06-06T12:00:00+09:00",
                "sequence": 1,
                "migration_record_id": "fixture:0000000000000003",
                "kind": "PDFのみ",
                "math_section": "解析・測度・確率",
                "summary": "PDFだけが残っている原稿です。",
                "original_url": "",
                "tags": ["数学", "解析"],
                "keywords": ["PDFのみ"],
                "build_enabled": False,
                "files": [
                    {
                        "source": "paper.pdf",
                        "path": "published.pdf",
                        "role": "published-pdf",
                        "label": "",
                        "public": True,
                    }
                ],
            },
            {"paper.pdf": b"%PDF-1.4\n%%EOF\n"},
        )
        import_fixture_paper(
            cls.root,
            cls.environment,
            "tex",
            {
                "title": "TeXだけの原稿",
                "published_at": "2026-07-07T13:00:00+09:00",
                "sequence": 1,
                "migration_record_id": "fixture:0000000000000004",
                "kind": "単純なTeX",
                "math_section": "代数・組合せ",
                "summary": "TeXだけが残っている原稿です。",
                "original_url": "",
                "tags": ["数学", "位相空間"],
                "keywords": ["TeXのみ"],
                "build_enabled": False,
                "files": [
                    {
                        "source": "source.tex",
                        "path": "source.tex",
                        "role": "manuscript",
                        "label": "TeX原稿",
                        "public": True,
                    }
                ],
            },
            {"source.tex": b"\\documentclass{article}\n"},
        )

        cls.site = cls.root / "_site"
        run_tool(cls.environment, "stage", str(cls.site))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def read(self, relative: str) -> str:
        return (self.site / relative).read_text(encoding="utf-8")

    def test_home_and_archive_keep_latest_limit_search_and_year_routes(self) -> None:
        home = self.read("index.html")
        self.assertEqual(3, home.count('class="paper-card"'))
        self.assertNotIn("通常原稿", home)
        self.assertIn("TeXだけの原稿", home)
        self.assertIn('href="archive/"', home)
        self.assertIn('href="math/"', home)

        archive = self.read("archive/index.html")
        self.assertEqual(4, archive.count('class="paper-card"'))
        self.assertIn('id="paper-query"', archive)
        for year in range(2023, 2027):
            self.assertIn(f'id="year-{year}"', archive)
            self.assertIn(f"{year}年", archive)

    def test_japanese_tag_page_is_grouped_by_year(self) -> None:
        tag_page = self.read("tags/位相空間/index.html")
        self.assertIn("位相空間", tag_page)
        self.assertIn('id="year-2026"', tag_page)
        self.assertIn('id="year-2023"', tag_page)
        self.assertIn("TeXだけの原稿", tag_page)
        self.assertIn("通常原稿", tag_page)
        archive = self.read("archive/index.html")
        self.assertIn('href="../tags/%E4%BD%8D%E7%9B%B8%E7%A9%BA%E9%96%93/"', archive)

    def test_math_directory_and_all_section_pages_are_present(self) -> None:
        math = self.read("math/index.html")
        for route, title in (
            ("algebra-combinatorics", "代数・組合せ"),
            ("topology-geometry", "位相・距離・幾何"),
            ("analysis-probability", "解析・測度・確率"),
            ("other", "その他"),
        ):
            self.assertIn(f'href="{route}/"', math)
            section = self.read(f"math/{route}/index.html")
            self.assertIn(title, section)
            self.assertIn("年", section)

    def test_each_paper_kind_has_the_correct_primary_action(self) -> None:
        normal = self.read("papers/2023-04-04-01/index.html")
        self.assertIn('class="primary-action" href="main.pdf"', normal)
        self.assertIn('href="article.tex"', normal)

        blog = self.read("papers/2024-05-05-01/index.html")
        self.assertIn('class="primary-action"', blog)
        self.assertIn("電波通信で読む", blog)
        self.assertNotIn("main.pdf", blog)
        self.assertNotIn("TeX原稿", blog)

        pdf = self.read("papers/2025-06-06-01/index.html")
        self.assertIn('class="primary-action" href="main.pdf"', pdf)
        self.assertNotIn("TeX原稿", pdf)

        tex = self.read("papers/2026-07-07-01/index.html")
        self.assertIn('class="primary-action" href="source.tex"', tex)
        self.assertNotIn("main.pdf", tex)

    def test_feed_sitemap_robots_and_not_found_page_keep_contract(self) -> None:
        rss = ET.fromstring(self.read("feed.xml"))
        items = rss.findall("./channel/item")
        self.assertEqual(4, len(items))
        self.assertEqual("TeXだけの原稿", items[0].findtext("title"))
        self.assertEqual(
            "https://dempacomm.github.io/papers/2026-07-07-01/",
            items[0].findtext("link"),
        )

        sitemap = ET.fromstring(self.read("sitemap.xml"))
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {node.text for node in sitemap.findall("s:url/s:loc", namespace)}
        self.assertIn("https://dempacomm.github.io/", locations)
        self.assertIn("https://dempacomm.github.io/archive/", locations)
        self.assertIn("https://dempacomm.github.io/math/", locations)
        self.assertIn(
            "https://dempacomm.github.io/tags/%E4%BD%8D%E7%9B%B8%E7%A9%BA%E9%96%93/",
            locations,
        )
        self.assertIn(
            "https://dempacomm.github.io/papers/2023-04-04-01/", locations
        )

        self.assertEqual(
            "User-agent: *\nAllow: /\n"
            "Sitemap: https://dempacomm.github.io/sitemap.xml\n",
            self.read("robots.txt"),
        )
        not_found = self.read("404.html")
        self.assertIn("404 NOT FOUND", not_found)
        self.assertIn('name="robots" content="noindex"', not_found)
        self.assertIn('href="/archive/"', not_found)
        self.assertIn('href="/math/"', not_found)

    def test_legacy_slug_and_japanese_filename_remain_public(self) -> None:
        canonical = self.site / "papers" / "2023-04-04-01"
        legacy = self.site / "papers" / "old-normal-paper"
        self.assertEqual(
            (canonical / "index.html").read_bytes(),
            (legacy / "index.html").read_bytes(),
        )
        self.assertEqual(
            (canonical / "main.pdf").read_bytes(),
            (legacy / "main.pdf").read_bytes(),
        )
        self.assertTrue((canonical / "図版_日本語.txt").is_file())
        self.assertIn('href="図版_日本語.txt"', self.read("papers/2023-04-04-01/index.html"))

    def test_staged_routes_and_broken_link_detection_are_fixed(self) -> None:
        routes = {
            str(path.relative_to(self.site))
            for path in self.site.rglob("index.html")
        }
        self.assertEqual(
            {
                "index.html",
                "archive/index.html",
                "math/index.html",
                "math/algebra-combinatorics/index.html",
                "math/topology-geometry/index.html",
                "math/analysis-probability/index.html",
                "math/other/index.html",
                "papers/2023-04-04-01/index.html",
                "papers/2024-05-05-01/index.html",
                "papers/2025-06-06-01/index.html",
                "papers/2026-07-07-01/index.html",
                "papers/old-normal-paper/index.html",
                "tags/数学/index.html",
                "tags/位相空間/index.html",
                "tags/読み物/index.html",
                "tags/解析/index.html",
            },
            routes,
        )
        run_tool(self.environment, "check-links", str(self.site))

        broken_page = self.site / "broken.html"
        broken_page.write_text('<a href="missing-page/">broken</a>', encoding="utf-8")
        try:
            result = run_tool(
                self.environment, "check-links", str(self.site), check=False
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing target missing-page/", result.stderr)
        finally:
            broken_page.unlink()


if __name__ == "__main__":
    unittest.main()
