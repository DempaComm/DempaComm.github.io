"""Promote a manually reviewed LaTeXML trial to protected public files."""

from __future__ import annotations

import html
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from dempa_site.config import SITE_TITLE_TOP, SITE_URL
from dempa_site.conversion.latexml import svg_findings
from dempa_site.dates import local_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.loader import load_schema
from dempa_site.manifests.model import Paper
from dempa_site.manifests.validation import validate_manifest_data
from dempa_site.paths import safe_relative_path


ALLOWED_PUBLIC_SUFFIXES = {".html", ".css", ".png", ".jpg", ".jpeg", ".svg", ".webp"}
IGNORED_TRIAL_FILES = {"LaTeXML.cache"}
UNSAFE_HTML_PATTERNS = (
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<object\b", re.IGNORECASE),
    re.compile(r"<embed\b", re.IGNORECASE),
    re.compile(r"<form\b", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"\son[a-z]+\s*=", re.IGNORECASE),
)


@dataclass(frozen=True)
class LaTeXMLPublication:
    paper_dir: Path
    html_path: Path
    file_count: int


def _reviewed_result(report: dict, paper: Paper) -> dict:
    if report.get("schema_version") != 2 or report.get("tool") != "LaTeXML":
        raise PaperToolError("LaTeXML試験レポートの形式が不正です")
    matches = [item for item in report.get("results", []) if item.get("slug") == paper.slug]
    if len(matches) != 1:
        raise PaperToolError(f"LaTeXML試験結果が一意ではありません: {paper.slug}")
    result = matches[0]
    if not result.get("automatic_checks_passed"):
        reasons = result.get("blocking_reasons") or ["自動検査に合格していません"]
        raise PaperToolError("LaTeXML HTMLを公開できません: " + "; ".join(reasons))
    if result.get("privacy_findings"):
        raise PaperToolError("LaTeXML HTMLに未確認の個人情報候補があります")
    source_relative = safe_relative_path(result["source"], PaperToolError)
    source_path = paper.source_path.parent / source_relative
    if not source_path.is_file():
        raise PaperToolError(f"LaTeXML変換元TeXがありません: {source_relative}")
    if result.get("source_sha256") != sha256_file(source_path):
        raise PaperToolError("LaTeXML変換後に変換元TeXが変更されています")
    return result


def _public_source_href(paper: Paper, source_path: str) -> str:
    for entry in paper.files:
        if entry.public and entry.path == source_path:
            return "../" + quote(entry.path, safe="/")
    return ""


def _public_pdf_href(paper: Paper) -> str:
    preferred_roles = ("published-pdf", "built-pdf")
    for role in preferred_roles:
        for entry in paper.files:
            if (
                entry.public
                and entry.role == role
                and Path(entry.path).suffix.casefold() == ".pdf"
            ):
                return "../" + quote(entry.path, safe="/")
    return ""


def _integrate_site_html(
    source: str,
    paper: Paper,
    source_path: str,
    *,
    automatically_published: bool,
    public_directory: str,
    version_name: str,
) -> str:
    if any(pattern.search(source) for pattern in UNSAFE_HTML_PATTERNS):
        raise PaperToolError("LaTeXML HTMLに公開を許可しない動的要素があります")
    _, unsafe_svg_findings = svg_findings(source)
    if unsafe_svg_findings:
        raise PaperToolError("LaTeXML SVGに公開を許可しない要素があります")
    slug = html.escape(paper.slug, quote=True)
    title = html.escape(paper.title)
    canonical = f"{SITE_URL}/papers/{slug}/{quote(public_directory, safe='')}/"
    head_addition = (
        f'<link rel="canonical" href="{canonical}">\n'
        '<link rel="stylesheet" href="../../../styles.css" type="text/css">\n'
    )
    if "</head>" not in source:
        raise PaperToolError("LaTeXML HTMLにhead終端がありません")
    source = source.replace("</head>", head_addition + "</head>", 1)
    source = re.sub(
        r"<body(?:\s[^>]*)?>",
        '<body class="paper-html-page">',
        source,
        count=1,
        flags=re.IGNORECASE,
    )
    source = source.replace(
        '<article class="', '<article id="main-content" class="', 1
    )
    pdf_href = _public_pdf_href(paper)
    tex_href = _public_source_href(paper, source_path)
    pdf_link = f'    <a href="{pdf_href}">PDFを読む</a>\n' if pdf_href else ""
    tex_link = f'    <a href="{tex_href}">TeXソース</a>\n' if tex_href else ""
    if automatically_published:
        eyebrow = "AUTOMATIC HTML VERSION"
        description = (
            f"{title}の{html.escape(version_name)}をLaTeXMLで自動変換したものです。"
            "自動検査には合格していますが、"
            "元PDFとの目視比較は未実施です。正本はPDF・TeXです。"
        )
    else:
        eyebrow = "EXPERIMENTAL HTML VERSION"
        description = (
            f"{title}の{html.escape(version_name)}をLaTeXMLで変換したものです。"
            "正本はPDF・TeXです。"
        )
    navigation = f"""<a class="skip-link" href="#main-content">本文へ移動</a>
<header class="html-version-header">
  <p class="eyebrow">{eyebrow}</p>
  <p>{description}</p>
  <nav class="paper-actions" aria-label="HTML版の案内">
    <a class="primary-action" href="../">原稿ページへ戻る</a>
{pdf_link}{tex_link}    <a href="../../../">{html.escape(SITE_TITLE_TOP)}トップ</a>
  </nav>
</header>
"""
    if '<body class="paper-html-page">' not in source:
        raise PaperToolError("LaTeXML HTMLにbody要素がありません")
    integrated = source.replace(
        '<body class="paper-html-page">',
        '<body class="paper-html-page">\n' + navigation,
        1,
    )
    trailing_newline = "\n" if integrated.endswith("\n") else ""
    return "\n".join(line.rstrip() for line in integrated.splitlines()) + trailing_newline


def publish_latexml_trial(
    *,
    root: Path,
    paper: Paper,
    trial_output: Path,
    automatically_published: bool = False,
    public_directory: str = "html",
    label: str | None = None,
    version_name: str = "HTML版",
    alternate: bool = False,
) -> LaTeXMLPublication:
    root = root.resolve()
    paper_dir = paper.source_path.parent.resolve()
    try:
        paper_dir.relative_to(root / "papers")
    except ValueError as error:
        raise PaperToolError("HTML版の公開先がpapersフォルダ外です") from error
    trial_output = trial_output.expanduser().resolve()
    report_path = trial_output / "report.json"
    if not report_path.is_file():
        raise PaperToolError(f"LaTeXML試験レポートがありません: {report_path}")
    report = read_json(report_path)
    result = _reviewed_result(report, paper)
    source_dir = trial_output / paper.slug
    html_relative = safe_relative_path(result["html"], PaperToolError)
    trial_html = trial_output / html_relative
    if trial_html.parent != source_dir or not trial_html.is_file():
        raise PaperToolError("LaTeXML HTMLの公開元が原稿別試験フォルダにありません")
    all_files = sorted(path for path in source_dir.iterdir() if path.is_file())
    public_files = [
        path for path in all_files if path.suffix.casefold() in ALLOWED_PUBLIC_SUFFIXES
    ]
    log_relative = safe_relative_path(result["log"], PaperToolError)
    expected_log = trial_output / log_relative
    unexpected = [
        path
        for path in all_files
        if path not in public_files
        and path != expected_log
        and path.name not in IGNORED_TRIAL_FILES
    ]
    if not public_files or unexpected:
        raise PaperToolError("LaTeXML試験出力に公開対象外のファイルがあります")

    public_directory = str(safe_relative_path(public_directory, PaperToolError))
    if Path(public_directory).parent != Path("."):
        raise PaperToolError("HTML版の公開フォルダ名は一階層で指定してください")
    target_dir = paper_dir / public_directory
    if target_dir.exists():
        raise PaperToolError(f"HTML版の公開先が既にあります: {target_dir}")
    temporary = Path(tempfile.mkdtemp(prefix=".html-publication-", dir=paper_dir))
    manifest_path = paper.source_path
    try:
        for source_file in public_files:
            target = temporary / source_file.name
            if source_file.name == "index.html":
                transformed = _integrate_site_html(
                    source_file.read_text(encoding="utf-8"),
                    paper,
                    result["source"],
                    automatically_published=automatically_published,
                    public_directory=public_directory,
                    version_name=version_name,
                )
                target.write_text(transformed, encoding="utf-8")
            else:
                shutil.copy2(source_file, target)

        html_label = label or (
            "HTML版を読む（自動変換・未目視）"
            if automatically_published
            else "HTML版を読む（試験）"
        )
        files = []
        for target in sorted(temporary.iterdir()):
            relative = f"{public_directory}/{target.name}"
            files.append(
                {
                    "path": relative,
                    "role": "derived-html" if target.name == "index.html" else "derived-asset",
                    "label": html_label if target.name == "index.html" else "",
                    "public": True,
                    "original_sha256": sha256_file(target),
                    "sha256": sha256_file(target),
                }
            )

        manifest = paper.to_dict()
        manifest["files"].extend(files)
        reviewed_at = local_now_seconds().isoformat(timespec="seconds")
        version_record = {
            "status": "automatic" if automatically_published else "approved",
            "generator": "LaTeXML",
            "generator_version": report["version"],
            "generated_at": report["generated_at"],
            "source_path": result["source"],
            "source_sha256": result["source_sha256"],
            "path": f"{public_directory}/index.html",
            "label": html_label,
            "reviewed_at": reviewed_at,
        }
        versions = manifest.get("html_versions")
        if versions is None:
            versions = []
            if manifest.get("html_version") is not None:
                versions.append(manifest.pop("html_version"))
            versions.extend(manifest.pop("alternate_html_versions", []))
            manifest["html_versions"] = versions
        if alternate:
            if any(item["path"] == version_record["path"] for item in versions):
                raise PaperToolError("paper.jsonには同じ公開先の別版HTMLがあります")
            versions.append(version_record)
        else:
            if versions:
                raise PaperToolError("paper.jsonには既にHTML版の承認情報があります")
            versions.append(version_record)
        validate_manifest_data(manifest, manifest_path, load_schema(), PaperToolError)
        temporary.rename(target_dir)
        try:
            write_json(manifest_path, manifest)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    return LaTeXMLPublication(paper_dir, target_dir / "index.html", len(public_files))
