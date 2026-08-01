from __future__ import annotations

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


class ConverterTests(unittest.TestCase):
    def test_structure_and_reference_are_preserved(self) -> None:
        result = convert_document(artificial_document())
        self.assertTrue(result.succeeded, result.errors)
        self.assertIn(r"\dempa-statement-label(`sample`)(`1`)", result.satysfi)
        self.assertIn(r"\ref(`sample`);", result.satysfi)
        self.assertEqual({"sample": "1"}, result.labels)

    def test_unknown_ast_node_stops_without_output(self) -> None:
        document = artificial_document()
        document["blocks"].append({"t": "Table", "c": []})
        result = convert_document(document)
        self.assertFalse(result.succeeded)
        self.assertIsNone(result.satysfi)
        self.assertIn("AST_UNSUPPORTED_BLOCK: Table", result.errors)


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
