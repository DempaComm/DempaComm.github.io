from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.importing.tex import import_tex
from dempa_site.paths import RepositoryPaths


class ImportRollbackTest(unittest.TestCase):
    def test_copy_verification_failure_removes_the_partial_paper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = RepositoryPaths(root)
            paths.papers.mkdir()
            source = root / "incoming.tex"
            source.write_text("\\title{Copy Test}\n", encoding="utf-8")
            review_root = root / ".privacy-review"
            review_dir = review_root / sha256_file(source)
            review_dir.mkdir(parents=True)
            write_json(
                review_dir / "report.json",
                {
                    "schema_version": 1,
                    "sha256": sha256_file(source),
                    "file_type": "tex",
                    "manual_review_required": True,
                    "rendered_pages": [],
                    "inspection_status": "completed",
                },
            )

            def fail_after_partial_copy(_source: Path, target: Path) -> str:
                target.write_bytes(b"partial")
                raise PaperToolError("copy verification failed")

            with patch(
                "dempa_site.importing.common.copy_byte_identical",
                side_effect=fail_after_partial_copy,
            ):
                with self.assertRaisesRegex(
                    PaperToolError, "copy verification failed"
                ):
                    import_tex(
                        paths=paths,
                        review_root=review_root,
                        tex_file=str(source),
                        title=None,
                        published_at="2026-07-22T12:00:00+09:00",
                        sequence=1,
                        original_url=None,
                        privacy_reviewed=True,
                        privacy_override=None,
                    )

            self.assertFalse((paths.papers / "2026-07-22-01").exists())


if __name__ == "__main__":
    unittest.main()
