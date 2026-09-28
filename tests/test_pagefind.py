from __future__ import annotations

import subprocess
import gzip
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.site.pagefind import PAGEFIND_GLOB, adapt_japanese_queries, build_pagefind_index


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
                splitter = ("for(const{segment:word}of wordSegmenter.segment(term)){}"
                            "this.loadFragment(id,locations,term)")
                (bundle / "pagefind.js").write_text(splitter, encoding="utf-8")
                (bundle / "pagefind-entry.json").write_text("{}", encoding="utf-8")
                (bundle / "pagefind-worker.js").write_text(splitter, encoding="utf-8")
                (bundle / "wasm.unknown.pagefind").write_bytes(b"wasm")
                (bundle / "pagefind.ja_test.pf_meta").write_bytes(b"meta")
                (bundle / "index" / "test.pf_index").write_bytes(b"index")
                (bundle / "fragment" / "test.pf_fragment").write_bytes(gzip.compress(
                    '{"content":"ディリクレ\\u200b積分"}'.encode("utf-8")))
                return subprocess.CompletedProcess(command, 0, "", "")

            report = build_pagefind_index(
                site,
                executable=("pagefind-for-test",),
                run_command=successful,
            )
            self.assertIn('"ディリクレ"', (report.bundle / "pagefind.js").read_text())
            for name in ("pagefind.js", "pagefind-worker.js"):
                self.assertIn("segmentQuery(term,trueLanguage,wordSegmenter)", (report.bundle / name).read_text())

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

    def test_unrecognized_query_splitter_stops_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            for name in ("pagefind.js", "pagefind-worker.js"):
                (bundle / name).write_text("new bundle format", encoding="utf-8")
            with self.assertRaisesRegex(PaperToolError, "検索処理が想定と異なります"):
                adapt_japanese_queries(bundle)

    @unittest.skipUnless(shutil.which("node") and importlib.util.find_spec("pagefind"),
                         "Pagefind and Node.js are needed for the search integration test")
    def test_japanese_queries_match_the_real_generated_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = self.prepared_site(Path(temporary))
            html = site / "papers" / "2026-07-28-01" / "html" / "index.html"
            html.write_text('<html lang="ja"><head><title>検索検証</title></head><body>'
                            '<article data-pagefind-body><h1>積分</h1>'
                            '<p>ディリクレ積分とパラコンパクト空間を考える。</p>'
                            '</article></body></html>', encoding="utf-8")
            build_pagefind_index(site)
            result = subprocess.run(
                [shutil.which("node"), str(Path(__file__).with_name("pagefind_search.mjs")), str(site)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
