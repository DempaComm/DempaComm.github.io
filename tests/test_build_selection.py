from __future__ import annotations

import unittest

from dempa_site.build_selection import changed_paper_slugs


class BuildSelectionTest(unittest.TestCase):
    def test_paper_changes_select_only_affected_slugs(self) -> None:
        self.assertEqual(
            {"2026-07-22-01", "2026-07-23-01"},
            changed_paper_slugs(
                [
                    "papers/2026-07-22-01/main.tex",
                    "papers/2026-07-22-01/figure.png",
                    "papers/2026-07-23-01/paper.json",
                ]
            ),
        )

    def test_empty_change_list_skips_all_builds(self) -> None:
        self.assertEqual(set(), changed_paper_slugs([]))

    def test_change_outside_paper_folders_requests_full_rebuild(self) -> None:
        self.assertIsNone(changed_paper_slugs([".github/workflows/pages.yml"]))


if __name__ == "__main__":
    unittest.main()
