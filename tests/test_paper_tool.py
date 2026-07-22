from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import (
    PAPER_TOOL as TOOL,
    add_privacy_review_receipt as add_review_receipt,
    prepare_paper_repository as prepare_root,
)


class SourceOnlyImportTest(unittest.TestCase):
    def test_build_roots_can_be_selected_by_effective_engine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            slug = "2026-07-22-01"
            paper_dir = root / "papers" / slug
            paper_dir.mkdir()
            source = paper_dir / "main.tex"
            source.write_text("\\documentclass{article}\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            (paper_dir / "paper.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "slug": slug,
                        "migration_record_id": "fixture:build-root",
                        "legacy_slugs": [],
                        "title": "LuaLaTeX原稿",
                        "published_at": "2026-07-22T12:00:00+09:00",
                        "sequence": 1,
                        "year": 2026,
                        "kind": "単純なTeX",
                        "math_section": "その他",
                        "summary": "エンジン別ビルドルートの検査です。",
                        "original_url": "",
                        "order": 2026072201,
                        "tags": ["数学"],
                        "keywords": ["LuaLaTeX"],
                        "build": {
                            "enabled": True,
                            "engine": "lualatex",
                            "root": "main.tex",
                        },
                        "files": [
                            {
                                "path": "main.tex",
                                "role": "manuscript",
                                "label": "TeX原稿",
                                "public": False,
                                "original_sha256": digest,
                                "sha256": digest,
                            }
                        ],
                        "approved_changes": [],
                        "privacy_reviews": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            selected = subprocess.run(
                [sys.executable, str(TOOL), "build-roots", "--engine", "lualatex"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            excluded = subprocess.run(
                [sys.executable, str(TOOL), "build-roots", "--engine", "platex"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            compatible = subprocess.run(
                [sys.executable, str(TOOL), "build-roots"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(f"papers/{slug}/main.tex\n", selected.stdout)
            self.assertEqual("", excluded.stdout)
            self.assertEqual(selected.stdout, compatible.stdout)

    def test_import_blog_only_article_without_public_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            spec = root / "blog-only.json"
            spec.write_text(
                json.dumps(
                    {
                        "title": "PDFリンクのない記事",
                        "published_at": "2017-02-04T21:49:57+09:00",
                        "sequence": 1,
                        "migration_record_id": "article:0123456789abcdef",
                        "kind": "ブログ本文のみ",
                        "math_section": "その他",
                        "summary": "電波通信で公開したブログ本文のみの記事です。",
                        "original_url": "https://example.hatenablog.com/entry/2017/02/04/214957",
                        "tags": ["雑談"],
                        "keywords": ["PDFリンクのない記事"],
                        "build_enabled": False,
                        "files": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(TOOL), "import-paper", str(spec)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            slug = "2017-02-04-01"
            manifest_path = root / "papers" / slug / "paper.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("ブログ本文のみ", manifest["kind"])
            self.assertEqual([], manifest["files"])
            self.assertEqual([], manifest["privacy_reviews"])
            staged = root / "staged"
            subprocess.run(
                [sys.executable, str(TOOL), "stage", str(staged)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            page = (staged / "papers" / slug / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn('class="primary-action"', page)
            self.assertIn("電波通信で読む", page)
            self.assertNotIn("PDFを読む", page)

    def test_approve_change_refreshes_privacy_review_for_changed_tex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            incoming = root / "incoming.tex"
            incoming.write_text("\\author{Public Name}\\n", encoding="utf-8")
            add_review_receipt(root, incoming)
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-tex",
                    str(incoming),
                    "--published-at",
                    "2026-07-16T12:00:00+09:00",
                    "--privacy-reviewed",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            paper_dir = root / "papers" / "2026-07-16-01"
            source = paper_dir / "source.tex"
            source.write_text("\\author{Updated Public Name}\\n", encoding="utf-8")
            add_review_receipt(root, source)

            blocked = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "approve-change",
                    "2026-07-16-01",
                    "--file",
                    "source.tex",
                    "--reason",
                    "requested update",
                ],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, blocked.returncode)
            self.assertIn("--privacy-reviewed", blocked.stderr)

            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "approve-change",
                    "2026-07-16-01",
                    "--file",
                    "source.tex",
                    "--reason",
                    "requested update",
                    "--privacy-reviewed",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            manifest = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(digest, manifest["files"][0]["sha256"])
            self.assertEqual(digest, manifest["privacy_reviews"][0]["source_sha256"])
            self.assertEqual(1, len(manifest["approved_changes"]))

    def test_one_tex_file_can_be_staged_without_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source = root / "incoming.tex"
            source_bytes = b"\\documentclass{article}\n\\title{Emergency Paper}\n"
            source.write_bytes(source_bytes)
            add_review_receipt(root, source)

            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-tex",
                    str(source),
                    "--published-at",
                    "2026-07-16T12:00:00+09:00",
                    "--privacy-reviewed",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("2026-07-16-01", imported.stdout)
            paper_dir = root / "papers" / "2026-07-16-01"
            self.assertEqual(source_bytes, (paper_dir / "source.tex").read_bytes())
            manifest = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            self.assertEqual("Emergency Paper", manifest["title"])
            self.assertFalse(manifest["build"]["enabled"])

            output = root / "_site"
            subprocess.run(
                [sys.executable, str(TOOL), "stage", str(output)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            staged = output / "papers" / "2026-07-16-01"
            self.assertTrue((staged / "source.tex").is_file())
            self.assertFalse((staged / "main.pdf").exists())
            self.assertTrue((output / "archive" / "index.html").is_file())
            self.assertTrue((output / "math" / "index.html").is_file())
            self.assertTrue(
                (output / "math" / "other" / "index.html").is_file()
            )
            self.assertTrue((output / "404.html").is_file())
            self.assertTrue((output / "feed.xml").is_file())
            self.assertTrue((output / "sitemap.xml").is_file())
            self.assertTrue((output / "robots.txt").is_file())
            self.assertTrue((output / "favicon.ico").is_file())
            self.assertTrue((output / "apple-touch-icon.png").is_file())
            self.assertTrue((output / "site.webmanifest").is_file())
            self.assertTrue((output / "og-image.png").is_file())
            not_found = (output / "404.html").read_text(encoding="utf-8")
            self.assertIn('href="/styles.css"', not_found)
            self.assertIn('href="/archive/"', not_found)
            self.assertIn('href="/math/"', not_found)
            self.assertIn('href="/archive/#tags-title"', not_found)
            self.assertIn('name="robots" content="noindex"', not_found)
            page = (staged / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="primary-action" href="source.tex"', page)
            self.assertNotIn("main.pdf", page)
            self.assertNotIn('href=""', page)
            home = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("新着原稿", home)
            self.assertIn('href="archive/"', home)
            self.assertEqual(1, home.count('class="paper-card"'))
            self.assertNotIn("<span>TeX原稿</span>", home)
            self.assertIn("Shippori+Mincho+B1", home)
            self.assertIn("Zen+Kaku+Gothic+New", home)
            self.assertIn("Zen+Kurenaido", home)
            self.assertIn('rel="icon" href="/favicon.ico"', home)
            self.assertIn('rel="manifest" href="/site.webmanifest"', home)
            self.assertIn('property="og:image"', home)
            self.assertIn('name="theme-color" content="#17324d"', home)
            archive = (output / "archive" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("全原稿アーカイブ", archive)
            self.assertIn("絞り込みを解除", archive)
            self.assertNotIn("<span>TeX原稿</span>", archive)
            math_home = (output / "math" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("分野別総覧への入口", math_home)
            self.assertIn('href="other/"', math_home)
            math_other = (
                output / "math" / "other" / "index.html"
            ).read_text(encoding="utf-8")
            self.assertIn("その他", math_other)
            self.assertIn("Emergency Paper", math_other)
            self.assertNotIn("<span>TeX原稿</span>", math_other)
            self.assertNotIn(
                "<span>TeX原稿</span>",
                (staged / "index.html").read_text(encoding="utf-8"),
            )

            checked = subprocess.run(
                [sys.executable, str(TOOL), "check-links", str(output)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("OK  links", checked.stdout)
            (output / "broken.html").write_text(
                '<a href="missing-page/">broken</a>', encoding="utf-8"
            )
            broken = subprocess.run(
                [sys.executable, str(TOOL), "check-links", str(output)],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, broken.returncode)
            self.assertIn("missing target", broken.stderr)

    def test_one_pdf_file_can_be_staged_as_main_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source = root / "finished-paper.pdf"
            source_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
            source.write_bytes(source_bytes)
            add_review_receipt(root, source)

            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-pdf",
                    str(source),
                    "--published-at",
                    "2026-07-16T12:00:00+09:00",
                    "--privacy-reviewed",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("2026-07-16-01", imported.stdout)
            paper_dir = root / "papers" / "2026-07-16-01"
            self.assertEqual(source_bytes, (paper_dir / "published.pdf").read_bytes())
            manifest = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            self.assertEqual("finished-paper", manifest["title"])
            self.assertFalse(manifest["build"]["enabled"])

            output = root / "_site"
            subprocess.run(
                [sys.executable, str(TOOL), "stage", str(output)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            staged = output / "papers" / "2026-07-16-01"
            self.assertEqual(source_bytes, (staged / "main.pdf").read_bytes())
            page = (staged / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="primary-action" href="main.pdf"', page)
            self.assertNotIn('href=""', page)

    def test_import_requires_inspection_and_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source = root / "private.tex"
            source.write_text("\\author{Private Name}\n", encoding="utf-8")

            blocked = subprocess.run(
                [sys.executable, str(TOOL), "import-tex", str(source)],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, blocked.returncode)
            self.assertIn("run inspect-file first", blocked.stderr)

            inspected = subprocess.run(
                [sys.executable, str(TOOL), "inspect-file", str(source)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("\\author candidate: Private Name", inspected.stdout)
            still_blocked = subprocess.run(
                [sys.executable, str(TOOL), "import-tex", str(source)],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, still_blocked.returncode)
            self.assertIn("--privacy-reviewed", still_blocked.stderr)

            source.write_text("\\author{Changed Private Name}\n", encoding="utf-8")
            stale = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-tex",
                    str(source),
                    "--privacy-reviewed",
                ],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, stale.returncode)
            self.assertIn("run inspect-file first", stale.stderr)

    def test_failed_inspection_can_be_overridden_with_a_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source = root / "reviewed-manually.tex"
            source.write_text("\\author{Known Public Name}\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            review = root / ".privacy-review" / digest
            review.mkdir(parents=True)
            (review / "report.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "sha256": digest,
                        "file_type": "tex",
                        "manual_review_required": True,
                        "rendered_pages": [],
                        "inspection_status": "failed",
                    }
                ),
                encoding="utf-8",
            )

            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-tex",
                    str(source),
                    "--privacy-override",
                    "著者名は公開名として本人確認済み",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("IMPORTED", imported.stdout)
            manifest_path = next((root / "papers").glob("*/paper.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            review_record = manifest["privacy_reviews"][0]
            self.assertEqual("overridden", review_record["status"])
            self.assertEqual(
                "著者名は公開名として本人確認済み",
                review_record["reason"],
            )

    def test_import_paper_requires_reviews_for_every_public_tex_and_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source_dir = root / "incoming"
            source_dir.mkdir()
            tex_name = "article-ウリゾーン.tex"
            normalized_tex_name = "article-ウリゾーン.tex"
            tex = source_dir / tex_name
            pdf = source_dir / "finished.pdf"
            bib = source_dir / "refs.bib"
            tex.write_text("\\title{Reviewed Article}\n", encoding="utf-8")
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            bib.write_text("@book{x,title={Reference}}\n", encoding="utf-8")
            spec = root / "spec.json"
            spec_value = {
                "title": "Reviewed Article",
                "published_at": "2026-07-16T12:00:00+09:00",
                "sequence": 1,
                "migration_record_id": "source:0123456789abcdef",
                "kind": "複数ファイル原稿",
                "summary": "検査済み原稿です。",
                "original_url": "",
                "tags": ["数学"],
                "keywords": ["Reviewed Article"],
                "source_dir": str(source_dir),
                "build_enabled": False,
                "files": [
                    {
                        "source": tex_name,
                        "path": tex_name,
                        "role": "manuscript",
                        "label": "TeXソース",
                        "public": True,
                    },
                    {
                        "source": "finished.pdf",
                        "path": "published.pdf",
                        "role": "published-pdf",
                        "label": "",
                        "public": True,
                    },
                    {
                        "source": "refs.bib",
                        "path": "refs.bib",
                        "role": "bibliography",
                        "label": "BibTeX",
                        "public": True,
                    },
                ],
            }
            spec.write_text(json.dumps(spec_value), encoding="utf-8")

            blocked = subprocess.run(
                [sys.executable, str(TOOL), "import-paper", str(spec)],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, blocked.returncode)
            self.assertIn("run inspect-file first", blocked.stderr)
            add_review_receipt(root, tex)
            add_review_receipt(root, pdf)
            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-paper",
                    str(spec),
                    "--privacy-reviewed",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("PUBLIC FILES TO IMPORT", imported.stdout)
            manifest_path = root / "papers" / "2026-07-16-01" / "paper.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(2, manifest["schema_version"])
            self.assertEqual(
                "source:0123456789abcdef", manifest["migration_record_id"]
            )
            self.assertEqual(
                {normalized_tex_name, "published.pdf"},
                {review["path"] for review in manifest["privacy_reviews"]},
            )
            self.assertTrue((manifest_path.parent / normalized_tex_name).is_file())

            manifest["privacy_reviews"].pop()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            invalid = subprocess.run(
                [sys.executable, str(TOOL), "verify"],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn("invalid privacy review coverage", invalid.stderr)

            manifest["schema_version"] = 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            legacy_bypass = subprocess.run(
                [sys.executable, str(TOOL), "verify"],
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertNotEqual(0, legacy_bypass.returncode)
            self.assertIn(
                "schema 1 privacy exemption is limited to migrated legacy papers",
                legacy_bypass.stderr,
            )


if __name__ == "__main__":
    unittest.main()
