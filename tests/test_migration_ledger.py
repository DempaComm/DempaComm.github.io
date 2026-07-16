from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "migration_ledger.py"


class MigrationLedgerTest(unittest.TestCase):
    def test_scan_matches_published_source_and_preserves_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2022" / "11__20" / "ar11" / "sample"
            source_dir.mkdir(parents=True)
            tex = source_dir / "sample.tex"
            pdf = source_dir / "sample.pdf"
            tex.write_bytes(b"original tex")
            pdf.write_bytes(b"%PDF original")
            private_copy = myblog / "MyBlogCOPY" / "private"
            private_copy.mkdir(parents=True)
            (private_copy / "private.tex").write_bytes(b"do not list")

            paper_dir = root / "papers" / "2022-09-10-01"
            paper_dir.mkdir(parents=True)
            manifest = {
                "schema_version": 2,
                "slug": "2022-09-10-01",
                "title": "Published title",
                "published_at": "2022-09-10T23:42:49+09:00",
                "sequence": 1,
                "original_url": "https://example.com/original",
                "tags": ["数学", "解析"],
                "math_section": "解析・測度・確率",
                "build": {"enabled": False, "engine": "platex"},
                "files": [
                    {
                        "original_sha256": hashlib.sha256(tex.read_bytes()).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()
                    },
                ],
            }
            (paper_dir / "paper.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}

            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            csv_path = root / "ledger" / "migration-ledger.csv"
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(1, len(rows))
            self.assertEqual("published", rows[0]["status"])
            self.assertEqual("2022-09-10-01", rows[0]["target_slug"])
            self.assertEqual("sample.tex", rows[0]["tex_files"])
            self.assertNotIn(str(Path(temporary)), rows[0]["source_dir"])
            self.assertNotIn("MyBlogCOPY", rows[0]["source_dir"])

            rows[0]["notes"] = "manual note"
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rescanned = list(csv.DictReader(stream))
            self.assertEqual("manual note", rescanned[0]["notes"])

            checked = subprocess.run(
                [sys.executable, str(TOOL), "check"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("OK  migration ledger", checked.stdout)
            generated = json.loads(
                (root / "ledger" / "migration-ledger.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(1, generated["record_count"])
            self.assertEqual(1, generated["status_counts"]["published"])


if __name__ == "__main__":
    unittest.main()
