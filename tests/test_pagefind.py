from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.site.pagefind import PAGEFIND_GLOB, build_pagefind_index


class PagefindIndexTest(unittest.TestCase):
    def prepared_site(self, root: Path) -> Path:
        site = root / "_site"
        (site / "search").mkdir(parents=True)
        (site / "search" / "index.html").write_text("search", encoding="utf-8")
        html = site / "papers" / "2026-07-28-01" / "html"
        html.mkdir(parents=True)
        (html / "index.html").write_text("<h1>位相空間</h1>", encoding="utf-8")
        return site

    def test_primary_latexml_pages_are_indexed_in_japanese(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = self.prepared_site(Path(temporary))
            commands = []

            def successful(command, **_kwargs):
                commands.append(command)
                bundle = site / "pagefind"
                (bundle / "index").mkdir(parents=True)
                (bundle / "fragment").mkdir()
                (bundle / "pagefind.js").write_text("export {};", encoding="utf-8")
                (bundle / "pagefind-entry.json").write_text("{}", encoding="utf-8")
                (bundle / "pagefind-worker.js").write_text("worker", encoding="utf-8")
                (bundle / "wasm.unknown.pagefind").write_bytes(b"wasm")
                (bundle / "pagefind.ja_test.pf_meta").write_bytes(b"meta")
                (bundle / "index" / "test.pf_index").write_bytes(b"index")
                (bundle / "fragment" / "test.pf_fragment").write_bytes(b"fragment")
                return subprocess.CompletedProcess(command, 0, "", "")

            report = build_pagefind_index(
                site,
                executable=("pagefind-for-test",),
                run_command=successful,
            )

        self.assertEqual(1, report.page_count)
        self.assertEqual("pagefind-for-test", commands[0][0])
        self.assertIn(PAGEFIND_GLOB, commands[0])
        self.assertIn("ja", commands[0])

    def test_failed_or_empty_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = self.prepared_site(Path(temporary))

            def failing(command, **_kwargs):
                return subprocess.CompletedProcess(command, 2, "", "index failed")

            with self.assertRaisesRegex(PaperToolError, "index failed"):
                build_pagefind_index(site, run_command=failing)

        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "_site"
            (site / "search").mkdir(parents=True)
            (site / "search" / "index.html").write_text("search")
            with self.assertRaisesRegex(PaperToolError, "HTML版がありません"):
                build_pagefind_index(site)

    def test_incomplete_successful_bundle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = self.prepared_site(Path(temporary))

            def incomplete(command, **_kwargs):
                bundle = site / "pagefind"
                bundle.mkdir()
                (bundle / "pagefind.js").write_text("export {};", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with self.assertRaisesRegex(PaperToolError, "pagefind-entry.json"):
                build_pagefind_index(site, run_command=incomplete)


if __name__ == "__main__":
    unittest.main()
