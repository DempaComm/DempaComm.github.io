from __future__ import annotations

import unittest

from dempa_site.features import FeatureResult, feature_result_lines


class FeatureReportingTest(unittest.TestCase):
    def test_report_lists_counts_targets_and_optional_failure_reason(self) -> None:
        lines = feature_result_lines(
            (
                FeatureResult("random", False, "", "generated", phase="generation"),
                FeatureResult("html", False, "2026-07-02-01", "failed", "tool missing", "validation"),
                FeatureResult("typst", False, "", "disabled"),
            )
        )

        self.assertEqual("FEATURES generated=1 failed=1 disabled=1", lines[0])
        self.assertIn("FEATURE generated: random", lines)
        self.assertIn("FEATURE disabled: typst", lines)
        self.assertIn(
            "WARN feature failed: html [2026-07-02-01] "
            "(optional, validation): tool missing",
            lines,
        )


if __name__ == "__main__":
    unittest.main()
