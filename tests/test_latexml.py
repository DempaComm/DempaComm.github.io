from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.conversion.latexml import run_latexml_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper


class LaTeXMLTrialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        paper_dir = self.root / "papers" / "2026-07-26-01"
        paper_dir.mkdir(parents=True)
        source = paper_dir / "main.tex"
        source.write_text("\\documentclass{article}\\begin{document}test\\end{document}", encoding="utf-8")
        digest = sha256_file(source)
        data = {
            "schema_version": 1,
            "slug": "2026-07-26-01",
            "migration_record_id": "fixture:test",
            "legacy_slugs": [],
            "title": "LaTeXML試験",
            "published_at": "2026-07-26T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "試験",
            "original_url": "",
            "order": 2026072601,
            "tags": ["数学"],
            "keywords": ["LaTeXML"],
            "build": {"enabled": True, "engine": "lualatex", "root": "main.tex"},
            "files": [{
                "path": "main.tex",
                "role": "manuscript",
                "label": "TeX原稿",
                "public": True,
                "original_sha256": digest,
                "sha256": digest,
            }],
            "approved_changes": [],
            "privacy_reviews": [],
        }
        manifest_path = paper_dir / "paper.json"
        self.paper = Paper.from_dict(data, manifest_path)
        self.papers = [(manifest_path, self.paper)]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_converter_is_a_clean_error(self) -> None:
        with patch("dempa_site.conversion.latexml.shutil.which", return_value=None):
            with self.assertRaisesRegex(PaperToolError, "brew install latexml"):
                run_latexml_trial(
                    root=self.root,
                    papers=self.papers,
                    output=self.root / "trial",
                    requested_slugs=[self.paper.slug],
                )

    def test_success_writes_derived_html_and_review_report_only(self) -> None:
        def fake_run(command, **_kwargs):
            if "--VERSION" in command:
                return subprocess.CompletedProcess(command, 0, "latexmlc version 0.8.8\n", "")
            destination = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--destination=")))
            log = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--log=")))
            destination.write_text("<html><body>converted</body></html>", encoding="utf-8")
            log.write_text("conversion log", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        output = self.root / "trial"
        with patch("dempa_site.conversion.latexml.shutil.which", return_value="/test/latexmlc"), patch(
            "dempa_site.conversion.latexml.subprocess.run", side_effect=fake_run
        ):
            report = run_latexml_trial(
                root=self.root,
                papers=self.papers,
                output=output,
                requested_slugs=[self.paper.slug],
            )

        self.assertEqual("generated", report["results"][0]["status"])
        self.assertTrue(report["manual_review_required"])
        self.assertFalse(report["publishable"])
        self.assertTrue((output / self.paper.slug / "index.html").is_file())
        self.assertTrue((output / "report.json").is_file())
        self.assertEqual("\\documentclass{article}\\begin{document}test\\end{document}", (self.paper.source_path.parent / "main.tex").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
