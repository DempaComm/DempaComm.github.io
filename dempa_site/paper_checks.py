"""Focused checks for one paper during an edit cycle."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.config import LATEXMK_ARGS_BY_ENGINE
from dempa_site.errors import PaperToolError
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path
from dempa_site.protection.hashes import protected_file_errors


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class PaperCheckReport:
    slug: str
    protected_files: int
    privacy_receipts: int
    built: bool
    engine: str


def _build_paper(
    manifest_path: Path,
    paper: Paper,
    *,
    run_command: CommandRunner,
    latexmk: str | None,
) -> None:
    executable = latexmk or shutil.which("latexmk")
    if not executable:
        raise PaperToolError(
            "latexmkが見つかりません。ビルドを省く場合は --skip-build を指定してください"
        )
    if not paper.build.root:
        raise PaperToolError(f"build.rootがありません: {paper.slug}")
    root = safe_relative_path(paper.build.root, PaperToolError)
    engine = paper.build.effective_engine
    try:
        engine_argument = LATEXMK_ARGS_BY_ENGINE[engine]
    except KeyError as error:
        raise PaperToolError(f"未対応のTeXエンジンです: {engine}") from error
    command = (
        executable,
        engine_argument,
        "-file-line-error",
        "-halt-on-error",
        "-interaction=nonstopmode",
        str(root),
    )
    completed = run_command(
        command,
        cwd=manifest_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if len(detail) > 4000:
            detail = detail[-4000:]
        raise PaperToolError(
            f"{paper.slug} の{engine}ビルドに失敗しました"
            + (f"\n{detail}" if detail else "")
        )
    if not (manifest_path.parent / "main.pdf").is_file():
        raise PaperToolError(
            f"{paper.slug} のビルド後にmain.pdfがありません"
        )


def check_paper(
    manifest_path: Path,
    paper: Paper,
    *,
    build: bool = True,
    run_command: CommandRunner = subprocess.run,
    latexmk: str | None = None,
) -> PaperCheckReport:
    """Check one approved paper without generating the complete public site."""
    errors = protected_file_errors(manifest_path, paper, PaperToolError)
    if errors:
        details = "\n".join(f"ERR {error}" for error in errors)
        raise PaperToolError(
            "対象原稿に未承認または不足したファイルがあります\n" + details
        )

    keywords = manifest_path.parent / "keywords.txt"
    expected_keywords = rendered_keywords(paper)
    if not keywords.is_file() or keywords.read_text(encoding="utf-8") != expected_keywords:
        raise PaperToolError(
            f"keywords.txtがpaper.jsonと一致しません: {paper.slug}"
        )

    built = False
    if build and paper.build.enabled:
        _build_paper(
            manifest_path,
            paper,
            run_command=run_command,
            latexmk=latexmk,
        )
        built = True

    return PaperCheckReport(
        slug=paper.slug,
        protected_files=len(paper.files),
        privacy_receipts=len(paper.privacy_reviews),
        built=built,
        engine=paper.build.effective_engine if paper.build.enabled else "",
    )
