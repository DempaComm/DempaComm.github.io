from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dempa_site.maintenance import apply_local_cleanup, local_cleanup_plan


class LocalCleanupTest(unittest.TestCase):
    def test_only_reviewed_generated_files_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            papers = root / "papers" / "paper"
            papers.mkdir(parents=True)
            (papers / "main.aux").write_text("temporary", encoding="utf-8")
            (papers / "main.tex").write_text("protected", encoding="utf-8")
            numbered_site = root / "_site 2"
            numbered_site.mkdir()
            (numbered_site / "index.html").write_text("copy", encoding="utf-8")
            current_site = root / "_site"
            current_site.mkdir()
            (current_site / "index.html").write_text("current", encoding="utf-8")
            review_root = root / ".privacy-review"
            reviewed = review_root / ("a" * 64)
            unreviewed = review_root / ("b" * 64)
            overridden = review_root / ("c" * 64)
            reviewed.mkdir(parents=True)
            unreviewed.mkdir()
            overridden.mkdir()
            (reviewed / "report.txt").write_text("reviewed", encoding="utf-8")
            (unreviewed / "report.txt").write_text("pending", encoding="utf-8")
            (overridden / "report.txt").write_text("overridden", encoding="utf-8")
            experiment = root / "_experiments"
            experiment.mkdir()
            (experiment / "report.json").write_text("{}", encoding="utf-8")
            paper = SimpleNamespace(
                privacy_reviews=(
                    SimpleNamespace(status="reviewed", source_sha256="a" * 64),
                    SimpleNamespace(status="overridden", source_sha256="c" * 64),
                )
            )

            plan = local_cleanup_plan(root, (paper,), include_experiments=True)
            apply_local_cleanup(plan)

            self.assertFalse(numbered_site.exists())
            self.assertFalse((papers / "main.aux").exists())
            self.assertFalse(reviewed.exists())
            self.assertFalse(overridden.exists())
            self.assertFalse(experiment.exists())
            self.assertTrue(unreviewed.is_dir())
            self.assertTrue((papers / "main.tex").is_file())
            self.assertTrue((current_site / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
