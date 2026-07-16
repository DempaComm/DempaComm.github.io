from __future__ import annotations

import json
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


class SourceOnlyImportTest(unittest.TestCase):
    def test_one_tex_file_can_be_staged_without_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = prepare_root(root)
            source = root / "incoming.tex"
            source_bytes = b"\\documentclass{article}\n\\title{Emergency Paper}\n"
            source.write_bytes(source_bytes)

            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-tex",
                    str(source),
                    "--published-at",
                    "2026-07-16T12:00:00+09:00",
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

            imported = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "import-pdf",
                    str(source),
                    "--published-at",
                    "2026-07-16T12:00:00+09:00",
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


if __name__ == "__main__":
    unittest.main()
