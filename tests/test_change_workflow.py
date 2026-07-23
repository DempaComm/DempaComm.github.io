from __future__ import annotations

import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.loader import load_manifest
from dempa_site.protection.change_workflow import (
    allowed_public_changes,
    review_changes,
    resumable_change_count,
    unexpected_public_differences,
)
from scripts import paper_tool
from tests.support import add_privacy_review_receipt


def prepare_paper(root: Path, *, two_files: bool = False):
    paper_dir = root / "papers" / "2026-07-23-01"
    paper_dir.mkdir(parents=True)
    main = paper_dir / "main.tex"
    main.write_text("\\documentclass{article}\nold\n", encoding="utf-8")
    files = [
        {
            "path": "main.tex",
            "role": "manuscript",
            "label": "TeX原稿",
            "public": True,
            "original_sha256": sha256_file(main),
            "sha256": sha256_file(main),
        }
    ]
    if two_files:
        bib = paper_dir / "refs.bib"
        bib.write_text("old\n", encoding="utf-8")
        files.append(
            {
                "path": "refs.bib",
                "role": "bibliography",
                "label": "BibTeX",
                "public": True,
                "original_sha256": sha256_file(bib),
                "sha256": sha256_file(bib),
            }
        )
    manifest_path = paper_dir / "paper.json"
    write_json(
        manifest_path,
        {
            "schema_version": 2,
            "slug": "2026-07-23-01",
            "migration_record_id": "fixture:change-workflow",
            "legacy_slugs": ["legacy-change"],
            "title": "修正支援",
            "published_at": "2026-07-23T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "修正支援のテストです。",
            "original_url": "",
            "order": 2026072301,
            "tags": ["数学"],
            "keywords": ["修正支援"],
            "build": {"enabled": True, "engine": "lualatex", "root": "main.tex"},
            "files": files,
            "approved_changes": [],
            "privacy_reviews": [
                {
                    "path": "main.tex",
                    "status": "reviewed",
                    "reason": "",
                    "source_sha256": sha256_file(main),
                    "inspection_status": "completed",
                    "recorded_at": "2026-07-23T03:00:00+00:00",
                }
            ],
        },
    )
    return manifest_path, load_manifest(manifest_path, PaperToolError), main


class ChangeWorkflowTest(unittest.TestCase):
    def test_finish_change_requires_explicit_public_acceptance_before_approval(self) -> None:
        args = argparse.Namespace(accept_public_change=False)

        with self.assertRaisesRegex(PaperToolError, "--accept-public-change"):
            paper_tool.command_finish_change(args)

    def test_review_change_creates_a_current_privacy_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, paper, main = prepare_paper(root)
            main.write_text("\\author{Public Name}\nnew\n", encoding="utf-8")

            reviewed = review_changes(
                manifest_path, paper, root / ".privacy-review", ["main.tex"]
            )

            self.assertEqual("main.tex", reviewed[0].path)
            self.assertIn("\\author candidate: Public Name", reviewed[0].findings)
            self.assertTrue((reviewed[0].report_directory / "report.txt").is_file())

    def test_review_change_rejects_an_unrequested_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, paper, main = prepare_paper(root, two_files=True)
            main.write_text("new\n", encoding="utf-8")
            (manifest_path.parent / "refs.bib").write_text("new\n", encoding="utf-8")

            with self.assertRaisesRegex(PaperToolError, "outside requested files"):
                review_changes(
                    manifest_path,
                    paper,
                    root / ".privacy-review",
                    ["main.tex"],
                )

    def test_public_difference_allowlist_is_limited_to_the_selected_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path, paper, _main = prepare_paper(Path(temporary))
            allowed = allowed_public_changes(paper, ["main.tex"])

            self.assertIn("papers/2026-07-23-01/main.tex", allowed)
            self.assertIn("papers/legacy-change/paper.json", allowed)
            self.assertEqual(
                ("changed: papers/other-paper/paper.json",),
                unexpected_public_differences(
                    (
                        "changed: papers/2026-07-23-01/main.tex",
                        "changed: papers/other-paper/paper.json",
                    ),
                    allowed,
                ),
            )

    def test_finish_change_approves_then_checks_before_writing_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, paper, main = prepare_paper(root)
            main.write_text("\\author{Public Name}\nnew\n", encoding="utf-8")
            add_privacy_review_receipt(root, main)
            args = argparse.Namespace(
                slug=paper.slug,
                reason="本文を修正",
                files=["main.tex"],
                privacy_reviewed=True,
                privacy_override=None,
                accept_public_change=True,
                output="_site",
            )
            differences = (
                f"changed: papers/{paper.slug}/main.tex",
                f"changed: papers/{paper.slug}/paper.json",
                "changed: papers/legacy-change/main.tex",
                "changed: papers/legacy-change/paper.json",
            )

            with (
                patch.object(paper_tool, "ROOT", root),
                patch.object(paper_tool, "PAPERS_DIR", root / "papers"),
                patch.object(paper_tool, "PRIVACY_REVIEW_DIR", root / ".privacy-review"),
                patch.object(paper_tool, "manifests", return_value=[(manifest_path, paper)]),
                patch.object(paper_tool, "complete_check_steps", return_value=(object(),)),
                patch.object(paper_tool, "run_check_suite") as run_checks,
                patch.object(paper_tool, "snapshot_differences", return_value=differences),
                patch.object(paper_tool, "write_baseline") as write_snapshot,
                patch.object(paper_tool, "check_baseline") as check_snapshot,
                redirect_stdout(io.StringIO()),
            ):
                paper_tool.command_finish_change(args)

            updated = load_manifest(manifest_path, PaperToolError)
            self.assertEqual(sha256_file(main), updated.files[0].sha256)
            self.assertEqual(
                1,
                resumable_change_count(updated, ["main.tex"], "本文を修正"),
            )
            run_checks.assert_called_once()
            write_snapshot.assert_called_once()
            check_snapshot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
