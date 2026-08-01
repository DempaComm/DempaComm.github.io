from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dempa_typst_converter.correction import correct_tylax_source  # noqa: E402
from dempa_typst_converter.cli import main  # noqa: E402


class CorrectionTest(unittest.TestCase):
    def test_known_math_token_is_corrected_and_reported(self) -> None:
        raw = "$n\\neq1$\n"

        result = correct_tylax_source(raw)

        self.assertEqual("$n != 1$\n", result.source)
        self.assertTrue(result.safe_to_write)
        self.assertEqual("latex-neq", result.report.applied_rules[0].rule_id)
        self.assertTrue(result.report.manual_review_required)
        self.assertFalse(result.report.publishable)

    def test_theorem_markers_and_references_fail_closed(self) -> None:
        raw = "/* Begin prop */\n<nab> 命題\n命題 @nab\n/* End prop */\n"

        result = correct_tylax_source(raw)

        self.assertFalse(result.safe_to_write)
        self.assertGreaterEqual(len(result.report.blocking_findings), 3)

    def test_input_text_is_not_mutated(self) -> None:
        raw = "$a\\neq b$\n"

        correct_tylax_source(raw)

        self.assertEqual("$a\\neq b$\n", raw)

    def test_strings_and_comments_are_not_rewritten(self) -> None:
        raw = '"n\\neq1"\n/* n\\neq1 */\n// n\\neq1\n$n\\neq1$\n'

        result = correct_tylax_source(raw)

        self.assertEqual(
            '"n\\neq1"\n/* n\\neq1 */\n// n\\neq1\n$n != 1$\n',
            result.source,
        )
        self.assertFalse(result.safe_to_write)

    def test_cli_writes_a_safe_result_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text("$n\\neq1$\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        str(raw),
                        "--output",
                        str(output),
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(0, code)
            self.assertEqual("$n != 1$\n", output.read_text(encoding="utf-8"))
            self.assertTrue(report.is_file())

    def test_cli_does_not_write_blocked_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text("/* Begin prop */\n<nab> 命題 @nab\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        str(raw),
                        "--output",
                        str(output),
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(2, code)
            self.assertFalse(output.exists())
            self.assertTrue(report.is_file())

    def test_cli_refuses_to_overwrite_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            report = root / "report.json"
            raw.write_text("$n\\neq1$\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        str(raw),
                        "--output",
                        str(raw),
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(2, code)
            self.assertEqual("$n\\neq1$\n", raw.read_text(encoding="utf-8"))
            self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
