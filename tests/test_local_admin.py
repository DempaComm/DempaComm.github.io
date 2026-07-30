from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.errors import PaperToolError
from dempa_site.local_admin import (
    LocalAdmin,
    ReviewResult,
    _csrf_field,
    _dashboard,
    _paper_page,
    _require_csrf,
    _review_result_card,
)
from tests.support import prepare_paper_repository


def _paper(root: Path, *, with_html: bool = False) -> tuple[Path, Path]:
    slug = "2026-07-30-01"
    paper_dir = root / "papers" / slug
    paper_dir.mkdir()
    source = paper_dir / "source.tex"
    source.write_text("\\documentclass{article}\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
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
    }
    if with_html:
        html_dir = paper_dir / "html"
        html_dir.mkdir()
        html_file = html_dir / "index.html"
        html_file.write_text("<html><body>old</body></html>\n", encoding="utf-8")
        html_digest = hashlib.sha256(html_file.read_bytes()).hexdigest()
        manifest["files"].append(
            {
                "path": "html/index.html",
                "role": "derived-html",
                "label": "HTML版",
                "public": True,
                "original_sha256": html_digest,
                "sha256": html_digest,
            }
        )
        manifest["html_versions"] = [
            {
                "status": "automatic",
                "generator": "LaTeXML",
                "generator_version": "test",
                "generated_at": "2026-07-30T12:00:00+09:00",
                "source_path": "source.tex",
                "source_sha256": digest,
                "path": "html/index.html",
                "label": "HTML版",
                "reviewed_at": "2026-07-30T12:00:00+09:00",
            }
        ]
    (paper_dir / "paper.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return paper_dir, source


def _trial(root: Path, source: Path) -> Path:
    slug = source.parent.name
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    trial = root / "trial"
    result_dir = trial / slug
    result_dir.mkdir(parents=True)
    (result_dir / "index.html").write_text(
        "<!doctype html><html><head><title>試験</title></head>"
        '<body><article class="ltx_document">new</article></body></html>\n',
        encoding="utf-8",
    )
    (result_dir / "latexml.log").write_text("ok\n", encoding="utf-8")
    (trial / "report.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-07-30T13:00:00+09:00",
                "tool": "LaTeXML",
                "version": "LaTeXML test",
                "results": [
                    {
                        "slug": slug,
                        "source": source.name,
                        "source_sha256": digest,
                        "html": f"{slug}/index.html",
                        "log": f"{slug}/latexml.log",
                        "automatic_checks_passed": True,
                        "privacy_findings": [],
                        "blocking_reasons": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return trial


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
            self.assertIn("承認して事前検査", detail)
            self.assertIn(app.csrf_token, detail)

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

    def test_existing_html_is_retired_before_changed_source_is_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            paper_dir, source = _paper(root, with_html=True)
            source.write_text("\\documentclass{article}\n% revised\n", encoding="utf-8")
            app = LocalAdmin(root)
            app.preflight = lambda: "事前検査成功"  # type: ignore[method-assign]

            result = app.approve_reviewed_change(
                "2026-07-30-01", ["source.tex"], "本文更新"
            )

            manifest = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            self.assertFalse((paper_dir / "html").exists())
            self.assertNotIn("html_versions", manifest)
            self.assertNotIn("html/index.html", [item["path"] for item in manifest["files"]])
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                next(
                    item
                    for item in manifest["files"]
                    if item["path"] == "source.tex"
                )["sha256"],
            )
            self.assertIn("旧HTMLを回復可能な隔離領域へ退避", result)
            backups = list(
                (root / "_experiments" / "local-admin" / "retired-html").glob(
                    "*/html/index.html"
                )
            )
            self.assertEqual(1, len(backups))

    def test_retired_html_is_restored_when_approval_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            paper_dir, source = _paper(root, with_html=True)
            source.write_text("\\documentclass{article}\n% revised\n", encoding="utf-8")
            original_manifest = (paper_dir / "paper.json").read_bytes()

            with self.assertRaisesRegex(PaperToolError, "not protected"):
                LocalAdmin(root).approve_reviewed_change(
                    "2026-07-30-01", ["missing.tex"], "本文更新"
                )

            self.assertEqual(original_manifest, (paper_dir / "paper.json").read_bytes())
            self.assertTrue((paper_dir / "html" / "index.html").is_file())

    def test_existing_html_can_be_replaced_by_reviewed_trial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            paper_dir, source = _paper(root, with_html=True)
            trial = _trial(root, source)
            app = LocalAdmin(root)
            app._trials["reviewed-trial"] = ("2026-07-30-01", trial)

            published = app.publish_trial("2026-07-30-01", "reviewed-trial")

            manifest = json.loads((paper_dir / "paper.json").read_text(encoding="utf-8"))
            self.assertEqual("papers/2026-07-30-01/html/index.html", published)
            self.assertIn("new", (paper_dir / "html" / "index.html").read_text())
            self.assertEqual("html/index.html", manifest["html_versions"][0]["path"])
            backups = list(
                (root / "_experiments" / "local-admin" / "retired-html").glob(
                    "*/html/index.html"
                )
            )
            self.assertEqual(1, len(backups))
            self.assertIn("old", backups[0].read_text(encoding="utf-8"))

    def test_csrf_token_is_required_and_embedded_in_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            app = LocalAdmin(root)
            self.assertIn(app.csrf_token, _csrf_field(app))
            with self.assertRaisesRegex(PaperToolError, "操作確認トークン"):
                _require_csrf(app, {})
            _require_csrf(app, {"csrf": [app.csrf_token]})

    def test_baseline_is_not_written_when_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_paper_repository(root)
            baseline = root / "tests" / "fixtures" / "site-baseline.json"
            baseline.parent.mkdir(parents=True)
            baseline.write_text('{"original": true}\n', encoding="utf-8")
            app = LocalAdmin(root)
            app._baseline_previews["preview"] = ("changed: index.html",)

            def fail_preflight() -> str:
                raise PaperToolError("自動テスト: 失敗")

            app.preflight = fail_preflight  # type: ignore[method-assign]
            with patch("dempa_site.local_admin.write_baseline") as write:
                with self.assertRaisesRegex(PaperToolError, "自動テスト: 失敗"):
                    app.accept_baseline("preview", "意図した更新")

            write.assert_not_called()
            self.assertEqual(
                '{"original": true}\n', baseline.read_text(encoding="utf-8")
            )

    def test_pdf_review_card_links_every_rendered_page(self) -> None:
        card = _review_result_card(
            ReviewResult(
                "published.pdf",
                "token",
                "確認事項なし",
                ("page-01.png", "page-02.png"),
            )
        )
        self.assertIn("PDF全ページ画像", card)
        self.assertIn("/files/token/page-01.png", card)
        self.assertIn("/files/token/page-02.png", card)
