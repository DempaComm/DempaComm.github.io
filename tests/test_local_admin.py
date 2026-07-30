from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.local_admin import LocalAdmin, _dashboard, _paper_page
from tests.support import prepare_paper_repository


def _paper(root: Path) -> tuple[Path, Path]:
    slug = "2026-07-30-01"
    paper_dir = root / "papers" / slug
    paper_dir.mkdir()
    source = paper_dir / "source.tex"
    source.write_text("\\documentclass{article}\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (paper_dir / "paper.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "slug": slug,
                "migration_record_id": "fixture:local-admin",
                "legacy_slugs": [],
                "title": "管理画面の試験原稿",
                "published_at": "2026-07-30T12:00:00+09:00",
                "sequence": 1,
                "year": 2026,
                "kind": "単純なTeX",
                "math_section": "その他",
                "summary": "ローカル管理画面の試験です。",
                "original_url": "",
                "order": 2026073001,
                "tags": ["数学"],
                "keywords": ["試験"],
                "build": {"enabled": False, "engine": "platex"},
                "files": [
                    {
                        "path": "source.tex",
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
    return paper_dir, source


class LocalAdminTest(unittest.TestCase):
    def test_dashboard_and_paper_page_show_changed_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            _, source = _paper(root)
            source.write_text("\\documentclass{article}\n% revised\n", encoding="utf-8")

            app = LocalAdmin(root)
            dashboard = _dashboard(app).decode("utf-8")
            detail = _paper_page(app, "2026-07-30-01").decode("utf-8")

            self.assertIn("管理画面の試験原稿", dashboard)
            self.assertIn("未承認: source.tex", dashboard)
            self.assertIn("HTML試験版を生成", detail)
            self.assertIn("承認して全体検査", detail)

    def test_local_file_tokens_cannot_escape_registered_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            report = root / "report"
            report.mkdir()
            (report / "report.txt").write_text("ok", encoding="utf-8")
            app = LocalAdmin(root)
            token = app.token_for(report, "test")

            self.assertEqual(
                (report / "report.txt").resolve(),
                app.readable_file(token, "report.txt"),
            )
            with self.assertRaises(PaperToolError):
                app.readable_file(token, "../index.html")

    def test_trial_refuses_unapproved_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            _, source = _paper(root)
            source.write_text("changed", encoding="utf-8")

            with self.assertRaisesRegex(PaperToolError, "未承認の変更"):
                LocalAdmin(root).create_trial("2026-07-30-01")
