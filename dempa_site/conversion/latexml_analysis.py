"""Safety and completeness checks for generated LaTeXML HTML."""

from __future__ import annotations

import html
import re


SVG_PATTERN = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
DOCUMENT_TITLE_PATTERN = re.compile(
    r'<h1\b(?=[^>]*\bclass="[^"]*\bltx_title_document\b)[^>]*>(.*?)</h1>',
    re.IGNORECASE | re.DOTALL,
)
UNSAFE_SVG_PATTERNS = (
    ("script element", re.compile(r"<script\b", re.IGNORECASE)),
    ("event handler", re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)),
    (
        "external resource",
        re.compile(
            r"(?:href|xlink:href)\s*=\s*['\"]\s*(?:https?:|//|data:|javascript:)",
            re.IGNORECASE,
        ),
    ),
)


def blocking_reasons(
    *,
    status: str,
    warning_count: int,
    error_count: int,
    has_error_markup: bool,
    title_present: bool,
    conversion_date_visible: bool,
    missing_graphics: int,
    unsafe_svg_findings: list[str],
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
    if unsafe_svg_findings:
        reasons.append("生成SVGに公開を許可しない要素があります")
    if findings:
        reasons.append("生成HTMLの簡易個人情報検査に確認事項があります")
    return reasons


def svg_findings(html_text: str) -> tuple[int, list[str]]:
    """Count inline SVGs and report executable or externally loaded content."""
    fragments = SVG_PATTERN.findall(html_text)
    findings = []
    for index, fragment in enumerate(fragments, start=1):
        for label, pattern in UNSAFE_SVG_PATTERNS:
            if pattern.search(fragment):
                findings.append(f"inline SVG {index}: {label}")
    return len(fragments), findings


def has_document_title(html_text: str) -> bool:
    """Return whether LaTeXML emitted a non-empty document-title heading."""
    for fragment in DOCUMENT_TITLE_PATTERN.findall(html_text):
        plain_text = re.sub(r"<[^>]+>", "", fragment)
        if re.sub(r"\s+", " ", html.unescape(plain_text)).strip():
            return True
    return False


def set_conversion_date(html_text: str, label: str) -> tuple[str, bool]:
    replacement = f'<div class="ltx_dates">HTML変換日：{label}</div>'
    date_pattern = re.compile(r'<div class="ltx_dates">.*?</div>', re.DOTALL)
    if date_pattern.search(html_text):
        return date_pattern.sub(replacement, html_text, count=1), True
    body_pattern = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
    if body_pattern.search(html_text):
        return body_pattern.sub(rf"\1\n{replacement}", html_text, count=1), True
    return html_text, False


def effective_warning_lines(
    log_text: str, html_text: str, has_bibliographies: bool
) -> tuple[list[str], list[str]]:
    """Separate actionable warnings from a safe mixed-bibliography warning."""
    warnings = [
        line for line in log_text.splitlines() if line.startswith("Warning:")
    ]
    ignored = []
    if has_bibliographies and "ltx_missing_citation" not in html_text:
        for line in tuple(warnings):
            if line.startswith("Warning:expected:bibkeys "):
                warnings.remove(line)
                ignored.append(line)
    return warnings, ignored
