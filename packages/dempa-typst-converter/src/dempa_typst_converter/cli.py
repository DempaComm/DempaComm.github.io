"""Command-line entry point for conservative Tylax post-processing."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

from dempa_typst_converter.correction import CorrectionResult, correct_tylax_source
from dempa_typst_converter.latex_hints import extract_statement_hints


STYLE_NAME = "dempa-style.typ"


def _bundled_style() -> Path:
    return Path(__file__).resolve().parent / "styles" / STYLE_NAME


def _validate_with_typst(result: CorrectionResult) -> CorrectionResult:
    executable = shutil.which("typst")
    if executable is None:
        report = replace(
            result.report,
            review_findings=result.report.review_findings
            + ("Typst executable not found; syntax validation was skipped",),
        )
        return CorrectionResult(result.source, report)
    with tempfile.TemporaryDirectory(prefix="dempa-typst-validate-") as temporary:
        root = Path(temporary)
        source = root / "main.typ"
        source.write_text(result.source, encoding="utf-8")
        if result.requires_style:
            (root / STYLE_NAME).write_bytes(_bundled_style().read_bytes())
        completed = subprocess.run(
            [executable, "compile", "--root", str(root), str(source), str(root / "main.pdf")],
            capture_output=True,
            text=True,
            check=False,
        )
    if completed.returncode == 0:
        return result
    detail = next(
        (line.strip() for line in completed.stderr.splitlines() if line.strip()),
        f"Typst exited with status {completed.returncode}",
    )
    report = replace(
        result.report,
        blocking_findings=result.report.blocking_findings
        + (f"Typst syntax validation failed: {detail}",),
    )
    return CorrectionResult(result.source, report)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Safely post-process Tylax output without changing the source TeX"
    )
    value.add_argument("input", type=Path, help="raw .typ file produced by Tylax")
    value.add_argument("--output", required=True, type=Path, help="corrected .typ path")
    value.add_argument("--report", required=True, type=Path, help="JSON report path")
    value.add_argument(
        "--latex-source",
        type=Path,
        help="read-only original .tex used only to verify optional statement titles",
    )
    return value


def main(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if len({input_path, output_path, report_path}) != 3:
        print("BLOCKED: input, output, and report must use different paths")
        return 2
    existing = [path for path in (output_path, report_path) if path.exists()]
    if existing:
        print("BLOCKED: refusing to overwrite existing files: " + ", ".join(map(str, existing)))
        return 2
    source = input_path.read_text(encoding="utf-8")
    statement_hints = None
    if args.latex_source is not None:
        latex_path = args.latex_source.expanduser().resolve()
        statement_hints = extract_statement_hints(latex_path.read_text(encoding="utf-8"))
    result = correct_tylax_source(source, statement_hints)
    style_output = output_path.parent / STYLE_NAME
    bundled_style = _bundled_style()
    if result.requires_style and style_output.exists():
        if style_output.read_bytes() != bundled_style.read_bytes():
            print(f"BLOCKED: refusing to overwrite a different style file: {style_output}")
            return 2
    if result.safe_to_write:
        result = _validate_with_typst(result)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result.report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not result.safe_to_write:
        for finding in result.report.blocking_findings:
            print(f"BLOCKED: {finding}")
        print(f"REPORT: {report_path}")
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if result.requires_style and not style_output.exists():
        style_output.write_bytes(bundled_style.read_bytes())
    output_path.write_text(result.source, encoding="utf-8")
    print(f"WROTE: {output_path}")
    print(f"REPORT: {report_path}")
    for finding in result.report.review_findings:
        print(f"REVIEW: {finding}")
    print("MANUAL REVIEW REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
