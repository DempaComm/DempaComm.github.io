from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dempa_typst_converter.correction import correct_tylax_source  # noqa: E402
from dempa_typst_converter.cli import main  # noqa: E402
from dempa_typst_converter.latex_hints import (  # noqa: E402
    StatementHint,
    extract_statement_hints,
)


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

    def test_flattened_fact_and_multiline_lemma_are_recovered(self) -> None:
        raw = """*Fact 1.* _リウビルの定理 本文． _

*Lemma 1.* _補題の本文

 _
"""

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn("#fact[\n  リウビルの定理 本文．\n]", result.source)
        self.assertIn("#lemma[\n  補題の本文\n]", result.source)
        self.assertEqual(2, result.report.schema_version)
        self.assertIn(
            "Tylax flattened optional statement titles into body text for: Fact, Lemma",
            result.report.review_findings,
        )

    def test_latex_hints_separate_only_exact_statement_titles(self) -> None:
        raw = """*Fact 1.* _リウビルの定理 有界な整関数は定数関数である． _

/* Begin thm */
代数学の基本定理 定数でない複素係数多項式は根を持つ．
/* End thm */
"""
        hints = (
            StatementHint("fact", "リウビルの定理"),
            StatementHint("thm", "代数学の基本定理"),
        )

        result = correct_tylax_source(raw, hints)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn(
            "#fact(title: [リウビルの定理])[\n  有界な整関数は定数関数である．\n]",
            result.source,
        )
        self.assertIn(
            "#theorem(title: [代数学の基本定理])[\n  定数でない複素係数多項式は根を持つ．\n]",
            result.source,
        )
        self.assertEqual((), result.report.review_findings)
        self.assertEqual(
            2,
            next(
                rule.replacements
                for rule in result.report.applied_rules
                if rule.rule_id == "statement-titles"
            ),
        )

    def test_mismatched_latex_title_hint_fails_closed(self) -> None:
        raw = "/* Begin thm */本文だけ．/* End thm */\n"

        result = correct_tylax_source(
            raw, (StatementHint("thm", "一致しない題名"),)
        )

        self.assertFalse(result.safe_to_write)
        self.assertIn(
            "statement title does not match Tylax output: 一致しない題名",
            result.report.blocking_findings,
        )

    def test_reordered_latex_statement_hints_fail_closed(self) -> None:
        raw = """/* Begin thm */
定理名 本文．
/* End thm */
*Fact 1.* _事実名 本文． _
"""
        hints = (
            StatementHint("fact", "事実名"),
            StatementHint("thm", "定理名"),
        )

        result = correct_tylax_source(raw, hints)

        self.assertFalse(result.safe_to_write)
        self.assertTrue(
            any(
                finding.startswith("LaTeX and Tylax statement sequences differ:")
                for finding in result.report.blocking_findings
            )
        )

    def test_latex_hint_extraction_ignores_comments_and_post_document_text(self) -> None:
        latex = r"""
% \begin{thm}[コメント]
\begin{comment}
\begin{fact}[無効]
\end{comment}
\begin{fact}[リウビルの定理]
\begin{lemma}
\end{document}
\begin{thm}[文書外]
"""

        self.assertEqual(
            (
                StatementHint("fact", "リウビルの定理"),
                StatementHint("lem", None),
            ),
            extract_statement_hints(latex),
        )

    def test_fact_and_example_markers_use_shared_style(self) -> None:
        raw = """/* Begin fact */
事実本文．
/* End fact */
/* Begin exam */
例本文．
/* End exam */
"""

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn("#fact[", result.source)
        self.assertIn("#example[", result.source)

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

    def test_displaystyle_residue_is_removed_only_inside_math(self) -> None:
        raw = 'display text\n"$display x$"\n$display 1/f$\n'

        result = correct_tylax_source(raw)

        self.assertEqual('display text\n"$display x$"\n$1/f$\n', result.source)
        self.assertTrue(result.safe_to_write)

    def test_fraction_inside_absolute_value_does_not_render_as_set(self) -> None:
        raw = '$ abs({frac(1, f(a))}) < abs({frac(1, f(b))}) $\n'

        result = correct_tylax_source(raw)

        self.assertEqual(
            '$ abs(frac(1, f(a))) < abs(frac(1, f(b))) $\n', result.source
        )
        self.assertTrue(result.safe_to_write)
        self.assertEqual(
            "absolute-fraction-braces", result.report.applied_rules[0].rule_id
        )

    def test_tylax_bibliography_is_rendered_as_numbered_entry(self) -> None:
        raw = '''= References

#show figure.where(kind: "bib"): it => block[#it.caption #it.body]
#figure(kind: "bib", supplement: none, caption: [1])[Book title ] <book>
'''

        result = correct_tylax_source(raw)

        self.assertTrue(result.safe_to_write, result.report.blocking_findings)
        self.assertIn("#heading(numbering: none)[参考文献]", result.source)
        self.assertIn("#bibliography-entry([1], [Book title]) <book>", result.source)
        self.assertNotIn("figure.where", result.source)

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

    def test_cli_uses_latex_source_as_read_only_title_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            latex = root / "original.tex"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text(
                "/* Begin thm */\n定理名 本文．\n/* End thm */\n",
                encoding="utf-8",
            )
            original = "\\begin{thm}[定理名]\n本文．\n\\end{thm}\n"
            latex.write_text(original, encoding="utf-8")

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        str(raw),
                        "--latex-source",
                        str(latex),
                        "--output",
                        str(output),
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(0, code)
            self.assertIn(
                "#theorem(title: [定理名])", output.read_text(encoding="utf-8")
            )
            self.assertEqual(original, latex.read_text(encoding="utf-8"))

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

    def test_cli_typst_validation_rejects_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text("#this-function-does-not-exist[]\n", encoding="utf-8")

            failed_compile = subprocess.CompletedProcess(
                args=["typst", "compile"],
                returncode=1,
                stdout="",
                stderr="error: unknown variable\n",
            )
            with (
                patch(
                    "dempa_typst_converter.cli.shutil.which",
                    return_value="/usr/bin/typst",
                ),
                patch(
                    "dempa_typst_converter.cli.subprocess.run",
                    return_value=failed_compile,
                ),
                redirect_stdout(StringIO()),
            ):
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
            self.assertIn(
                "Typst syntax validation failed",
                report.read_text(encoding="utf-8"),
            )

    def test_cli_records_when_typst_validation_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            raw.write_text("本文．\n", encoding="utf-8")

            with (
                patch("dempa_typst_converter.cli.shutil.which", return_value=None),
                redirect_stdout(StringIO()),
            ):
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
            self.assertIn(
                "Typst executable not found; syntax validation was skipped",
                report.read_text(encoding="utf-8"),
            )

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
