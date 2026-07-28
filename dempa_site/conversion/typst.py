"""Run isolated LaTeX-to-Typst comparison trials."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dempa_site.dates import local_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path


CONVERTERS = ("tylax", "pandoc")


@dataclass(frozen=True)
class TypstTarget:
    paper_dir: Path
    paper: Paper
    source: Path
    category: str


def _find_executable(name: str) -> str | None:
    executable = shutil.which(name)
    if executable is not None:
        return executable
    if name == "t2l":
        cargo_binary = Path.home() / ".cargo" / "bin" / name
        if cargo_binary.is_file():
            return str(cargo_binary)
    return None


def _tex_source(paper_dir: Path, paper: Paper) -> Path:
    if paper.build.root:
        build_root = safe_relative_path(paper.build.root, PaperToolError)
        if build_root.suffix.casefold() == ".tex":
            return paper_dir / build_root
    candidates = [
        paper_dir / safe_relative_path(entry.path, PaperToolError)
        for entry in paper.files
        if entry.role == "manuscript"
        and Path(entry.path).suffix.casefold() == ".tex"
    ]
    if not candidates:
        raise PaperToolError(
            f"Typstへ変換できるTeX原稿がありません: {paper.slug}"
        )
    return candidates[0]


def configured_targets(
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    requested_slugs: Iterable[str] = (),
) -> tuple[TypstTarget, ...]:
    by_slug = {paper.slug: (path.parent, paper) for path, paper in papers}
    requested = tuple(requested_slugs)
    if requested:
        entries = [{"slug": slug, "category": "手動指定"} for slug in requested]
    else:
        config_path = root / "experiments" / "typst-trial.json"
        if not config_path.is_file():
            raise PaperToolError(f"Typst試験設定がありません: {config_path}")
        config = read_json(config_path)
        if (
            config.get("schema_version") != 1
            or not isinstance(config.get("papers"), list)
        ):
            raise PaperToolError(f"Typst試験設定の形式が不正です: {config_path}")
        entries = config["papers"]

    slugs = [entry.get("slug", "") for entry in entries]
    if len(slugs) != len(set(slugs)):
        raise PaperToolError("Typst試験対象の原稿番号が重複しています")
    missing = sorted(set(slugs) - set(by_slug))
    if missing:
        raise PaperToolError("Typst試験対象が未登録です: " + ", ".join(missing))

    targets = []
    for entry in entries:
        slug = entry.get("slug")
        category = entry.get("category")
        if (
            not isinstance(slug, str)
            or not isinstance(category, str)
            or not category.strip()
        ):
            raise PaperToolError("Typst試験対象にはslugとcategoryが必要です")
        paper_dir, paper = by_slug[slug]
        source = _tex_source(paper_dir, paper)
        if not source.is_file():
            raise PaperToolError(f"Typst試験のTeX原稿がありません: {source}")
        targets.append(TypstTarget(paper_dir, paper, source, category))
    return tuple(targets)


def _tool_version(executable: str, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            [executable, *arguments],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return output.splitlines()[0] if output else "unknown"


def _copy_workspace(target: TypstTarget, destination: Path) -> Path:
    ignored = shutil.ignore_patterns(
        ".DS_Store",
        "__pycache__",
        "html",
        "html-*",
        "main.pdf",
        "*.aux",
        "*.bbl",
        "*.blg",
        "*.dvi",
        "*.fdb_latexmk",
        "*.fls",
        "*.log",
        "*.out",
        "*.synctex.gz",
        "*.toc",
    )
    shutil.copytree(target.paper_dir, destination, ignore=ignored)
    return destination / target.source.relative_to(target.paper_dir)


def _converter_command(
    converter: str, executables: dict[str, str], source: Path, output: Path
) -> list[str]:
    if converter == "tylax":
        return [executables["tylax"], str(source), "-o", str(output)]
    if converter == "pandoc":
        return [
            executables["pandoc"],
            "--from=latex",
            "--to=typst",
            "--standalone",
            str(source),
            "-o",
            str(output),
        ]
    raise PaperToolError(f"未知のTypst変換器です: {converter}")


def _display_command(command: list[str], workspace: Path) -> list[str]:
    displayed = []
    for argument in command:
        try:
            displayed.append(str(Path(argument).relative_to(workspace)))
        except (ValueError, OSError):
            displayed.append(Path(argument).name if argument.startswith("/") else argument)
    return displayed


def _run_command(
    command: list[str], *, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _write_log(path: Path, completed: subprocess.CompletedProcess[str]) -> None:
    path.write_text(
        f"returncode: {completed.returncode}\n\n"
        f"[stdout]\n{completed.stdout}\n\n[stderr]\n{completed.stderr}",
        encoding="utf-8",
    )


def _converter_result(
    *,
    converter: str,
    executables: dict[str, str],
    workspace: Path,
    source: Path,
    target_dir: Path,
    timeout: int,
) -> dict:
    workspace_output = workspace / f"{converter}.typ"
    published_output = target_dir / f"{converter}.typ"
    published_pdf = target_dir / f"{converter}.pdf"
    conversion_log = target_dir / f"{converter}.log"
    compile_log = target_dir / f"{converter}-compile.log"
    command = _converter_command(
        converter, executables, source, workspace_output
    )
    record = {
        "converter": converter,
        "status": "failed",
        "command": _display_command(command, workspace),
        "typst_path": "",
        "pdf_path": "",
        "typst_sha256": "",
        "typst_bytes": 0,
        "pdf_bytes": 0,
        "contains_japanese": False,
        "conversion_returncode": None,
        "compile_returncode": None,
        "error": "",
    }
    try:
        completed = _run_command(command, cwd=workspace, timeout=timeout)
        record["conversion_returncode"] = completed.returncode
        _write_log(conversion_log, completed)
        if completed.returncode != 0 or not workspace_output.is_file():
            record["status"] = "conversion-failed"
            return record

        shutil.copy2(workspace_output, published_output)
        typst_text = published_output.read_text(encoding="utf-8", errors="replace")
        record.update(
            {
                "typst_path": published_output.name,
                "typst_sha256": sha256_file(published_output),
                "typst_bytes": published_output.stat().st_size,
                "contains_japanese": any(
                    "\u3040" <= character <= "\u9fff"
                    for character in typst_text
                ),
            }
        )

        workspace_pdf = workspace / f"{converter}.pdf"
        compile_command = [
            executables["typst"],
            "compile",
            "--root",
            str(workspace),
            str(workspace_output),
            str(workspace_pdf),
        ]
        compiled = _run_command(compile_command, cwd=workspace, timeout=timeout)
        record["compile_command"] = _display_command(
            compile_command, workspace
        )
        record["compile_returncode"] = compiled.returncode
        _write_log(compile_log, compiled)
        if compiled.returncode != 0 or not workspace_pdf.is_file():
            record["status"] = "compile-failed"
            return record

        shutil.copy2(workspace_pdf, published_pdf)
        record.update(
            {
                "status": "generated",
                "pdf_path": published_pdf.name,
                "pdf_bytes": published_pdf.stat().st_size,
            }
        )
        return record
    except subprocess.TimeoutExpired as error:
        record["status"] = "timed-out"
        record["error"] = f"{error.cmd[0]} timed out after {timeout} seconds"
        return record
    except (OSError, UnicodeError) as error:
        record["error"] = str(error)
        return record


def _trial_report(
    *,
    generated_at: datetime,
    executables: dict[str, str],
    results: list[dict],
) -> dict:
    return {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "publishable": False,
        "manual_review_required": True,
        "tools": {
            "typst": _tool_version(executables["typst"], "--version"),
            "tylax": _tool_version(executables["tylax"], "--version"),
            "pandoc": _tool_version(executables["pandoc"], "--version"),
        },
        "manual_review_checklist": [
            "日本語が欠落または文字化けしていないか",
            "数式、定理環境、番号、相互参照が元PDFと一致するか",
            "図版、TikZ、引用、参考文献が欠落していないか",
            "変換されたTypstソースが人間に編集可能か",
            "元PDFと意味およびページ内容が変わっていないか",
        ],
        "results": results,
    }


def run_typst_trial(
    *,
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    output: Path,
    requested_slugs: Iterable[str] = (),
    timeout: int = 180,
) -> dict:
    executables = {
        "typst": _find_executable("typst"),
        "tylax": _find_executable("t2l"),
        "pandoc": _find_executable("pandoc"),
    }
    missing = [name for name, path in executables.items() if path is None]
    if missing:
        raise PaperToolError(
            "Typst試験ツールが見つかりません: "
            + ", ".join(missing)
            + "（docs/TYPST_TRIAL.mdの導入手順を確認してください）"
        )
    resolved_executables = {
        name: str(path) for name, path in executables.items() if path is not None
    }
    if timeout < 10:
        raise PaperToolError("Typst試験のtimeoutは10秒以上にしてください")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise PaperToolError(
            f"Typst出力先が空ではありません: {output}"
            "（別の--outputを指定してください）"
        )
    output.mkdir(parents=True, exist_ok=True)
    targets = configured_targets(root, papers, requested_slugs)
    results = []
    for target in targets:
        target_dir = output / target.paper.slug
        target_dir.mkdir()
        converter_results = []
        with tempfile.TemporaryDirectory(prefix=f"typst-{target.paper.slug}-") as temporary:
            workspace = Path(temporary) / "paper"
            source = _copy_workspace(target, workspace)
            for converter in CONVERTERS:
                converter_results.append(
                    _converter_result(
                        converter=converter,
                        executables=resolved_executables,
                        workspace=workspace,
                        source=source,
                        target_dir=target_dir,
                        timeout=timeout,
                    )
                )
        results.append(
            {
                "slug": target.paper.slug,
                "title": target.paper.title,
                "category": target.category,
                "source_path": str(target.source.relative_to(root)),
                "source_sha256": sha256_file(target.source),
                "manual_review_required": True,
                "converters": converter_results,
            }
        )
    report = _trial_report(
        generated_at=local_now_seconds(),
        executables=resolved_executables,
        results=results,
    )
    write_json(output / "report.json", report)
    return report
