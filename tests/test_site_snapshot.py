from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "site_snapshot.py"


class SiteSnapshotTest(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[dict[str, str], Path, Path]:
        paper = root / "papers" / "2026-07-22-01"
        paper.mkdir(parents=True)
        (paper / "paper.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "slug": "2026-07-22-01",
                    "migration_record_id": "fixture:site-snapshot",
                    "legacy_slugs": ["legacy-paper"],
                    "title": "Snapshot fixture",
                    "published_at": "2026-07-22T12:00:00+09:00",
                    "sequence": 1,
                    "year": 2026,
                    "kind": "TeX原稿",
                    "math_section": "その他",
                    "summary": "公開物スナップショットのテスト用原稿です。",
                    "original_url": "",
                    "order": 2026072201,
                    "tags": ["数学"],
                    "keywords": ["Snapshot fixture"],
                    "build": {"enabled": True, "engine": "", "root": "main.tex"},
                    "files": [
                        {
                            "path": "main.tex",
                            "role": "manuscript",
                            "label": "TeX原稿",
                            "public": False,
                            "original_sha256": "0" * 64,
                            "sha256": "0" * 64,
                        }
                    ],
                    "approved_changes": [],
                    "privacy_reviews": []
                }
            ),
            encoding="utf-8",
        )
        site = root / "_site"
        (site / "papers" / "2026-07-22-01").mkdir(parents=True)
        (site / "papers" / "legacy-paper").mkdir(parents=True)
        (site / "index.html").write_text("original", encoding="utf-8")
        (site / "papers" / "2026-07-22-01" / "main.pdf").write_bytes(b"pdf-a")
        (site / "papers" / "legacy-paper" / "main.pdf").write_bytes(b"pdf-a")
        baseline = root / "baseline.json"
        environment = {**os.environ, "PAPER_REPO_ROOT": str(root)}
        return environment, site, baseline

    def run_tool(
        self, environment: dict[str, str], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generated_pdfs_are_presence_checked_without_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, site, baseline = self.prepare(Path(temporary))
            written = self.run_tool(
                environment, "write", str(site), "--baseline", str(baseline)
            )
            self.assertEqual(0, written.returncode, written.stderr)
            (site / "papers" / "2026-07-22-01" / "main.pdf").write_bytes(b"pdf-b")
            (site / "papers" / "legacy-paper" / "main.pdf").write_bytes(b"pdf-b")
            checked = self.run_tool(
                environment, "check", str(site), "--baseline", str(baseline)
            )
            self.assertEqual(0, checked.returncode, checked.stderr)

    def test_changed_deterministic_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment, site, baseline = self.prepare(Path(temporary))
            written = self.run_tool(
                environment, "write", str(site), "--baseline", str(baseline)
            )
            self.assertEqual(0, written.returncode, written.stderr)
            (site / "index.html").write_text("changed", encoding="utf-8")
            checked = self.run_tool(
                environment, "check", str(site), "--baseline", str(baseline)
            )
            self.assertNotEqual(0, checked.returncode)
            self.assertIn("changed: index.html", checked.stderr)


if __name__ == "__main__":
    unittest.main()
