from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.protection.hashes import protected_file_errors
from dempa_site.protection.privacy import require_privacy_review, review_path


class PrivacyProtectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.review_root = self.root / ".privacy-review"
        self.source = self.root / "source.tex"
        self.source.write_text("\\author{Public Name}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_report(
        self,
        *,
        digest: str | None = None,
        status: str = "completed",
        file_type: str = "tex",
        pages: list[str] | None = None,
    ) -> Path:
        directory = review_path(self.review_root, self.source)
        directory.mkdir(parents=True)
        write_json(
            directory / "report.json",
            {
                "schema_version": 1,
                "sha256": digest or sha256_file(self.source),
                "file_type": file_type,
                "manual_review_required": True,
                "rendered_pages": pages or [],
                "inspection_status": status,
            },
        )
        return directory

    def test_review_is_required_and_must_match_the_current_sha(self) -> None:
        with self.assertRaisesRegex(PaperToolError, "run inspect-file first"):
            require_privacy_review(
                self.source, self.review_root, True, None
            )

        self.write_report(digest="0" * 64)
        with self.assertRaisesRegex(PaperToolError, "privacy review is stale"):
            require_privacy_review(
                self.source, self.review_root, True, None
            )

    def test_override_requires_a_reason_and_cannot_mix_with_acknowledgement(self) -> None:
        self.write_report()
        with self.assertRaisesRegex(PaperToolError, "non-empty reason"):
            require_privacy_review(
                self.source, self.review_root, False, "   "
            )
        with self.assertRaisesRegex(PaperToolError, "either --privacy-reviewed"):
            require_privacy_review(
                self.source, self.review_root, True, "alternate review"
            )

    def test_failed_inspection_can_only_continue_as_a_recorded_override(self) -> None:
        self.write_report(status="failed")
        with self.assertRaisesRegex(PaperToolError, "privacy inspection failed"):
            require_privacy_review(
                self.source, self.review_root, True, None
            )
        review = require_privacy_review(
            self.source, self.review_root, False, "manually checked elsewhere"
        )
        self.assertEqual("overridden", review["status"])
        self.assertEqual("manually checked elsewhere", review["reason"])
        self.assertEqual("failed", review["inspection_status"])

    def test_pdf_acknowledgement_requires_every_rendered_page_file(self) -> None:
        self.source = self.root / "source.pdf"
        self.source.write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.write_report(file_type="pdf", pages=["page-1.png"])
        with self.assertRaisesRegex(PaperToolError, "images are missing"):
            require_privacy_review(
                self.source, self.review_root, True, None
            )


class ProtectedHashTest(unittest.TestCase):
    def test_missing_and_changed_files_are_reported_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paper_dir = Path(temporary) / "2026-07-22-01"
            paper_dir.mkdir()
            source = paper_dir / "source.tex"
            source.write_bytes(b"changed")
            manifest_path = paper_dir / "paper.json"
            digest = "0" * 64
            raw = {
                "schema_version": 2,
                "slug": "2026-07-22-01",
                "legacy_slugs": [],
                "title": "Hash test",
                "published_at": "2026-07-22T12:00:00+09:00",
                "sequence": 1,
                "year": 2026,
                "kind": "TeX原稿",
                "math_section": "",
                "summary": "",
                "original_url": "",
                "order": 2026072201,
                "tags": ["数学"],
                "keywords": ["hash"],
                "build": {"enabled": False, "engine": ""},
                "files": [
                    {
                        "path": "source.tex",
                        "role": "manuscript",
                        "label": "TeX",
                        "public": True,
                        "original_sha256": digest,
                        "sha256": digest,
                    },
                    {
                        "path": "missing.bib",
                        "role": "bibliography",
                        "label": "BibTeX",
                        "public": True,
                        "original_sha256": digest,
                        "sha256": digest,
                    },
                ],
                "approved_changes": [],
                "privacy_reviews": [],
            }
            paper = Paper.from_dict(raw, manifest_path)
            errors = protected_file_errors(
                manifest_path, paper, PaperToolError
            )
            self.assertEqual(2, len(errors))
            self.assertIn("SHA-256 mismatch", errors[0])
            self.assertIn("missing", errors[1])
            self.assertEqual(b"changed", source.read_bytes())


if __name__ == "__main__":
    unittest.main()

