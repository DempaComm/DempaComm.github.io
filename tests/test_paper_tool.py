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
            page = (staged / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="primary-action" href="source.tex"', page)
            self.assertNotIn("main.pdf", page)
            self.assertNotIn('href=""', page)

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
            self.assertEqual("overridden", manifest["privacy_review"]["status"])
            self.assertEqual(
                "著者名は公開名として本人確認済み",
                manifest["privacy_review"]["reason"],
            )


if __name__ == "__main__":
    unittest.main()
