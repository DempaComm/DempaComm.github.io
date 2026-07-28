from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dempa_site.site.links import local_link_errors, scanned_links_and_ids


class LocalLinkScannerTest(unittest.TestCase):
    def test_scans_quoted_bare_and_entity_encoded_attributes(self) -> None:
        links, ids = scanned_links_and_ids(
            """<main id='本文'><a href="paper/?a=1&amp;b=2#定理">本文</a>
            <link href=styles.css><script src='search.js'></script>
            <img src="ignored.png"><div id=plain></div></main>"""
        )

        self.assertEqual(
            ["paper/?a=1&b=2#定理", "styles.css", "search.js"], links
        )
        self.assertEqual({"本文", "plain"}, ids)

    def test_keeps_missing_target_fragment_and_unsafe_path_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            (site / "index.html").write_text(
                """<a href="present.html#ok">ok</a>
                <a href="present.html#missing">fragment</a>
                <a href="missing.html">missing</a>
                <a href="../outside.html">unsafe</a>""",
                encoding="utf-8",
            )
            (site / "present.html").write_text(
                '<section id="ok"></section>', encoding="utf-8"
            )

            errors = local_link_errors(site)

        self.assertEqual(3, len(errors))
        self.assertTrue(any("missing fragment" in error for error in errors))
        self.assertTrue(any("missing target" in error for error in errors))
        self.assertTrue(any("unsafe link" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
