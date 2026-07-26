"""Run isolated LaTeXML trials without changing protected paper sources."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.dates import local_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path
from dempa_site.protection.privacy import privacy_findings


@dataclass(frozen=True)
class LaTeXMLTarget:
    paper_dir: Path
    paper: Paper
    source: Path
    category: str


@dataclass(frozen=True)
class PreparedGraphic:
    source: str
    page: int
    output: str
    width: str


INCLUDE_GRAPHICS_PATTERN = re.compile(
    r"\\includegraphics\s*(?:\[(?P<options>[^]]*)\])?\s*\{(?P<source>[^{}]+)\}"
)
MISSING_IMAGE_PATTERN = re.compile(
    r'<img\b(?=[^>]*\bclass="[^"]*\bltx_missing_image\b)[^>]*>',
    re.IGNORECASE,
)


def _binding_files(root: Path) -> tuple[Path, ...]:
    binding_dir = root / "experiments" / "latexml-bindings"
    if not binding_dir.is_dir():
        return ()
    return tuple(sorted(binding_dir.glob("*.ltxml")))


def _blocking_reasons(
    *,
    status: str,
    warning_count: int,
    error_count: int,
    has_error_markup: bool,
    title_present: bool,
    conversion_date_visible: bool,
    missing_graphics: int,
    findings: list[str],
) -> list[str]:
    reasons = []
    if status == "failed":
        reasons.append("HTMLを生成できませんでした")
    if warning_count:
        reasons.append(f"LaTeXML警告が{warning_count}件あります")
    if error_count:
        reasons.append(f"LaTeXMLエラーが{error_count}件あります")
    if has_error_markup:
        reasons.append("生成HTMLにltx_ERRORがあります")
    if not title_present:
        reasons.append("生成HTMLに原稿題名がありません")
    if not conversion_date_visible:
        reasons.append("生成HTMLにHTML変換日を表示できませんでした")
    if missing_graphics:
        reasons.append(f"生成HTMLに未変換の図版が{missing_graphics}件あります")
    if findings:
        reasons.append("生成HTMLの簡易個人情報検査に確認事項があります")
    return reasons


def _set_conversion_date(html_text: str, label: str) -> tuple[str, bool]:
    replacement = f'<div class="ltx_dates">HTML変換日：{label}</div>'
    date_pattern = re.compile(r'<div class="ltx_dates">.*?</div>', re.DOTALL)
    if date_pattern.search(html_text):
        return date_pattern.sub(replacement, html_text, count=1), True
    body_pattern = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
    if body_pattern.search(html_text):
        return body_pattern.sub(rf"\1\n{replacement}", html_text, count=1), True
    return html_text, False


def _without_tex_comments(source: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in source.splitlines())


def _prepare_pdf_graphics(
    source: Path, target_dir: Path, timeout: int
) -> tuple[PreparedGraphic, ...]:
    references = []
    other_graphics = []
    for match in INCLUDE_GRAPHICS_PATTERN.finditer(
        _without_tex_comments(source.read_text(encoding="utf-8", errors="replace"))
    ):
        relative = safe_relative_path(match.group("source"), PaperToolError)
        if relative.suffix.casefold() != ".pdf":
            other_graphics.append(str(relative))
            continue
        options = match.group("options") or ""
        page_match = re.search(r"(?:^|,)\s*page\s*=\s*(\d+)\s*(?:,|$)", options)
        page = int(page_match.group(1)) if page_match else 1
        width_match = re.search(
            r"(?:^|,)\s*width\s*=\s*([0-9.]+(?:cm|mm|in|pt|px|em|rem|%))\s*(?:,|$)",
            options,
        )
        width = width_match.group(1) if width_match else ""
        references.append((relative, page, width))
    if not references:
        return ()
    if other_graphics:
        raise PaperToolError(
            "PDFと他形式の図版が混在しているため自動画像化できません: "
            + ", ".join(other_graphics)
        )

    converter = shutil.which("pdftoppm")
    if converter is None:
        raise PaperToolError(
            "PDF図版のHTML変換にはpdftoppmが必要です。macOSでは `brew install poppler` で導入してください"
        )
    prepared_by_key: dict[tuple[Path, int], PreparedGraphic] = {}
    prepared = []
    for relative, page, width in references:
        key = (relative, page)
        graphic = prepared_by_key.get(key)
        if graphic is None:
            pdf_path = source.parent / relative
            if not pdf_path.is_file():
                raise PaperToolError(f"PDF図版がありません: {relative}")
            output_name = f"figure-{len(prepared_by_key) + 1:02d}-page-{page}.png"
            output_prefix = target_dir / output_name.removesuffix(".png")
            completed = subprocess.run(
                [
                    converter,
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-png",
                    "-r",
                    "144",
                    str(pdf_path),
                    str(output_prefix),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output_path = target_dir / output_name
            if completed.returncode != 0 or not output_path.is_file():
                detail = (completed.stderr or completed.stdout).strip()
                raise PaperToolError(
                    f"PDF図版をPNGへ変換できません: {relative} page={page} {detail}"
                )
            graphic = PreparedGraphic(str(relative), page, output_name, "")
            prepared_by_key[key] = graphic
        prepared.append(
            PreparedGraphic(graphic.source, graphic.page, graphic.output, width)
        )
    return tuple(prepared)


def _insert_prepared_graphics(
    html_text: str, graphics: tuple[PreparedGraphic, ...]
) -> tuple[str, int]:
    index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        if index >= len(graphics):
            return match.group(0)
        graphic = graphics[index]
        index += 1
        tag = match.group(0)
        tag = re.sub(
            r'src="[^"]*"',
            f'src="{html.escape(graphic.output, quote=True)}"',
            tag,
            count=1,
        )
        class_match = re.search(r'class="([^"]*)"', tag)
        if class_match:
            classes = [
                value
                for value in class_match.group(1).split()
                if value not in {"ltx_missing", "ltx_missing_image"}
            ]
            tag = (
                tag[: class_match.start(1)]
                + " ".join(classes)
                + tag[class_match.end(1) :]
            )
        width = html.escape(graphic.width, quote=True)
        sizing = f"width:{width};" if width else ""
        tag = tag[:-1] + f' style="{sizing}max-width:100%;height:auto">'
        return tag

    converted = MISSING_IMAGE_PATTERN.sub(replace, html_text)
    missing = len(MISSING_IMAGE_PATTERN.findall(converted))
    if index != len(graphics):
        missing += len(graphics) - index
    return converted, missing


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
    conversion_time = local_now_seconds()
    conversion_date = conversion_time.date().isoformat()
    conversion_date_label = (
        f"{conversion_time.year}年{conversion_time.month}月{conversion_time.day}日"
    )
    targets = configured_targets(root, papers, requested_slugs)
    binding_files = _binding_files(root)
    binding_dir = binding_files[0].parent if binding_files else None
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
            "--nocomments",
            f"--timeout={timeout}",
            "--expire=-1",
            f"--log={log}",
        ]
        if binding_dir is not None:
            command.append(f"--path={binding_dir.resolve()}")
        graphics: tuple[PreparedGraphic, ...] = ()
        missing_graphics = 0
        try:
            graphics = _prepare_pdf_graphics(target.source, target_dir, timeout)
            if graphics:
                command.append("--nographicimages")
            command.append(str(target.source.relative_to(target.paper_dir)))
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
            html_text = (
                destination.read_text(encoding="utf-8", errors="replace")
                if destination.is_file()
                else ""
            )
            html_text, missing_graphics = _insert_prepared_graphics(
                html_text, graphics
            )
            html_text, conversion_date_visible = _set_conversion_date(
                html_text, conversion_date_label
            )
            if destination.is_file():
                destination.write_text(html_text, encoding="utf-8")
            has_error_markup = "ltx_ERROR" in html_text
            title_present = target.paper.title in html_text
            findings = privacy_findings(html_text, "html")
            if not destination.is_file() or completed.returncode != 0:
                status = "failed"
            elif error_count or has_error_markup:
                status = "partial"
            elif warning_count:
                status = "generated-with-warnings"
            else:
                status = "generated"
            error = "" if status != "failed" else (completed.stderr or completed.stdout)[-4000:]
        except (PaperToolError, subprocess.TimeoutExpired) as exception:
            status = "failed"
            error = (
                str(exception)
                if isinstance(exception, PaperToolError)
                else f"Python側の制限時間を超過しました: {exception}"
            )
            warning_count = 0
            error_count = 0
            has_error_markup = False
            title_present = False
            conversion_date_visible = False
            missing_graphics = len(graphics)
            findings = []
        blocking_reasons = _blocking_reasons(
            status=status,
            warning_count=warning_count,
            error_count=error_count,
            has_error_markup=has_error_markup,
            title_present=title_present,
            conversion_date_visible=conversion_date_visible,
            missing_graphics=missing_graphics,
            findings=findings,
        )
        results.append(
            {
                "slug": target.paper.slug,
                "title": target.paper.title,
                "category": target.category,
                "source": str(target.source.relative_to(target.paper_dir)),
                "source_sha256": sha256_file(target.source),
                "status": status,
                "html": f"{target.paper.slug}/index.html" if destination.is_file() else "",
                "log": f"{target.paper.slug}/latexml.log" if log.is_file() else "",
                "warning_count": warning_count,
                "error_count": error_count,
                "error_markup": has_error_markup,
                "title_present": title_present,
                "html_conversion_date": conversion_date,
                "html_conversion_date_visible": conversion_date_visible,
                "graphics": [
                    {
                        "source": graphic.source,
                        "page": graphic.page,
                        "output": f"{target.paper.slug}/{graphic.output}",
                        "converter": "pdftoppm",
                        "width": graphic.width,
                    }
                    for graphic in graphics
                ],
                "missing_graphics": missing_graphics,
                "privacy_findings": findings,
                "comments_removed": True,
                "automatic_checks_passed": not blocking_reasons,
                "blocking_reasons": blocking_reasons,
                "error": error,
            }
        )
    report = {
        "schema_version": 2,
        "generated_at": conversion_time.isoformat(timespec="seconds"),
        "tool": "LaTeXML",
        "version": _tool_version(executable),
        "publishable": False,
        "manual_review_required": True,
        "binding_files": [
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
            }
            for path in binding_files
        ],
        "manual_review_checklist": [
            "題名、著者名などに公開したくない情報がないか",
            "HTML変換日が実際の変換日と一致しているか",
            "日本語が欠落または文字化けしていないか",
            "数式、定理環境、番号、相互参照が元PDFと一致するか",
            "図版、引用、参考文献が欠落していないか",
            "元PDFと意味が変わっていないか",
        ],
        "results": results,
    }
    write_json(output / "report.json", report)
    return report
