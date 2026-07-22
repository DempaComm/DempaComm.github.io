from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tools.legacy_migration.review import metadata_review_html


REPO_ROOT = Path(__file__).resolve().parents[1]


class LegacyMigrationIsolationTest(unittest.TestCase):
    def test_private_review_renderer_is_kept_with_legacy_tooling(self) -> None:
        page = metadata_review_html(
            [
                {
                    "record_id": "fixture:1",
                    "local_title": "</script><script>alert(1)</script>",
                    "metadata_match": "unmatched",
                    "metadata_published_at": "",
                    "source_dir": "fixture",
                    "priority_archive": False,
                }
            ]
        )
        self.assertIn("メタデータ候補確認", page)
        self.assertIn("<\\/script><script>alert(1)<\\/script>", page)
        self.assertIn('content="noindex,nofollow,noarchive"', page)

    def test_public_site_modules_do_not_import_legacy_migration_tooling(self) -> None:
        forbidden = ("migration_ledger", "legacy_migration", "ledger/")
        for path in sorted((REPO_ROOT / "dempa_site").rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, source, f"{path} imports legacy state")

    def test_compatibility_script_is_only_a_thin_entry_point(self) -> None:
        path = REPO_ROOT / "scripts" / "migration_ledger.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual([], functions)
        self.assertLess(len(source.splitlines()), 30)
        self.assertIn("from tools.legacy_migration.cli import main", source)


if __name__ == "__main__":
    unittest.main()
