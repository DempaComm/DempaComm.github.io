"""Run isolated LaTeXML trials without changing protected paper sources."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.dates import local_now_isoformat
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path


@dataclass(frozen=True)
class LaTeXMLTarget:
    paper_dir: Path
    paper: Paper
    source: Path
    category: str


def _tex_source(paper_dir: Path, paper: Paper) -> Path:
    if paper.build.root:
        root = safe_relative_path(paper.build.root, PaperToolError)
        if root.suffix.casefold() == ".tex":
            return paper_dir / root
    candidates = [
        paper_dir / safe_relative_path(entry.path, PaperToolError)
        for entry in paper.files
        if entry.role == "manuscript" and Path(entry.path).suffix.casefold() == ".tex"
    ]
    if not candidates:
        raise PaperToolError(f"LaTeXMLで変換できるTeX原稿がありません: {paper.slug}")
    return candidates[0]


def configured_targets(
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    requested_slugs: Iterable[str] = (),
) -> tuple[LaTeXMLTarget, ...]:
    by_slug = {paper.slug: (path.parent, paper) for path, paper in papers}
    requested = tuple(requested_slugs)
    if requested:
        entries = [{"slug": slug, "category": "手動指定"} for slug in requested]
    else:
        config_path = root / "experiments" / "latexml-trial.json"
        if not config_path.is_file():
            raise PaperToolError(f"LaTeXML試験設定がありません: {config_path}")
        config = read_json(config_path)
        if config.get("schema_version") != 1 or not isinstance(config.get("papers"), list):
            raise PaperToolError(f"LaTeXML試験設定の形式が不正です: {config_path}")
        entries = config["papers"]
    slugs = [entry.get("slug", "") for entry in entries]
    if len(slugs) != len(set(slugs)):
        raise PaperToolError("LaTeXML試験対象の原稿番号が重複しています")
    missing = sorted(set(slugs) - set(by_slug))
    if missing:
        raise PaperToolError("LaTeXML試験対象が未登録です: " + ", ".join(missing))
    targets = []
    for entry in entries:
        slug = entry.get("slug")
        category = entry.get("category")
        if not isinstance(slug, str) or not isinstance(category, str) or not category.strip():
            raise PaperToolError("LaTeXML試験対象にはslugとcategoryが必要です")
        paper_dir, paper = by_slug[slug]
        targets.append(LaTeXMLTarget(paper_dir, paper, _tex_source(paper_dir, paper), category))
    return tuple(targets)


def _tool_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--VERSION"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return (result.stdout or result.stderr).strip().splitlines()[0]


def run_latexml_trial(
    *,
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    output: Path,
    requested_slugs: Iterable[str] = (),
    timeout: int = 180,
) -> dict:
    executable = shutil.which("latexmlc")
    if executable is None:
        raise PaperToolError(
            "latexmlcが見つかりません。macOSでは `brew install latexml` で導入してから再実行してください"
        )
    if timeout < 10:
        raise PaperToolError("LaTeXMLのtimeoutは10秒以上にしてください")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise PaperToolError(
            f"LaTeXML出力先が空ではありません: {output}（別の--outputを指定してください）"
        )
    output.mkdir(parents=True, exist_ok=True)
    targets = configured_targets(root, papers, requested_slugs)
    results = []
    for target in targets:
        target_dir = output / target.paper.slug
        target_dir.mkdir()
        destination = target_dir / "index.html"
        log = target_dir / "latexml.log"
        command = [
            executable,
            f"--destination={destination}",
            "--format=html5",
            "--presentationmathml",
            f"--timeout={timeout}",
            "--expire=-1",
            f"--log={log}",
            str(target.source.relative_to(target.paper_dir)),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=target.paper_dir,
                capture_output=True,
                text=True,
                timeout=timeout + 30,
                check=False,
            )
            log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            warning_count = sum(line.startswith("Warning:") for line in log_text.splitlines())
            error_count = sum(line.startswith("Error:") for line in log_text.splitlines())
            has_error_markup = destination.is_file() and "ltx_ERROR" in destination.read_text(
                encoding="utf-8", errors="replace"
            )
            if not destination.is_file() or completed.returncode != 0:
                status = "failed"
            elif error_count or has_error_markup:
                status = "partial"
            elif warning_count:
                status = "generated-with-warnings"
            else:
                status = "generated"
            error = "" if status != "failed" else (completed.stderr or completed.stdout)[-4000:]
        except subprocess.TimeoutExpired as exception:
            status = "failed"
            error = f"Python側の制限時間を超過しました: {exception}"
            warning_count = 0
            error_count = 0
            has_error_markup = False
        results.append(
            {
                "slug": target.paper.slug,
                "title": target.paper.title,
                "category": target.category,
                "source": str(target.source.relative_to(target.paper_dir)),
                "status": status,
                "html": f"{target.paper.slug}/index.html" if destination.is_file() else "",
                "log": f"{target.paper.slug}/latexml.log" if log.is_file() else "",
                "warning_count": warning_count,
                "error_count": error_count,
                "error_markup": has_error_markup,
                "error": error,
            }
        )
    report = {
        "schema_version": 1,
        "generated_at": local_now_isoformat(),
        "tool": "LaTeXML",
        "version": _tool_version(executable),
        "publishable": False,
        "manual_review_required": True,
        "results": results,
    }
    write_json(output / "report.json", report)
    return report
