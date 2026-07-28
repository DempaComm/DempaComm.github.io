"""Run isolated LaTeXML trials without changing protected paper sources."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
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
        if paper.html_version is not None:
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
    results = []
    for position, target in enumerate(targets, start=1):
        target_dir = output / target.paper.slug
        target_dir.mkdir()
        destination = target_dir / "index.html"
        log = target_dir / "latexml.log"
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
        bibliography_files = _bibliography_files(target)
        for bibliography in bibliography_files:
            command.append(f"--bibliography={bibliography.resolve()}")
        graphics: tuple[PreparedGraphic, ...] = ()
        pdf_graphics: tuple[PreparedGraphic, ...] = ()
        tikzcd_graphics: tuple[PreparedGraphic, ...] = ()
        missing_graphics = 0
        source_normalizations = []
        try:
            pdf_graphics = _prepare_pdf_graphics(target.source, target_dir, timeout)
            if pdf_graphics:
                command.append("--nographicimages")
            source_text = target.source.read_text(encoding="utf-8", errors="replace")
            normalized_source, tikzcd_graphics = _prepare_tikzcd_graphics(
                target.source, source_text, target_dir, timeout
            )
            graphics = pdf_graphics + tikzcd_graphics
            tikzcd_normalization_count = len(tikzcd_graphics)
            normalized_source, normalization_count = _normalize_math_inside_text(
                normalized_source
            )
            normalized_source, brace_normalization_count = (
                _normalize_cross_row_braces(normalized_source)
            )
            normalized_source, quotient_normalization_count = (
                _normalize_quotient_relation(normalized_source)
            )
            normalized_source, legacy_punctuation_normalization_count = (
                _normalize_legacy_math_punctuation(normalized_source)
            )
            normalized_source, triangle_normalization_count = (
                _normalize_bigtriangleup_symbol(normalized_source)
            )
            normalized_source, function_space_normalization_count = (
                _normalize_left_exponent_function_space(normalized_source)
            )
            normalized_source, norm_delimiter_normalization_count = (
                _normalize_norm_delimiters(normalized_source)
            )
            normalized_source, absolute_value_normalization_count = (
                _normalize_absolute_value_placeholders(normalized_source)
            )
            normalized_source, empty_domain_map_normalization_count = (
                _normalize_empty_domain_maps(normalized_source)
            )
            normalized_source, continuation_relation_normalization_count = (
                _normalize_continuation_relations(normalized_source)
            )
            normalized_source, half_open_interval_normalization_count = (
                _normalize_inverse_image_half_open_intervals(normalized_source)
            )
            normalized_source, sized_parenthesis_normalization_count = (
                _normalize_sized_parentheses(normalized_source)
            )
            normalized_source, group_action_dot_normalization_count = (
                _normalize_group_action_dots(normalized_source)
            )
            normalized_source, group_map_display_normalization_count = (
                _normalize_group_map_display(normalized_source)
            )
            normalized_source, empty_membership_normalization_count = (
                _normalize_empty_membership_before_condition(normalized_source)
            )
            normalized_source, nocite_normalization_count = _normalize_nocite_all(
                normalized_source, bibliography_files
            )
            normalized_source, compat_package_count = (
                _inject_latexml_compat_package(
                    normalized_source, bibliography_files
                )
            )
            conversion_source = target.source
            temporary_source = None
            if (
                normalization_count
                or tikzcd_normalization_count
                or brace_normalization_count
                or quotient_normalization_count
                or legacy_punctuation_normalization_count
                or triangle_normalization_count
                or function_space_normalization_count
                or norm_delimiter_normalization_count
                or absolute_value_normalization_count
                or empty_domain_map_normalization_count
                or continuation_relation_normalization_count
                or half_open_interval_normalization_count
                or sized_parenthesis_normalization_count
                or group_action_dot_normalization_count
                or group_map_display_normalization_count
                or empty_membership_normalization_count
                or nocite_normalization_count
                or compat_package_count
            ):
                temporary_source = target_dir / ".latexml-normalized.tex"
                temporary_source.write_text(normalized_source, encoding="utf-8")
                conversion_source = temporary_source
            if normalization_count:
                source_normalizations.append(
                    {
                        "kind": "math-inside-text",
                        "count": normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if tikzcd_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "tikzcd-rasterized",
                        "count": tikzcd_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if brace_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "cross-row-braces",
                        "count": brace_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if quotient_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "quotient-relation",
                        "count": quotient_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if legacy_punctuation_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "legacy-math-punctuation",
                        "count": legacy_punctuation_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if triangle_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "bigtriangleup-symbol",
                        "count": triangle_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if function_space_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "left-exponent-function-space",
                        "count": function_space_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if norm_delimiter_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "norm-delimiters",
                        "count": norm_delimiter_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if absolute_value_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "absolute-value-placeholder",
                        "count": absolute_value_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if empty_domain_map_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "empty-domain-map",
                        "count": empty_domain_map_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if continuation_relation_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "continuation-relation",
                        "count": continuation_relation_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if half_open_interval_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "inverse-image-half-open-interval",
                        "count": half_open_interval_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if sized_parenthesis_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "sized-parentheses",
                        "count": sized_parenthesis_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if group_action_dot_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "group-action-dots",
                        "count": group_action_dot_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if group_map_display_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "group-map-display",
                        "count": group_map_display_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if empty_membership_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "empty-membership-before-condition",
                        "count": empty_membership_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if nocite_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "nocite-all",
                        "count": nocite_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if compat_package_count:
                source_normalizations.append(
                    {
                        "kind": "latexml-compat-package",
                        "count": compat_package_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            command.append(str(conversion_source))
            try:
                completed = subprocess.run(
                    command,
                    cwd=target.paper_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 30,
                    check=False,
                )
            finally:
                if temporary_source is not None:
                    temporary_source.unlink(missing_ok=True)
            log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            error_count = sum(line.startswith("Error:") for line in log_text.splitlines())
            html_text = (
                destination.read_text(encoding="utf-8", errors="replace")
                if destination.is_file()
                else ""
            )
            html_text = _deduplicate_tikzcd_graphics(
                html_text, graphics, target_dir
            )
            html_text = _link_public_pdf_assets(
                html_text, target.paper, target_dir
            )
            html_text, missing_graphics = _insert_prepared_graphics(
                html_text, pdf_graphics
            )
            html_text, conversion_date_visible = _set_conversion_date(
                html_text, conversion_date_label
            )
            if destination.is_file():
                destination.write_text(html_text, encoding="utf-8")
            warning_lines, ignored_warnings = _effective_warning_lines(
                log_text, html_text, bool(bibliography_files)
            )
            warning_count = len(warning_lines)
            inline_svg_count, unsafe_svg_findings = svg_findings(html_text)
            has_error_markup = "ltx_ERROR" in html_text
            title_present = has_document_title(html_text)
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
            inline_svg_count = 0
            unsafe_svg_findings = []
            findings = []
            ignored_warnings = []
        blocking_reasons = _blocking_reasons(
            status=status,
            warning_count=warning_count,
            error_count=error_count,
            has_error_markup=has_error_markup,
            title_present=title_present,
            conversion_date_visible=conversion_date_visible,
            missing_graphics=missing_graphics,
            unsafe_svg_findings=unsafe_svg_findings,
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
                "inline_svg_count": inline_svg_count,
                "unsafe_svg_findings": unsafe_svg_findings,
                "source_normalizations": source_normalizations,
                "bibliographies": [
                    {
                        "source": str(path.relative_to(target.paper_dir)),
                        "sha256": sha256_file(path),
                    }
                    for path in bibliography_files
                ],
                "ignored_warnings": ignored_warnings,
                "privacy_findings": findings,
                "comments_removed": True,
                "automatic_checks_passed": not blocking_reasons,
                "blocking_reasons": blocking_reasons,
                "error": error,
            }
        )
        if progress is not None:
            progress(position, len(targets), results[-1])
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
