"""Command-line entry point for conservative Tylax post-processing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dempa_typst_converter.correction import correct_tylax_source


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Safely post-process Tylax output without changing the source TeX"
    )
    value.add_argument("input", type=Path, help="raw .typ file produced by Tylax")
    value.add_argument("--output", required=True, type=Path, help="corrected .typ path")
    value.add_argument("--report", required=True, type=Path, help="JSON report path")
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
    result = correct_tylax_source(source)
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
    output_path.write_text(result.source, encoding="utf-8")
    print(f"WROTE: {output_path}")
    print(f"REPORT: {report_path}")
    print("MANUAL REVIEW REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
