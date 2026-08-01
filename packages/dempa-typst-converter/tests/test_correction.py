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
        raw = "/* Begin prop */\n<nab> 命題 @missing\n/* End prop */\n"

        result = correct_tylax_source(raw)

        self.assertFalse(result.safe_to_write)
        self.assertIn(
            "references without a converted statement target: missing",
            result.report.blocking_findings,
        )

    def test_previous_trial_structure_is_converted_without_fixed_numbers(self) -> None:
        raw = """前文． /* Begin df */
定義本文．
/* End df */
/* Begin prop */
<nab> 命題本文．
/* End prop */
_Proof._ 命題 @nab を使う． #h(1fr) $square.stroked$
/* Begin thm */
定理本文．
/* End thm */
"""

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn('#import "dempa-style.typ"', result.source)
        self.assertIn("#definition[", result.source)
        self.assertIn("#proposition[", result.source)
        self.assertIn("] <nab>", result.source)
        self.assertIn("#ref(<nab>, supplement: none)", result.source)
        self.assertIn("#proof[", result.source)
        self.assertIn("#theorem[", result.source)
        self.assertNotIn("命題 2", result.source)

    def test_structures_and_references_in_strings_or_comments_are_preserved(self) -> None:
        raw = '''"/* Begin prop */ fake /* End prop */"
/* Begin prop */
<real> 本文．
/* End prop */
// @real
"@real"
命題 @real
'''

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn('"/* Begin prop */ fake /* End prop */"', result.source)
        self.assertIn("// @real", result.source)
        self.assertIn('"@real"', result.source)
        self.assertIn("命題 #ref(<real>, supplement: none)", result.source)

    def test_duplicate_labels_fail_closed(self) -> None:
        raw = """/* Begin prop */
<same> 一つ目．
/* End prop */
/* Begin thm */
<same> 二つ目．
/* End thm */
"""

        result = correct_tylax_source(raw)

        self.assertFalse(result.safe_to_write)
        self.assertIn(
            "duplicate statement labels: same", result.report.blocking_findings
        )

    def test_unpaired_statement_marker_fails_closed(self) -> None:
        result = correct_tylax_source("/* Begin prop */\n本文\n")

        self.assertFalse(result.safe_to_write)
        self.assertIn(
            "unpaired or unsupported Tylax statement markers remain",
            result.report.blocking_findings,
        )

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
        self.assertTrue(result.safe_to_write)

    def test_latex_commands_in_comments_do_not_block(self) -> None:
        result = correct_tylax_source("/* \\maketitle */\n本文\n")

        self.assertTrue(result.safe_to_write)

    def test_title_separator_is_removed_only_before_maketitle_comment(self) -> None:
        raw = "\\* \\* \\*\n/* \\maketitle */本文\n"

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write)
        self.assertNotIn("\\* \\* \\*", result.source)
        self.assertEqual("tylax-title-separator", result.report.applied_rules[0].rule_id)

    def test_standalone_stars_elsewhere_are_preserved(self) -> None:
        raw = "本文\n\\* \\* \\*\n次の本文\n"

        result = correct_tylax_source(raw)

        self.assertIn("\\* \\* \\*", result.source)
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

    def test_cli_writes_structured_result_with_style(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text(
                "/* Begin prop */\n<p> 本文．\n/* End prop */\n命題 @p\n",
                encoding="utf-8",
            )

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
            self.assertTrue(output.is_file())
            self.assertTrue((root / "dempa-style.typ").is_file())

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
