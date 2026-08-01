from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from . import __version__
from .converter import ConversionResult, convert_document


GENERATED_NAMES = ("pandoc-ast.json", "main.saty", "dempa.satyh", "conversion-report.json", "satysfi.log", "main.pdf")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LaTeXをPandoc AST経由でSATySFiへ安全に変換する")
    parser.add_argument("input", type=Path, help="入力LaTeXファイル")
    parser.add_argument("--output-dir", required=True, type=Path, help="新規または空の隔離出力先")
    parser.add_argument("--pandoc", default="pandoc", help="Pandoc実行ファイル")
    parser.add_argument("--satysfi", default="satysfi", help="SATySFi実行ファイル")
    parser.add_argument("--compile", action="store_true", help="生成したSATySFiをPDFへコンパイルする")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report(input_path: Path, result: ConversionResult, pandoc_version: str) -> dict[str, Any]:
    return {
        "converter_version": __version__, "status": "converted" if result.succeeded else "failed",
        "input": {"name": input_path.name, "sha256": _sha256(input_path)},
        "pandoc_version": pandoc_version, "manual_review_required": True, "publishable": False,
        "rules": result.rule_report(), "labels": dict(sorted(result.labels.items())),
        "references": sorted(result.references), "warnings": result.warnings,
        "errors": sorted(set(result.errors)),
    }


def _ensure_output(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"出力先はディレクトリではありません: {output_dir}")
    if output_dir.exists():
        collisions = [name for name in GENERATED_NAMES if (output_dir / name).exists()]
        if collisions:
            raise ValueError("既存出力を上書きしません: " + ", ".join(collisions))
    else:
        output_dir.mkdir(parents=True)


def _style_path() -> Path:
    return Path(__file__).resolve().parent / "styles" / "dempa.satyh"


def run(args: argparse.Namespace) -> int:
    input_path = args.input.resolve()
    output_dir = args.output_dir.resolve()
    if not input_path.is_file():
        print(f"入力ファイルがありません: {input_path}", file=sys.stderr)
        return 1
    try:
        _ensure_output(output_dir)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="dempa-satysfi-") as temporary:
        temporary_path = Path(temporary)
        copied_input = temporary_path / input_path.name
        shutil.copy2(input_path, copied_input)
        ast_temporary = temporary_path / "pandoc-ast.json"
        version = subprocess.run([args.pandoc, "--version"], capture_output=True, text=True, check=False)
        pandoc_version = version.stdout.splitlines()[0] if version.returncode == 0 else "unknown"
        completed = subprocess.run(
            [args.pandoc, "--standalone", "--from=latex", "--to=json", "--metadata=date:",
             str(copied_input), "--output", str(ast_temporary)],
            cwd=temporary_path, capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            report = {
                "converter_version": __version__, "status": "failed",
                "input": {"name": input_path.name, "sha256": _sha256(input_path)},
                "pandoc_version": pandoc_version, "manual_review_required": True, "publishable": False,
                "rules": [], "labels": {}, "references": [], "warnings": [],
                "errors": ["PANDOC_FAILED: " + completed.stderr.strip()],
            }
            (output_dir / "conversion-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 2
        ast_text = ast_temporary.read_text(encoding="utf-8")
        (output_dir / "pandoc-ast.json").write_text(ast_text, encoding="utf-8")
        document = json.loads(ast_text)

    result = convert_document(document)
    report = _report(input_path, result, pandoc_version)
    report_path = output_dir / "conversion-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result.succeeded:
        return 2
    (output_dir / "main.saty").write_text(result.satysfi or "", encoding="utf-8")
    shutil.copyfile(_style_path(), output_dir / "dempa.satyh")

    if args.compile:
        compiled = subprocess.run(
            [args.satysfi, "main.saty", "-o", "main.pdf"], cwd=output_dir,
            env=dict(os.environ), capture_output=True, check=False,
        )
        log = (compiled.stdout + compiled.stderr).decode("utf-8", errors="replace")
        (output_dir / "satysfi.log").write_text(log, encoding="utf-8")
        compiler_warnings = sorted({
            line.strip() for line in log.splitlines() if "[Warning]" in line
        })
        report["warnings"] = report["warnings"] + [
            "SATYSFI_WARNING: " + warning for warning in compiler_warnings
        ]
        if compiled.returncode != 0:
            report["status"] = "compile_failed"
            report["errors"] = report["errors"] + ["SATYSFI_COMPILE_FAILED"]
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 3
        report["status"] = "compiled"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
