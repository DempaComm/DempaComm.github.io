from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dempa_site.conversion.latexml_publication import publish_latexml_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.loader import load_manifest


class LaTeXMLPublicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paper_dir = self.root / "papers" / "2026-07-26-01"
        self.paper_dir.mkdir(parents=True)
        source = self.paper_dir / "article.tex"
        source.write_text("\\documentclass{article}\n", encoding="utf-8")
        pdf = self.paper_dir / "published.pdf"
        pdf.write_bytes(b"%PDF-test")
        digest = sha256_file(source)
        self.manifest_path = self.paper_dir / "paper.json"
        write_json(
            self.manifest_path,
            {
                "schema_version": 2,
                "slug": "2026-07-26-01",
                "migration_record_id": "fixture:latexml-publication",
                "legacy_slugs": [],
                "title": "HTML公開試験",
                "published_at": "2026-07-26T12:00:00+09:00",
                "sequence": 1,
                "year": 2026,
                "kind": "単純なTeX",
                "math_section": "その他",
                "summary": "HTML公開試験です。",
                "original_url": "",
                "order": 2026072601,
                "tags": ["数学"],
                "keywords": ["HTML"],
                "build": {"enabled": True, "engine": "lualatex", "root": "article.tex"},
                "files": [
                    {
                        "path": "article.tex",
                        "role": "manuscript",
                        "label": "TeXソース",
                        "public": True,
                        "original_sha256": digest,
                        "sha256": digest,
                    },
                    {
                        "path": "published.pdf",
                        "role": "published-pdf",
                        "label": "PDF",
                        "public": True,
                        "original_sha256": sha256_file(pdf),
                        "sha256": sha256_file(pdf),
                    }
                ],
                "approved_changes": [],
                "privacy_reviews": [
                    {
                        "path": "article.tex",
                        "status": "reviewed",
                        "reason": "",
                        "source_sha256": digest,
                        "inspection_status": "completed",
                        "recorded_at": "2026-07-26T12:00:00+09:00",
                    },
                    {
                        "path": "published.pdf",
                        "status": "reviewed",
                        "reason": "",
                        "source_sha256": sha256_file(pdf),
                        "inspection_status": "completed",
                        "recorded_at": "2026-07-26T12:00:00+09:00",
                    }
                ],
            },
        )
        self.paper = load_manifest(self.manifest_path, PaperToolError)
        self.trial = self.root / "trial"
        result_dir = self.trial / self.paper.slug
        result_dir.mkdir(parents=True)
        (result_dir / "index.html").write_text(
            """<!doctype html><html><head><title>HTML公開試験</title></head>
<body><article class="ltx_document"><h1>HTML公開試験</h1>
<div class="ltx_dates">HTML変換日：2026年7月26日</div></article></body></html>""",
            encoding="utf-8",
        )
        (result_dir / "LaTeXML.css").write_text("/* LaTeXML */\n", encoding="utf-8")
        (result_dir / "figure-01-page-2.png").write_bytes(b"png")
        (result_dir / "latexml.log").write_text("ok\n", encoding="utf-8")
        write_json(
            self.trial / "report.json",
            {
                "schema_version": 2,
                "generated_at": "2026-07-26T12:30:00+09:00",
                "tool": "LaTeXML",
                "version": "latexmlc (LaTeXML version 0.8.8)",
                "publishable": False,
                "manual_review_required": True,
                "results": [
                    {
                        "slug": self.paper.slug,
                        "source": "article.tex",
                        "source_sha256": digest,
                        "html": f"{self.paper.slug}/index.html",
                        "log": f"{self.paper.slug}/latexml.log",
                        "automatic_checks_passed": True,
                        "privacy_findings": [],
                        "blocking_reasons": [],
                    }
                ],
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_reviewed_trial_becomes_hashed_public_files(self) -> None:
        publication = publish_latexml_trial(
            root=self.root,
            paper=self.paper,
            trial_output=self.trial,
        )

        self.assertEqual(3, publication.file_count)
        published = load_manifest(self.manifest_path, PaperToolError)
        self.assertIsNotNone(published.html_version)
        self.assertEqual("approved", published.html_version.status)
        self.assertEqual("html/index.html", published.html_version.path)
        public_html = publication.html_path.read_text(encoding="utf-8")
        self.assertIn("EXPERIMENTAL HTML VERSION", public_html)
        self.assertIn('../../../styles.css', public_html)
        self.assertIn('id="main-content"', public_html)
        self.assertIn("HTML変換日：2026年7月26日", public_html)
        self.assertIn('href="../article.tex">TeXソース</a>', public_html)
        self.assertIn('href="../published.pdf">PDFを読む</a>', public_html)
        self.assertNotIn("../main.tex", public_html)
        self.assertNotIn("../main.pdf", public_html)
        self.assertTrue((self.paper_dir / "html" / "figure-01-page-2.png").is_file())

    def test_dynamic_markup_is_rejected_without_changing_the_paper(self) -> None:
        trial_html = self.trial / self.paper.slug / "index.html"
        trial_html.write_text(
            trial_html.read_text(encoding="utf-8").replace(
                "</article>", "<script>alert(1)</script></article>"
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PaperToolError, "動的要素"):
            publish_latexml_trial(
                root=self.root,
                paper=self.paper,
                trial_output=self.trial,
            )

        self.assertFalse((self.paper_dir / "html").exists())
        self.assertNotIn("html_version", load_manifest(self.manifest_path).to_dict())

    def test_unsafe_inline_svg_is_rejected(self) -> None:
        trial_html = self.trial / self.paper.slug / "index.html"
        trial_html.write_text(
            trial_html.read_text(encoding="utf-8").replace(
                "</article>", '<svg onload="run()"></svg></article>'
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PaperToolError, "動的要素"):
            publish_latexml_trial(
                root=self.root,
                paper=self.paper,
                trial_output=self.trial,
            )


if __name__ == "__main__":
    unittest.main()
