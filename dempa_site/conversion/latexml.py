"""Run isolated LaTeXML trials without changing protected paper sources."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from dempa_site.dates import local_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path
from dempa_site.protection.privacy import privacy_findings
from dempa_site.conversion.latexml_analysis import (
    blocking_reasons as _blocking_reasons,
    effective_warning_lines as _effective_warning_lines,
    has_document_title,
    set_conversion_date as _set_conversion_date,
    svg_findings,
)
from dempa_site.conversion.latexml_graphics import (
    PreparedGraphic,
    _prepare_pdf_graphics,
    _replace_tikzcd_environments,
    _prepare_tikzcd_graphics,
    _insert_prepared_graphics,
    _deduplicate_tikzcd_graphics,
    _link_public_pdf_assets,
)
from dempa_site.conversion.latexml_normalization import (
    _without_tex_comments,
    _normalize_math_inside_text,
    _normalize_cross_row_braces,
    _normalize_quotient_relation,
    _normalize_legacy_math_punctuation,
    _normalize_bigtriangleup_symbol,
    _normalize_left_exponent_function_space,
    _normalize_norm_delimiters,
    _normalize_absolute_value_placeholders,
    _normalize_empty_domain_maps,
    _normalize_continuation_relations,
    _normalize_inverse_image_half_open_intervals,
    _inject_latexml_compat_package,
    _normalize_sized_parentheses,
    _normalize_group_action_dots,
    _normalize_group_map_display,
    _normalize_empty_membership_before_condition,
    _normalize_nocite_all,
)


@dataclass(frozen=True)
class LaTeXMLTarget:
    paper_dir: Path
    paper: Paper
    source: Path
    category: str


def _binding_files(root: Path) -> tuple[Path, ...]:
    binding_dir = root / "experiments" / "latexml-bindings"
    if not binding_dir.is_dir():
        return ()
    return tuple(sorted(binding_dir.glob("*.ltxml")))


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


def _bibliography_files(target: LaTeXMLTarget) -> tuple[Path, ...]:
    files = []
    for entry in target.paper.files:
        if (
            entry.public
            and entry.role == "bibliography"
            and Path(entry.path).suffix.casefold() == ".bib"
        ):
            candidate = target.paper_dir / safe_relative_path(
                entry.path, PaperToolError
            )
            if candidate.is_file():
                files.append(candidate)
    return tuple(files)


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


def unconverted_tex_slugs(
    papers: Iterable[tuple[Path, Paper]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return batch candidates, papers without TeX, and already converted papers."""
    candidates = []
    without_tex = []
    already_converted = []
    for manifest_path, paper in papers:
        if paper.html_versions:
            already_converted.append(paper.slug)
            continue
        try:
            source = _tex_source(manifest_path.parent, paper)
        except PaperToolError:
            without_tex.append(paper.slug)
            continue
        if not source.is_file():
            without_tex.append(paper.slug)
            continue
        candidates.append(paper.slug)
    return tuple(candidates), tuple(without_tex), tuple(already_converted)


def _tool_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--VERSION"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return (result.stdout or result.stderr).strip().splitlines()[0]


@dataclass(frozen=True)
class PreparedLaTeXMLConversion:
    target_dir: Path
    destination: Path
    log: Path
    command: tuple[str, ...]
    temporary_source: Path | None
    bibliography_files: tuple[Path, ...]
    graphics: tuple[PreparedGraphic, ...]
    pdf_graphics: tuple[PreparedGraphic, ...]
    source_normalizations: tuple[dict, ...]


@dataclass(frozen=True)
class LaTeXMLInspection:
    status: str
    error: str
    warning_count: int
    error_count: int
    has_error_markup: bool
    title_present: bool
    conversion_date_visible: bool
    missing_graphics: int
    inline_svg_count: int
    unsafe_svg_findings: tuple[str, ...]
    privacy_findings: tuple[str, ...]
    ignored_warnings: tuple[str, ...]


_NORMALIZATION_STEPS: tuple[
    tuple[str, Callable[[str], tuple[str, int]]], ...
] = (
    ("math-inside-text", _normalize_math_inside_text),
    ("cross-row-braces", _normalize_cross_row_braces),
    ("quotient-relation", _normalize_quotient_relation),
    ("legacy-math-punctuation", _normalize_legacy_math_punctuation),
    ("bigtriangleup-symbol", _normalize_bigtriangleup_symbol),
    ("left-exponent-function-space", _normalize_left_exponent_function_space),
    ("norm-delimiters", _normalize_norm_delimiters),
    ("absolute-value-placeholder", _normalize_absolute_value_placeholders),
    ("empty-domain-map", _normalize_empty_domain_maps),
    ("continuation-relation", _normalize_continuation_relations),
    (
        "inverse-image-half-open-interval",
        _normalize_inverse_image_half_open_intervals,
    ),
    ("sized-parentheses", _normalize_sized_parentheses),
    ("group-action-dots", _normalize_group_action_dots),
    ("group-map-display", _normalize_group_map_display),
    (
        "empty-membership-before-condition",
        _normalize_empty_membership_before_condition,
    ),
)


def _normalization_record(kind: str, count: int) -> dict:
    return {
        "kind": kind,
        "count": count,
        "scope": "temporary-conversion-copy",
    }


def _normalize_conversion_source(
    source: str,
    bibliography_files: tuple[Path, ...],
) -> tuple[str, tuple[dict, ...]]:
    normalizations = []
    for kind, normalize in _NORMALIZATION_STEPS:
        source, count = normalize(source)
        if count:
            normalizations.append(_normalization_record(kind, count))

    source, count = _normalize_nocite_all(source, bibliography_files)
    if count:
        normalizations.append(_normalization_record("nocite-all", count))
    source, count = _inject_latexml_compat_package(source, bibliography_files)
    if count:
        normalizations.append(_normalization_record("latexml-compat-package", count))
    return source, tuple(normalizations)


def _base_conversion_command(
    *,
    executable: str,
    destination: Path,
    log: Path,
    timeout: int,
    binding_dir: Path | None,
    bibliography_files: tuple[Path, ...],
) -> list[str]:
    command = [
        executable,
        f"--destination={destination}",
        "--format=html5",
        "--presentationmathml",
        "--svg",
        "--nocomments",
        f"--timeout={timeout}",
        "--expire=-1",
        f"--log={log}",
    ]
    if binding_dir is not None:
        command.append(f"--path={binding_dir.resolve()}")
    command.extend(
        f"--bibliography={bibliography.resolve()}"
        for bibliography in bibliography_files
    )
    return command


def _prepare_conversion(
    *,
    target: LaTeXMLTarget,
    target_dir: Path,
    executable: str,
    timeout: int,
    binding_dir: Path | None,
    bibliography_files: tuple[Path, ...],
) -> PreparedLaTeXMLConversion:
    destination = target_dir / "index.html"
    log = target_dir / "latexml.log"
    command = _base_conversion_command(
        executable=executable,
        destination=destination,
        log=log,
        timeout=timeout,
        binding_dir=binding_dir,
        bibliography_files=bibliography_files,
    )

    pdf_graphics = _prepare_pdf_graphics(target.source, target_dir, timeout)
    if pdf_graphics:
        command.append("--nographicimages")
    source_text = target.source.read_text(encoding="utf-8", errors="replace")
    normalized_source, tikzcd_graphics = _prepare_tikzcd_graphics(
        target.source, source_text, target_dir, timeout
    )
    normalized_source, source_normalizations = _normalize_conversion_source(
        normalized_source, bibliography_files
    )
    if tikzcd_graphics:
        records = list(source_normalizations)
        insertion = 1 if records and records[0]["kind"] == "math-inside-text" else 0
        records.insert(
            insertion,
            _normalization_record("tikzcd-rasterized", len(tikzcd_graphics)),
        )
        source_normalizations = tuple(records)

    temporary_source = None
    conversion_source = target.source
    if source_normalizations:
        temporary_source = target_dir / ".latexml-normalized.tex"
        temporary_source.write_text(normalized_source, encoding="utf-8")
        conversion_source = temporary_source
    command.append(str(conversion_source))
    return PreparedLaTeXMLConversion(
        target_dir=target_dir,
        destination=destination,
        log=log,
        command=tuple(command),
        temporary_source=temporary_source,
        bibliography_files=bibliography_files,
        graphics=pdf_graphics + tikzcd_graphics,
        pdf_graphics=pdf_graphics,
        source_normalizations=source_normalizations,
    )


def _execute_conversion(
    prepared: PreparedLaTeXMLConversion,
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(prepared.command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
            check=False,
        )
    finally:
        if prepared.temporary_source is not None:
            prepared.temporary_source.unlink(missing_ok=True)


def _inspect_conversion(
    *,
    prepared: PreparedLaTeXMLConversion,
    paper: Paper,
    completed: subprocess.CompletedProcess[str],
    conversion_date_label: str,
) -> LaTeXMLInspection:
    log_text = (
        prepared.log.read_text(encoding="utf-8", errors="replace")
        if prepared.log.is_file()
        else ""
    )
    error_count = sum(line.startswith("Error:") for line in log_text.splitlines())
    html_text = (
        prepared.destination.read_text(encoding="utf-8", errors="replace")
        if prepared.destination.is_file()
        else ""
    )
    html_text = _deduplicate_tikzcd_graphics(
        html_text, prepared.graphics, prepared.target_dir
    )
    html_text = _link_public_pdf_assets(html_text, paper, prepared.target_dir)
    html_text, missing_graphics = _insert_prepared_graphics(
        html_text, prepared.pdf_graphics
    )
    html_text, conversion_date_visible = _set_conversion_date(
        html_text, conversion_date_label
    )
    if prepared.destination.is_file():
        prepared.destination.write_text(html_text, encoding="utf-8")

    warning_lines, ignored_warnings = _effective_warning_lines(
        log_text, html_text, bool(prepared.bibliography_files)
    )
    warning_count = len(warning_lines)
    inline_svg_count, unsafe_svg_findings = svg_findings(html_text)
    has_error_markup = "ltx_ERROR" in html_text
    title_present = has_document_title(html_text)
    findings = privacy_findings(html_text, "html")
    if not prepared.destination.is_file() or completed.returncode != 0:
        status = "failed"
    elif error_count or has_error_markup:
        status = "partial"
    elif warning_count:
        status = "generated-with-warnings"
    else:
        status = "generated"
    error = "" if status != "failed" else (completed.stderr or completed.stdout)[-4000:]
    return LaTeXMLInspection(
        status=status,
        error=error,
        warning_count=warning_count,
        error_count=error_count,
        has_error_markup=has_error_markup,
        title_present=title_present,
        conversion_date_visible=conversion_date_visible,
        missing_graphics=missing_graphics,
        inline_svg_count=inline_svg_count,
        unsafe_svg_findings=tuple(unsafe_svg_findings),
        privacy_findings=tuple(findings),
        ignored_warnings=tuple(ignored_warnings),
    )


def _failed_inspection(
    exception: PaperToolError | subprocess.TimeoutExpired,
    graphics: tuple[PreparedGraphic, ...],
) -> LaTeXMLInspection:
    error = (
        str(exception)
        if isinstance(exception, PaperToolError)
        else f"Python側の制限時間を超過しました: {exception}"
    )
    return LaTeXMLInspection(
        status="failed",
        error=error,
        warning_count=0,
        error_count=0,
        has_error_markup=False,
        title_present=False,
        conversion_date_visible=False,
        missing_graphics=len(graphics),
        inline_svg_count=0,
        unsafe_svg_findings=(),
        privacy_findings=(),
        ignored_warnings=(),
    )


def _result_record(
    *,
    target: LaTeXMLTarget,
    destination: Path,
    log: Path,
    bibliography_files: tuple[Path, ...],
    graphics: tuple[PreparedGraphic, ...],
    source_normalizations: tuple[dict, ...],
    inspection: LaTeXMLInspection,
    conversion_date: str,
) -> dict:
    blocking_reasons = _blocking_reasons(
        status=inspection.status,
        warning_count=inspection.warning_count,
        error_count=inspection.error_count,
        has_error_markup=inspection.has_error_markup,
        title_present=inspection.title_present,
        conversion_date_visible=inspection.conversion_date_visible,
        missing_graphics=inspection.missing_graphics,
        unsafe_svg_findings=inspection.unsafe_svg_findings,
        findings=inspection.privacy_findings,
    )
    return {
        "slug": target.paper.slug,
        "title": target.paper.title,
        "category": target.category,
        "source": str(target.source.relative_to(target.paper_dir)),
        "source_sha256": sha256_file(target.source),
        "status": inspection.status,
        "html": f"{target.paper.slug}/index.html" if destination.is_file() else "",
        "log": f"{target.paper.slug}/latexml.log" if log.is_file() else "",
        "warning_count": inspection.warning_count,
        "error_count": inspection.error_count,
        "error_markup": inspection.has_error_markup,
        "title_present": inspection.title_present,
        "html_conversion_date": conversion_date,
        "html_conversion_date_visible": inspection.conversion_date_visible,
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
        "missing_graphics": inspection.missing_graphics,
        "inline_svg_count": inspection.inline_svg_count,
        "unsafe_svg_findings": list(inspection.unsafe_svg_findings),
        "source_normalizations": list(source_normalizations),
        "bibliographies": [
            {
                "source": str(path.relative_to(target.paper_dir)),
                "sha256": sha256_file(path),
            }
            for path in bibliography_files
        ],
        "ignored_warnings": list(inspection.ignored_warnings),
        "privacy_findings": list(inspection.privacy_findings),
        "comments_removed": True,
        "automatic_checks_passed": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "error": inspection.error,
    }


def _trial_report(
    *,
    root: Path,
    executable: str,
    binding_files: tuple[Path, ...],
    conversion_time: datetime,
    results: list[dict],
) -> dict:
    return {
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


def run_latexml_trial(
    *,
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    output: Path,
    requested_slugs: Iterable[str] = (),
    timeout: int = 180,
    progress: Callable[[int, int, dict], None] | None = None,
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
    results: list[dict] = []
    for position, target in enumerate(targets, start=1):
        target_dir = output / target.paper.slug
        target_dir.mkdir()
        destination = target_dir / "index.html"
        log = target_dir / "latexml.log"
        bibliography_files = _bibliography_files(target)
        prepared = None
        try:
            prepared = _prepare_conversion(
                target=target,
                target_dir=target_dir,
                executable=executable,
                timeout=timeout,
                binding_dir=binding_dir,
                bibliography_files=bibliography_files,
            )
            completed = _execute_conversion(
                prepared, cwd=target.paper_dir, timeout=timeout
            )
            inspection = _inspect_conversion(
                prepared=prepared,
                paper=target.paper,
                completed=completed,
                conversion_date_label=conversion_date_label,
            )
        except (PaperToolError, subprocess.TimeoutExpired) as exception:
            inspection = _failed_inspection(
                exception, prepared.graphics if prepared is not None else ()
            )
        result = _result_record(
            target=target,
            destination=destination,
            log=log,
            bibliography_files=bibliography_files,
            graphics=prepared.graphics if prepared is not None else (),
            source_normalizations=(
                prepared.source_normalizations if prepared is not None else ()
            ),
            inspection=inspection,
            conversion_date=conversion_date,
        )
        results.append(result)
        if progress is not None:
            progress(position, len(targets), result)
    report = _trial_report(
        root=root,
        executable=executable,
        binding_files=binding_files,
        conversion_time=conversion_time,
        results=results,
    )
    write_json(output / "report.json", report)
    return report
