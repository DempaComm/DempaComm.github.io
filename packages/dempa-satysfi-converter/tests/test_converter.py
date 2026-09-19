from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from dempa_satysfi_converter.converter import convert_document
from dempa_satysfi_converter.math import convert_math


def str_node(text: str) -> dict:
    return {"t": "Str", "c": text}


def artificial_document() -> dict:
    return {
        "pandoc-api-version": [1, 23, 1, 2],
        "meta": {
            "title": {"t": "MetaInlines", "c": [str_node("人工的な例")]},
            "author": {"t": "MetaInlines", "c": [str_node("Example Author")]},
        },
        "blocks": [
            {"t": "Para", "c": [str_node("本文"), {"t": "Space"}, {"t": "Math", "c": [{"t": "InlineMath"}, r"n\in\mathbb{N}"]}]},
            {"t": "Div", "c": [["sample", ["prop"], []], [{"t": "Para", "c": [
                {"t": "Strong", "c": [str_node("命題"), {"t": "Space"}, str_node("1")]},
                str_node("."), {"t": "Space"}, {"t": "Space"},
                {"t": "Emph", "c": [str_node("人工的な命題である．")]},
            ]}]]},
            {"t": "Para", "c": [str_node("命題"), {"t": "Link", "c": [["", [], [["reference-type", "ref"], ["reference", "sample"]]], [str_node("1")], ["#sample", ""]]}]},
        ],
    }


def citation_node(citation_id: str) -> dict:
    return {"t": "Cite", "c": [[{
        "citationId": citation_id,
        "citationPrefix": [],
        "citationSuffix": [],
        "citationMode": {"t": "NormalCitation"},
        "citationNoteNum": 0,
        "citationHash": 0,
    }], [str_node("ignored citeproc display")]]}


def artificial_bibliography_document() -> dict:
    document = artificial_document()
    document["meta"]["title"]["c"].append({
        "t": "Span", "c": [["", [], []], [
            {"t": "LineBreak"}, str_node("副題"),
        ]],
    })
    document["blocks"].append({"t": "Para", "c": [
        str_node("第二文献"), citation_node("second"), {"t": "Space"},
        str_node("https://example.org/notes"),
    ]})
    document["blocks"].append({"t": "Div", "c": [
        ["refs", ["references", "csl-bib-body", "hanging-indent"], []],
        [
            {"t": "Div", "c": [["ref-first", ["csl-entry"], []], [
                {"t": "Para", "c": [str_node("Alice. First article. 2020.")]},
            ]]},
            {"t": "Div", "c": [["ref-second", ["csl-entry"], []], [
                {"t": "Para", "c": [
                    str_node("Bob. Second article. 2021."), {"t": "Space"},
                    {"t": "Link", "c": [
                        ["", [], []], [str_node("https://doi.org/10.1000/example")],
                        ["https://doi.org/10.1000/example", ""],
                    ]},
                ]},
            ]]},
        ],
    ]})
    return document


class MathTests(unittest.TestCase):
    def test_sample_math_normalization(self) -> None:
        result = convert_math(r"A=\{\,n\in\mathbb{N}\mid\text{$n\neq1$かつ条件}\,\}")
        self.assertEqual([], result.errors)
        self.assertIn(r"\brace{", result.source)
        self.assertIn(r"\text!{n≠1かつ条件}", result.source)

    def test_unknown_math_command_stops(self) -> None:
        result = convert_math(r"\mystery{x}")
        self.assertTrue(any("MATH_UNSUPPORTED_COMMAND" in error for error in result.errors))

    def test_factorial_uses_explicit_satysfi_command(self) -> None:
        result = convert_math("n!+1")
        self.assertEqual(r"n\dempa-factorial+1", result.source)
        self.assertEqual([], result.errors)

    def test_commands_needed_for_elementary_number_theory_are_supported(self) -> None:
        result = convert_math(
            r"\sum_{i=1}^k a_i,\ \pi_i,\ \cdots,\ \max G,\ "
            r"A\prec B\iff p\neq q\Longrightarrow x\neq y"
        )
        self.assertEqual([], result.errors)
        self.assertIn(r"\Longleftrightarrow", result.source)
        self.assertIn(r"\dempa-sum{i=1}{k}", result.source)
        self.assertIn(r"\dempa-pi-sub{i}", result.source)

    def test_commands_needed_for_stone_weierstrass_are_supported(self) -> None:
        result = convert_math(
            r"X=\bigcup_{a\in X}U_a=\bigcup_{i=1}^n U_i,\ "
            r"F\equiv G,\ x\le y+\varepsilon,\ ||f-H||<\varepsilon"
        )
        self.assertEqual([], result.errors)
        self.assertIn(r"\dempa-bigcup-sub{a\in X}", result.source)
        self.assertIn(r"\dempa-bigcup{i=1}{n}", result.source)
        self.assertIn(r"F\equiv G", result.source)
        self.assertIn(r"x\leq y+\epsilon", result.source)
        self.assertIn(r"\norm{f-H}<\epsilon", result.source)

    def test_standard_commands_needed_for_clarkson_are_supported(self) -> None:
        result = convert_math(
            r"T\colon L^0(X,\mu)\to L^0(Y,\nu),\ "
            r"\chi_A\subset X,\ \lim_{n\to\infty}\sup \int \mathcal{F},\ "
            r"\mathop{\mathrm{Re}} z,\ \partial f,\ \theta"
        )
        self.assertEqual([], result.errors)
        self.assertIn(r"T\colon-rel L", result.source)
        self.assertIn(r"\mathop{\mathrm{Re}}", result.source)
        self.assertIn(r"\partial f", result.source)

        legacy = convert_math(r"\ell^p,\ \exp(z),\ L\sp{p}")
        self.assertEqual([], legacy.errors)
        self.assertEqual(
            r"\dempa-ell^{p}, \mathrm{exp}(z), L^{p}",
            legacy.source,
        )

    def test_braced_bar_becomes_typed_satysfi_overline(self) -> None:
        result = convert_math(r"c_n\bar{c}_m")
        self.assertEqual([], result.errors)
        self.assertEqual(r"c_{n}\dempa-bar{c}_{m}", result.source)
        self.assertEqual(1, result.rules["MATH_BAR"])

    def test_unbraced_bar_stops(self) -> None:
        result = convert_math(r"\bar c")
        self.assertIn(r"MATH_UNSUPPORTED_COMMAND: \bar", result.errors)

    def test_unbalanced_norm_stops(self) -> None:
        result = convert_math(r"||f-H|<\varepsilon")
        self.assertIn("MATH_UNBALANCED_NORM: double vertical bars must be paired", result.errors)

    def test_operator_bounded_absolute_values_are_supported(self) -> None:
        result = convert_math(r"|Q(0)|=|R(0)-Q(0)|\le||R-Q||")
        self.assertEqual([], result.errors)
        self.assertEqual(
            r"\abs{Q(0)}=\abs{R(0)-Q(0)}\leq\norm{R-Q}",
            result.source,
        )

    def test_latex_norm_delimiters_may_contain_absolute_values(self) -> None:
        result = convert_math(
            r"\|f_{iy}\|_{p_0}^{p_0}=\sum_{j=1}^n"
            r"\left||a_j|^{\frac{p}{p(iy)}}\right|^{p_0}"
        )
        self.assertEqual([], result.errors)
        self.assertEqual(
            r"\norm{f_{iy}}_{p_{0}}^{p_{0}}=\dempa-sum{j=1}{n}"
            r"\abs{\abs{a_{j}}^{\frac{p}{p(iy)}}}^{p_{0}}",
            result.source,
        )
        self.assertEqual(1, result.rules["MATH_NORM"])
        self.assertEqual(2, result.rules["MATH_ABSOLUTE_VALUE"])

    def test_ambiguous_vertical_bar_stops(self) -> None:
        result = convert_math(r"a|b")
        self.assertTrue(any("MATH_UNSUPPORTED_VERTICAL_BAR" in error for error in result.errors))

        chained = convert_math(r"a|b|c")
        self.assertTrue(any("MATH_UNSUPPORTED_VERTICAL_BAR" in error for error in chained.errors))

    def test_align_environment_becomes_satysfi_alignment(self) -> None:
        result = convert_math(
            "\\begin{align}\n&w_n=1\\\\\n&p,q\\in F\\Longrightarrow x\\neq y\n\\end{align}"
        )
        self.assertEqual([], result.errors)
        self.assertEqual(
            r"\align([[${}; ${w_{n}=1}]; [${}; ${p,q\in F\Longrightarrow x\neq y}]]);",
            result.source,
        )

    def test_parenthesized_array_becomes_satysfi_matrix(self) -> None:
        result = convert_math(
            r"A=\left(\begin{array}{cc}1&1\\1&-1\end{array}\right)"
        )
        self.assertEqual([], result.errors)
        self.assertEqual(
            r"A=\dempa-matrix{1}{1}{1}{-1}",
            result.source,
        )
        self.assertEqual(1, result.rules["MATH_MATRIX_ARRAY"])

    def test_array_with_rules_or_missing_parentheses_stops(self) -> None:
        ruled = convert_math(
            r"\left(\begin{array}{c|c}1&2\\3&4\end{array}\right)"
        )
        self.assertTrue(any("MATH_UNSUPPORTED_ARRAY_COLUMNS" in error for error in ruled.errors))
        bare = convert_math(r"\begin{array}{cc}1&2\\3&4\end{array}")
        self.assertTrue(any("MATH_UNSUPPORTED_ARRAY" in error for error in bare.errors))

    def test_array_with_inconsistent_rows_stops(self) -> None:
        result = convert_math(
            r"\left(\begin{array}{cc}1&2\\3\end{array}\right)"
        )
        self.assertIn("MATH_ARRAY_SHAPE: every row must match the column count", result.errors)

    def test_spaced_set_separator_becomes_mid(self) -> None:
        result = convert_math(r"\{n\in\mathbb{N}\ |\ n>0\}")
        self.assertEqual([], result.errors)
        self.assertEqual(r"\brace{n\in\mathbb{N} \mid n>0}", result.source)


class ConverterTests(unittest.TestCase):
    def test_structure_and_reference_are_preserved(self) -> None:
        result = convert_document(artificial_document())
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\dempa-statement-label(`sample`)(`1`)", result.satysfi)
        self.assertIn(r"\ref(`sample`);", result.satysfi)
        self.assertEqual({"sample": "1"}, result.labels)

    def test_unknown_ast_node_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "BlockQuote", "c": []})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.satysfi)
        self.assertIn("AST_UNSUPPORTED_BLOCK: BlockQuote", result.errors)

    def test_simple_table_preserves_cells_math_number_and_caption(self) -> None:
        def cell(inlines: list[dict], *, row_span: int = 1) -> list:
            return [["", [], []], {"t": "AlignDefault"}, row_span, 1, [
                {"t": "Plain", "c": inlines},
            ]]

        rows = [
            [["", [], []], [cell([str_node("項目")]), cell([str_node("値")])]],
            [["", [], []], [cell([str_node("A")]), cell([
                {"t": "Math", "c": [{"t": "InlineMath"}, "n=1"]},
            ])]],
        ]
        document = artificial_document()
        document["blocks"].append({"t": "Table", "c": [
            ["", [], []],
            [None, [{"t": "Plain", "c": [str_node("人工表")]}]],
            [[{"t": "AlignLeft"}, {"t": "ColWidthDefault"}],
             [{"t": "AlignCenter"}, {"t": "ColWidthDefault"}]],
            [["", [], []], []],
            [[["", [], []], 0, [], rows]],
            [["", [], []], []],
        ]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\dempa-table([[{項目}; {値}]; [{A}; {${n=1}}]])", result.satysfi)
        self.assertIn("表 1　人工表", result.satysfi)
        self.assertIn("TABLE_ALIGNMENT_NORMALIZED: column alignment is centered", result.warnings)

        document["blocks"][-1]["c"][4][0][3][0][1][0][2] = 2
        failed = convert_document(document)
        self.assertFalse(failed.succeeded)
        self.assertIn("AST_UNSUPPORTED_TABLE_CELL", failed.errors)

    def test_single_local_figure_preserves_image_and_caption(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Figure", "c": [
            ["", [], [["latex-placement", "h"]]],
            [None, [{"t": "Plain", "c": [
                str_node("人工図 "), {"t": "Math", "c": [{"t": "InlineMath"}, "X"]},
            ]}]],
            [{"t": "Div", "c": [["", ["center"], []], [
                {"t": "Plain", "c": [{"t": "Image", "c": [
                    ["", [], []], [], ["sample.png", ""],
                ]}]},
            ]]}],
        ]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertEqual(["sample.png"], result.images)
        self.assertIn(r"\dempa-image(`sample.png`);", result.satysfi)
        self.assertIn(r"図 1　人工図 ${X}", result.satysfi)
        self.assertIn("FIGURE_PLACEMENT_NOT_PRESERVED: h", result.warnings)
        self.assertTrue(any("IMAGE_SIZE_NORMALIZED: sample.png" in warning for warning in result.warnings))

    def test_unsafe_or_complex_figure_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Figure", "c": [
            ["", [], []], [None, [{"t": "Plain", "c": [str_node("図")]}]],
            [{"t": "Plain", "c": [{"t": "Image", "c": [
                ["", [], []], [], ["../outside.png", ""],
            ]}]}],
        ]})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIn("AST_UNSAFE_IMAGE_PATH: ../outside.png", result.errors)

    def test_citations_bibliography_spans_and_http_links_are_preserved(self) -> None:
        result = convert_document(artificial_bibliography_document())
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn("人工的な例 副題", result.satysfi)
        self.assertIn("第二文献[2]", result.satysfi)
        self.assertIn(r"+dempa-section-unnumbered(`refs`){参考文献}", result.satysfi)
        self.assertIn("* Alice. First article. 2020.", result.satysfi)
        self.assertIn(
            r"\dempa-href(`https://doi.org/10.1000/example`){https://doi.org/10.1000/example}",
            result.satysfi,
        )
        self.assertEqual(1, result.satysfi.count("https://doi.org/10.1000/example`){"))
        self.assertEqual(["second"], result.citations)

    def test_single_and_double_quotes_preserve_delimiters_and_content(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Para", "c": [
            {"t": "Quoted", "c": [{"t": "DoubleQuote"}, [
                str_node("線形写像"), {"t": "Space"},
                {"t": "Emph", "c": [str_node("theorem")]},
            ]]},
            {"t": "Space"},
            {"t": "Quoted", "c": [{"t": "SingleQuote"}, [str_node("補足")]]},
        ]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"“線形写像 \emph{theorem}” ‘補足’", result.satysfi)
        self.assertEqual(2, result.rules["AST_QUOTED"])

    def test_unknown_quote_type_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Para", "c": [{
            "t": "Quoted", "c": [{"t": "TripleQuote"}, [str_node("unsupported")]],
        }]})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIn("AST_UNSUPPORTED_QUOTE_TYPE: TripleQuote", result.errors)

    def test_unresolved_citation_stops_without_output(self) -> None:
        document = artificial_bibliography_document()
        document["blocks"][-2]["c"][1] = citation_node("missing")
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.satysfi)
        self.assertIn("AST_UNRESOLVED_CITATION: missing", result.errors)

    def test_styled_span_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Para", "c": [{
            "t": "Span", "c": [["", ["smallcaps"], []], [str_node("Styled")]],
        }]})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIn(
            "AST_UNSUPPORTED_SPAN_ATTRIBUTES: only attribute-free spans are supported",
            result.errors,
        )

    def test_multiblock_proof_preserves_paragraphs_and_places_qed_last(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Div", "c": [["", ["proof"], []], [
            {"t": "Para", "c": [
                {"t": "Emph", "c": [str_node("Proof.")]},
                {"t": "Space"}, str_node("第一段落．"),
            ]},
            {"t": "Para", "c": [str_node("第二段落．"), str_node("\u00a0◻")]},
        ]]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"+p{\dempa-proof-heading{証明.} \fil;第一段落．}", result.satysfi)
        self.assertIn(r"+p{第二段落． \dempa-qed;}", result.satysfi)

    def test_optional_proof_title_replaces_default_heading(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Div", "c": [["", ["proof"], []], [
            {"t": "Para", "c": [
                {"t": "Emph", "c": [str_node("別証明.")]},
                {"t": "Space"}, str_node("本文．"), str_node("\u00a0◻"),
            ]},
        ]]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\dempa-proof-heading{別証明.} \fil;本文．", result.satysfi)
        self.assertNotIn(r"\dempa-proof-heading{証明.} \fil;\emph{別証明.}", result.satysfi)

    def test_english_optional_proof_title_is_not_mistaken_for_default(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Div", "c": [["", ["proof"], []], [
            {"t": "Para", "c": [
                {"t": "Emph", "c": [str_node("Proof by contradiction.")]},
                {"t": "Space"}, str_node("Body."), str_node("\u00a0◻"),
            ]},
        ]]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(
            r"\dempa-proof-heading{Proof by contradiction.} \fil;Body.",
            result.satysfi,
        )

    def test_note_becomes_footnote_and_requires_single_paragraph(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Para", "c": [
            str_node("本文．"),
            {"t": "Note", "c": [{"t": "Para", "c": [
                str_node("注記"), {"t": "Space"},
                {"t": "Math", "c": [{"t": "InlineMath"}, "n=1"]},
            ]}]},
        ]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\dempa-footnote{注記 ${n=1}}", result.satysfi)

        document["blocks"][-1]["c"][-1]["c"].append({"t": "Para", "c": [str_node("続き")]})
        failed = convert_document(document)
        self.assertFalse(failed.succeeded)
        self.assertIn("AST_UNSUPPORTED_NOTE: only one-paragraph notes are supported", failed.errors)

    def test_display_math_is_passed_as_a_math_value(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Para", "c": [
            {"t": "Math", "c": [{"t": "DisplayMath"}, r"a_i=\sum_{j=1}^k b_j"]},
        ]})
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\eqn(${a_{i}=\dempa-sum{j=1}{k} b_{j}});", result.satysfi)

    def test_theorem_optional_title_is_kept_without_pandoc_wrapper_emphasis(self) -> None:
        document = artificial_document()
        theorem = document["blocks"][1]["c"][1][0]["c"]
        theorem[3:3] = [str_node("(副題)."), {"t": "Space"}]
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn("(副題).", result.satysfi)
        self.assertIn("人工的な命題である．", result.satysfi)
        self.assertNotIn(r"\emph{人工的な命題である．}", result.satysfi)

    def test_level_one_headers_preserve_numbering_and_unnumbered_status(self) -> None:
        document = artificial_document()
        document["blocks"][0:0] = [
            {"t": "Header", "c": [1, ["preparation", ["unnumbered"], []], [str_node("準備")]]},
            {"t": "Header", "c": [1, ["main", [], []], [str_node("本論")]]},
        ]
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"+dempa-section-unnumbered(`preparation`){準備}", result.satysfi)
        self.assertIn(r"+dempa-section(`main`)(`1`){本論}", result.satysfi)
        self.assertEqual("1", result.labels["main"])
        self.assertNotIn("preparation", result.labels)

    def test_deeper_header_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append(
            {"t": "Header", "c": [2, ["too-deep", [], []], [str_node("小見出し")]]}
        )
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.satysfi)
        self.assertIn("AST_UNSUPPORTED_HEADER_LEVEL: 2", result.errors)

    def test_theorem_may_contain_paragraphs_and_ordered_lists(self) -> None:
        document = artificial_document()
        theorem_blocks = document["blocks"][1]["c"][1]
        theorem_blocks.extend([
            {"t": "OrderedList", "c": [
                [1, {"t": "Decimal"}, {"t": "Period"}],
                [[{"t": "Para", "c": [
                    {"t": "Emph", "c": [str_node("第一条件である．")]},
                ]}]],
            ]},
            {"t": "Para", "c": [
                {"t": "Emph", "c": [str_node("以上を仮定する．")]},
            ]},
        ])
        result = convert_document(document)
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn("+enumerate{", result.satysfi)
        self.assertIn("* 第一条件である．", result.satysfi)
        self.assertIn("+p{以上を仮定する．}", result.satysfi)
        self.assertNotIn(r"\emph{第一条件である．}", result.satysfi)
        self.assertNotIn(r"\emph{以上を仮定する．}", result.satysfi)

    def test_theorem_with_other_nested_blocks_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"][1]["c"][1].append({"t": "BulletList", "c": []})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.satysfi)
        self.assertTrue(any("AST_THEOREM_SHAPE" in error for error in result.errors))


class CliTests(unittest.TestCase):
    def test_figure_asset_is_copied_and_missing_asset_stops(self) -> None:
        if not shutil.which("pandoc"):
            self.skipTest("Pandoc is not installed")
        package = Path(__file__).resolve().parents[1]
        source_text = r"""\documentclass{article}
\usepackage{graphicx}
\title{人工図版例}
\author{Example Author}
\begin{document}
\begin{figure}
\centering
\includegraphics{sample.png}
\caption{人工的な図}
\end{figure}
\end{document}
"""
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.tex"
            image = root / "sample.png"
            source.write_text(source_text, encoding="utf-8")
            image.write_bytes(png)
            environment = {**os.environ, "PYTHONPATH": str(package / "src")}
            command = [sys.executable, "-m", "dempa_satysfi_converter.cli", str(source), "--output-dir"]
            output = root / "output"
            completed = subprocess.run(command + [str(output)], cwd=package, env=environment, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertEqual(png, (output / "sample.png").read_bytes())
            report = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual(["sample.png"], report["images"])

            image.unlink()
            missing_output = root / "missing-output"
            missing = subprocess.run(command + [str(missing_output)], cwd=package, env=environment, capture_output=True, text=True)
            self.assertEqual(2, missing.returncode)
            missing_report = json.loads((missing_output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertIn("IMAGE_NOT_FOUND: sample.png", missing_report["errors"])
            self.assertFalse((missing_output / "main.saty").exists())

            outside = root / "outside.png"
            outside.write_bytes(png)
            image.symlink_to(outside)
            symlink_output = root / "symlink-output"
            symlinked = subprocess.run(command + [str(symlink_output)], cwd=package, env=environment, capture_output=True, text=True)
            self.assertEqual(2, symlinked.returncode)
            symlink_report = json.loads((symlink_output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertIn("IMAGE_UNSAFE_SYMLINK: sample.png", symlink_report["errors"])
            self.assertFalse((symlink_output / "main.saty").exists())

    def test_cli_is_deterministic_and_does_not_overwrite(self) -> None:
        if not shutil.which("pandoc"):
            self.skipTest("Pandoc is not installed")
        package = Path(__file__).resolve().parents[1]
        source_text = r"""\documentclass{article}
\newtheorem{prop}{命題}
\title{人工的な例}
\author{Example Author}
\begin{document}
本文 $n\in\mathbb{N}$．
\begin{prop}\label{sample}人工的な命題である．\end{prop}
命題\ref{sample}を参照する．
\end{document}
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.tex"
            first = root / "first"
            second = root / "second"
            source.write_text(source_text, encoding="utf-8")
            command = [sys.executable, "-m", "dempa_satysfi_converter.cli", str(source), "--output-dir"]
            environment = {**os.environ, "PYTHONPATH": str(package / "src")}
            one = subprocess.run(command + [str(first)], cwd=package, env=environment, capture_output=True, text=True)
            two = subprocess.run(command + [str(second)], cwd=package, env=environment, capture_output=True, text=True)
            self.assertEqual(0, one.returncode, one.stdout + one.stderr)
            self.assertEqual(0, two.returncode, two.stdout + two.stderr)
            self.assertEqual((first / "main.saty").read_bytes(), (second / "main.saty").read_bytes())
            report_one = json.loads((first / "conversion-report.json").read_text(encoding="utf-8"))
            report_two = json.loads((second / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report_one, report_two)
            repeated = subprocess.run(command + [str(first)], cwd=package, env=environment, capture_output=True, text=True)
            self.assertEqual(1, repeated.returncode)

    def test_generated_satysfi_compiles_without_warnings(self) -> None:
        if not shutil.which("pandoc"):
            self.skipTest("Pandoc is not installed")
        satysfi = shutil.which("satysfi")
        if not satysfi:
            candidate = Path.home() / ".opam" / "satysfi" / "bin" / "satysfi"
            satysfi = str(candidate) if candidate.is_file() else None
        if not satysfi:
            self.skipTest("SATySFi is not installed")
        package = Path(__file__).resolve().parents[1]
        source = package / "examples" / "minimal" / "input.tex"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            environment = {**os.environ, "PYTHONPATH": str(package / "src")}
            completed = subprocess.run(
                [sys.executable, "-m", "dempa_satysfi_converter.cli", str(source),
                 "--output-dir", str(output), "--compile", "--satysfi", satysfi],
                cwd=package, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            report = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual("compiled", report["status"])
            self.assertEqual([], report["errors"])
            self.assertEqual([], report["warnings"])
            self.assertTrue((output / "main.pdf").is_file())

    def test_extended_artificial_document_compiles(self) -> None:
        if not shutil.which("pandoc"):
            self.skipTest("Pandoc is not installed")
        satysfi = shutil.which("satysfi")
        if not satysfi:
            candidate = Path.home() / ".opam" / "satysfi" / "bin" / "satysfi"
            satysfi = str(candidate) if candidate.is_file() else None
        if not satysfi:
            self.skipTest("SATySFi is not installed")
        package = Path(__file__).resolve().parents[1]
        source_text = r"""\documentclass{article}
\usepackage{amsmath,amsthm}
\newtheorem{thm}{定理}
\title{拡張機能の人工例}
\author{Example Author}
\begin{document}
\maketitle
\section*{準備}
人工的な準備である．
\section{本論}
$A=(a_1,\cdots,a_k)$について
\[
[A,B]=\sum_{i=1}^k a_i b_i
\]
とする．
\begin{thm}[副題]
$\pi_i$を射影とすると，次が成り立つ．
\begin{enumerate}
\item $x\le y+\varepsilon$である．
\item $X=\bigcup_{i=1}^n U_i$かつ$F\equiv G$である．
\end{enumerate}
\begin{align}
&x_1=1\\
&p\neq q\Longrightarrow x_p\neq x_q
\end{align}
\end{thm}
\begin{proof}
第一段落である．\par
第二段落である．\footnote{一段落の人工的な注記である．}
\end{proof}
\[
A=\left(\begin{array}{cc}1&1\\1&-1\end{array}\right)
\]
\[
T\colon L^0(X,\mu)\to L^0(Y,\nu),\,
\chi_A\subset X,\, \lim_{n\to\infty}\sup \int \mathcal{F}
\]
\begin{table}
\centering
\caption{人工的な表}
\begin{tabular}{lc}
項目 & 値 \\
A & $n=1$
\end{tabular}
\end{table}
\end{document}
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.tex"
            output = root / "output"
            source.write_text(source_text, encoding="utf-8")
            environment = {**os.environ, "PYTHONPATH": str(package / "src")}
            completed = subprocess.run(
                [sys.executable, "-m", "dempa_satysfi_converter.cli", str(source),
                 "--output-dir", str(output), "--compile", "--satysfi", satysfi],
                cwd=package, env=environment, capture_output=True, text=True,
            )
            report = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                0, completed.returncode,
                completed.stdout + completed.stderr + json.dumps(report, ensure_ascii=False),
            )
            self.assertEqual("compiled", report["status"])
            self.assertEqual([], report["errors"])
            self.assertEqual(
                ["TABLE_ALIGNMENT_NORMALIZED: column alignment is centered"],
                report["warnings"],
            )
            self.assertTrue((output / "main.pdf").is_file())

    def test_artificial_bibliography_compiles_and_reports_bst_difference(self) -> None:
        if not shutil.which("pandoc"):
            self.skipTest("Pandoc is not installed")
        satysfi = shutil.which("satysfi")
        if not satysfi:
            candidate = Path.home() / ".opam" / "satysfi" / "bin" / "satysfi"
            satysfi = str(candidate) if candidate.is_file() else None
        if not satysfi:
            self.skipTest("SATySFi is not installed")
        package = Path(__file__).resolve().parents[1]
        source_text = r"""\documentclass{article}
\title{人工文献例}
\author{Example Author}
\begin{document}
\maketitle
詳細は\cite{sample}と https://example.org/notes を参照する．
\nocite{*}
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
"""
        bibliography_text = r"""@article{sample,
  author = {Example, Alice},
  title = {An Artificial Article},
  journal = {Example Journal},
  year = {2024}
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.tex"
            bibliography = root / "refs.bib"
            output = root / "output"
            source.write_text(source_text, encoding="utf-8")
            bibliography.write_text(bibliography_text, encoding="utf-8")
            environment = {**os.environ, "PYTHONPATH": str(package / "src")}
            completed = subprocess.run(
                [sys.executable, "-m", "dempa_satysfi_converter.cli", str(source),
                 "--output-dir", str(output), "--compile", "--satysfi", satysfi],
                cwd=package, env=environment, capture_output=True, text=True,
            )
            report = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                0, completed.returncode,
                completed.stdout + completed.stderr + json.dumps(report, ensure_ascii=False),
            )
            self.assertEqual("compiled", report["status"])
            self.assertEqual([], report["errors"])
            self.assertEqual(["sample"], report["citations"])
            self.assertIn(
                "BIBLIOGRAPHY_STYLE_NOT_PRESERVED: Pandoc citeproc does not apply plain",
                report["warnings"],
            )
            self.assertTrue((output / "main.pdf").is_file())


if __name__ == "__main__":
    unittest.main()
