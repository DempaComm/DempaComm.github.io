from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper
from dempa_site.paper_checks import check_paper


class FocusedPaperCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.paper_dir = Path(self.temporary.name) / "papers" / "2026-07-28-01"
        self.paper_dir.mkdir(parents=True)
        self.source = self.paper_dir / "main.tex"
        self.source.write_text("\\documentclass{article}\n", encoding="utf-8")
        digest = sha256_file(self.source)
        self.manifest_path = self.paper_dir / "paper.json"
        self.value = {
            "schema_version": 1,
            "slug": "2026-07-28-01",
            "migration_record_id": "fixture:focused-check",
            "legacy_slugs": [],
            "title": "対象原稿検査",
            "published_at": "2026-07-28T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "対象記事だけを検査します。",
            "original_url": "",
            "order": 2026072801,
            "tags": ["数学"],
            "keywords": ["高速検査"],
            "build": {"enabled": False, "engine": "", "root": "main.tex"},
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
        }
        self.paper = Paper.from_dict(self.value, self.manifest_path)
        (self.paper_dir / "keywords.txt").write_text(
            rendered_keywords(self.paper), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_approved_paper_can_be_checked_without_building_the_site(self) -> None:
        report = check_paper(self.manifest_path, self.paper)

        self.assertEqual(self.paper.slug, report.slug)
        self.assertEqual(1, report.protected_files)
        self.assertFalse(report.built)

    def test_unapproved_change_is_rejected_before_other_work(self) -> None:
        self.source.write_text("changed\n", encoding="utf-8")

        with self.assertRaisesRegex(PaperToolError, "未承認"):
            check_paper(self.manifest_path, self.paper)

    def test_enabled_build_uses_manifest_engine_and_requires_main_pdf(self) -> None:
        value = dict(self.value)
        value["build"] = {
            "enabled": True,
            "engine": "lualatex",
            "root": "main.tex",
        }
        paper = Paper.from_dict(value, self.manifest_path)
        commands: list[tuple[str, ...]] = []

        def successful(command, **kwargs):
            commands.append(command)
            (Path(kwargs["cwd"]) / "main.pdf").write_bytes(b"%PDF-test")
            return subprocess.CompletedProcess(command, 0, "", "")

        report = check_paper(
            self.manifest_path,
            paper,
            run_command=successful,
            latexmk="latexmk-for-test",
        )

        self.assertTrue(report.built)
        self.assertEqual("lualatex", report.engine)
        self.assertEqual("-lualatex", commands[0][1])

    def test_stale_keywords_are_rejected(self) -> None:
        (self.paper_dir / "keywords.txt").write_text("stale\n", encoding="utf-8")

        with self.assertRaisesRegex(PaperToolError, "keywords.txt"):
            check_paper(self.manifest_path, self.paper)


if __name__ == "__main__":
    unittest.main()
