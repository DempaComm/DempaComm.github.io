from __future__ import annotations

import tempfile
import unittest
import os
import subprocess
import sys
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.loader import load_manifest
from dempa_site.manifests.notes import record_note
from tests.support import PAPER_TOOL


class CorrectionCommandDataTest(unittest.TestCase):
    def prepared_paper(self, root: Path):
        paper_dir = root / "papers" / "2026-07-28-01"
        html_dir = paper_dir / "html"
        html_dir.mkdir(parents=True)
        source = paper_dir / "source.tex"
        source.write_text("\\documentclass{article}\n", encoding="utf-8")
        html_path = html_dir / "index.html"
        html_path.write_text('<div id="Thm1">定理</div>', encoding="utf-8")
        value = {
            "schema_version": 2,
            "slug": "2026-07-28-01",
            "migration_record_id": "fixture:notes",
            "legacy_slugs": [],
            "title": "訂正試験",
            "published_at": "2026-07-28T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "訂正コマンドの試験です。",
            "original_url": "",
            "order": 2026072801,
            "tags": ["数学"],
            "keywords": ["訂正"],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": "source.tex",
                    "role": "manuscript",
                    "label": "TeX原稿",
                    "public": False,
                    "original_sha256": sha256_file(source),
                    "sha256": sha256_file(source),
                },
                {
                    "path": "html/index.html",
                    "role": "derived-html",
                    "label": "HTML版",
                    "public": True,
                    "original_sha256": sha256_file(html_path),
                    "sha256": sha256_file(html_path),
                },
            ],
            "approved_changes": [],
            "privacy_reviews": [],
            "html_versions": [{
                "status": "approved",
                "generator": "LaTeXML",
                "generator_version": "0.8.8",
                "generated_at": "2026-07-28T12:00:00+09:00",
                "source_path": "source.tex",
                "source_sha256": sha256_file(source),
                "path": "html/index.html",
                "label": "HTML版",
                "reviewed_at": "2026-07-28T12:00:00+09:00",
            }],
        }
        manifest_path = paper_dir / "paper.json"
        write_json(manifest_path, value)
        return manifest_path, load_manifest(manifest_path)

    def test_records_correction_and_addendum_with_optional_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path, paper = self.prepared_paper(Path(temporary))
            record_note(
                manifest_path,
                paper,
                kind="correction",
                summary="仮定を訂正しました。",
                anchor="#Thm1",
                recorded_at="2026-07-28T16:00:00+09:00",
            )
            paper = load_manifest(manifest_path)
            record_note(
                manifest_path,
                paper,
                kind="addendum",
                summary="別証明を追記しました。",
                recorded_at="2026-07-29T10:00:00+09:00",
            )
            updated = load_manifest(manifest_path)

        self.assertEqual(2, len(updated.corrections))
        self.assertEqual("#Thm1", updated.corrections[0].anchor)
        self.assertEqual("addendum", updated.corrections[1].kind)

    def test_rejects_duplicate_or_missing_anchor_without_rewriting_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path, paper = self.prepared_paper(Path(temporary))
            before = manifest_path.read_bytes()
            with self.assertRaisesRegex(PaperToolError, "指定した位置がありません"):
                record_note(
                    manifest_path,
                    paper,
                    kind="correction",
                    summary="訂正",
                    anchor="#missing",
                )
            self.assertEqual(before, manifest_path.read_bytes())

            record_note(
                manifest_path,
                paper,
                kind="correction",
                summary="訂正",
                recorded_at="2026-07-28T16:00:00+09:00",
            )
            paper = load_manifest(manifest_path)
            with self.assertRaisesRegex(PaperToolError, "すでに登録"):
                record_note(
                    manifest_path,
                    paper,
                    kind="correction",
                    summary="訂正",
                )

    def test_invalid_date_restores_original_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path, paper = self.prepared_paper(Path(temporary))
            before = manifest_path.read_bytes()
            with self.assertRaisesRegex(PaperToolError, "ISO 8601"):
                record_note(
                    manifest_path,
                    paper,
                    kind="addendum",
                    summary="追記",
                    recorded_at="not-a-date",
                )
            self.assertEqual(before, manifest_path.read_bytes())

    def test_public_cli_commands_record_both_note_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _paper = self.prepared_paper(root)
            environment = {**os.environ, "PAPER_REPO_ROOT": str(root)}
            correction = subprocess.run(
                [
                    sys.executable,
                    str(PAPER_TOOL),
                    "add-correction",
                    "2026-07-28-01",
                    "--summary",
                    "仮定を訂正しました。",
                    "--anchor",
                    "#Thm1",
                    "--recorded-at",
                    "2026-07-28T16:00:00+09:00",
                ],
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            addendum = subprocess.run(
                [
                    sys.executable,
                    str(PAPER_TOOL),
                    "add-addendum",
                    "2026-07-28-01",
                    "--summary",
                    "別証明を追記しました。",
                    "--recorded-at",
                    "2026-07-29T10:00:00+09:00",
                ],
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            updated = load_manifest(manifest_path)

        self.assertIn("RECORDED 訂正", correction.stdout)
        self.assertIn("RECORDED 追記", addendum.stdout)
        self.assertEqual(["correction", "addendum"], [x.kind for x in updated.corrections])


if __name__ == "__main__":
    unittest.main()
