from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "paper_tool.py"


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
    (root / "styles.css").write_text("", encoding="utf-8")
    (root / "search.js").write_text("", encoding="utf-8")
    return {**os.environ, "PAPER_REPO_ROOT": str(root)}


def add_review_receipt(root: Path, source: Path) -> None:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    review = root / ".privacy-review" / digest
    review.mkdir(parents=True)
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


class SourceOnlyImportTest(unittest.TestCase):
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
            self.assertTrue((output / "404.html").is_file())
            self.assertTrue((output / "feed.xml").is_file())
            self.assertTrue((output / "sitemap.xml").is_file())
            self.assertTrue((output / "robots.txt").is_file())
            page = (staged / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="primary-action" href="source.tex"', page)
            self.assertNotIn("main.pdf", page)
            self.assertNotIn('href=""', page)
            home = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("新着原稿", home)
            self.assertIn('href="archive/"', home)
            archive = (output / "archive" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("全原稿アーカイブ", archive)
            self.assertIn("絞り込みを解除", archive)

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
            tex = source_dir / "article.tex"
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
                "kind": "複数ファイル原稿",
                "summary": "検査済み原稿です。",
                "original_url": "",
                "tags": ["数学"],
                "keywords": ["Reviewed Article"],
                "source_dir": str(source_dir),
                "build_enabled": False,
                "files": [
                    {
                        "source": "article.tex",
                        "path": "source.tex",
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
                {"source.tex", "published.pdf"},
                {review["path"] for review in manifest["privacy_reviews"]},
            )

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
