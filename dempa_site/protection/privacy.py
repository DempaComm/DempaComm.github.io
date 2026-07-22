"""Create and require manual privacy-review receipts for public TeX and PDF."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from dempa_site.dates import utc_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.paths import safe_relative_path


PRIVACY_TEX_COMMANDS = (
    "author",
    "email",
    "affiliation",
    "institute",
    "address",
    "thanks",
)
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass(frozen=True)
class PrivacyInspection:
    output: Path
    findings: tuple[str, ...]


def review_path(review_root: Path, source: Path) -> Path:
    return review_root / sha256_file(source)


def privacy_findings(text: str, file_type: str) -> list[str]:
    findings: list[str] = []
    for email in sorted(set(EMAIL_PATTERN.findall(text))):
        findings.append(f"email candidate: {email}")
    if file_type == "tex":
        for command in PRIVACY_TEX_COMMANDS:
            pattern = re.compile(rf"\\{command}\s*\{{([^{{}}]*)\}}", re.IGNORECASE)
            for value in pattern.findall(text):
                compact = " ".join(value.split())
                findings.append(f"\\{command} candidate: {compact or '(empty)'}")
    else:
        metadata_pattern = re.compile(
            r"^(Author|Creator|Subject|Keywords):\s*(.+)$",
            re.MULTILINE | re.IGNORECASE,
        )
        for key, value in metadata_pattern.findall(text):
            findings.append(f"PDF metadata {key}: {' '.join(value.split())}")
    for label in ("氏名", "著者", "所属", "住所", "電話", "連絡先"):
        if label in text:
            findings.append(f"personal-information label found: {label}")
    return list(dict.fromkeys(findings))


def optional_pdf_text(source: Path) -> tuple[str, list[str]]:
    notes: list[str] = []
    collected: list[str] = []
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        completed = subprocess.run(
            [pdfinfo, str(source)],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if completed.returncode == 0:
            collected.append(completed.stdout)
        else:
            notes.append("pdfinfo could not read metadata")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        completed = subprocess.run(
            [pdftotext, str(source), "-"],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if completed.returncode == 0:
            collected.append(completed.stdout)
            return "\n".join(collected), notes
        notes.append("pdftotext could not extract text")
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(source)
        metadata = reader.metadata or {}
        metadata_text = "\n".join(
            f"{key}: {value}" for key, value in metadata.items() if value
        )
        page_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        collected.extend([metadata_text, page_text])
        return "\n".join(collected), notes
    except Exception:
        if not collected:
            notes.append("PDF text and metadata extraction were unavailable")
        else:
            notes.append("PDF page text extraction was unavailable")
        return "\n".join(collected), notes


def render_pdf_review(source: Path, output: Path) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise PaperToolError(
            "PDF privacy review requires pdftoppm (Poppler) to render every page"
        )
    prefix = output / "page"
    completed = subprocess.run(
        [pdftoppm, "-png", "-r", "120", str(source), str(prefix)],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    pages = sorted(output.glob("page-*.png"))
    unsafe_render_messages = (
        "missing language pack",
        "unknown font",
        "no font in show",
        "couldn't find a font",
        "fontconfig error",
    )
    render_log = f"{completed.stdout}\n{completed.stderr}".casefold()
    if any(message in render_log for message in unsafe_render_messages):
        raise PaperToolError(
            "PDF rendering reported missing fonts; generated images may omit personal "
            "information, so privacy review cannot be approved"
        )
    if completed.returncode != 0 or not pages:
        raise PaperToolError(
            "PDF page rendering failed; the file must be reviewed visually before import"
        )
    return pages


def inspect_file(source: Path, review_root: Path) -> PrivacyInspection:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"file does not exist: {source}")
    suffix = source.suffix.casefold()
    if suffix not in {".tex", ".pdf"}:
        raise PaperToolError("inspect-file supports only .tex and .pdf files")
    output = review_path(review_root, source)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    notes: list[str] = []
    rendered_pages: list[Path] = []
    if suffix == ".tex":
        text = source.read_text(encoding="utf-8", errors="replace")
        file_type = "tex"
    else:
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PaperToolError(f"file does not have a PDF header: {source}")
        file_type = "pdf"
        text, notes = optional_pdf_text(source)
        try:
            rendered_pages = render_pdf_review(source, output)
        except PaperToolError as error:
            failure_report = {
                "schema_version": 1,
                "sha256": sha256_file(source),
                "source_name": source.name,
                "file_type": file_type,
                "findings": privacy_findings(text, file_type),
                "notes": notes,
                "rendered_pages": [],
                "manual_review_required": True,
                "inspection_status": "failed",
                "inspection_error": str(error),
            }
            write_json(output / "report.json", failure_report)
            (output / "extracted.txt").write_text(text, encoding="utf-8")
            (output / "report.txt").write_text(
                f"File: {source}\nSHA-256: {failure_report['sha256']}\n"
                f"Inspection failed: {error}\n"
                "Import is blocked unless --privacy-override with a reason is used.\n",
                encoding="utf-8",
            )
            raise
        (output / "extracted.txt").write_text(text, encoding="utf-8")
    findings = privacy_findings(text, file_type)
    report = {
        "schema_version": 1,
        "sha256": sha256_file(source),
        "source_name": source.name,
        "file_type": file_type,
        "findings": findings,
        "notes": notes,
        "rendered_pages": [page.name for page in rendered_pages],
        "manual_review_required": True,
        "inspection_status": "completed",
    }
    write_json(output / "report.json", report)
    report_lines = [
        f"File: {source}",
        f"SHA-256: {report['sha256']}",
        f"Type: {file_type}",
        "",
        "Automatic findings:",
        *(f"- {finding}" for finding in findings),
    ]
    if not findings:
        report_lines.append("- none detected (this does not prove the file is safe)")
    report_lines.extend(f"- note: {note}" for note in notes)
    report_lines.extend(
        [
            "",
            "Manual review is mandatory.",
            "For PDF, inspect every page PNG in this directory.",
            "Check author names, real names, email, affiliation, address, and metadata.",
        ]
    )
    (output / "report.txt").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    return PrivacyInspection(output, tuple(findings))


def _load_report(path: Path) -> dict[str, Any]:
    try:
        report = read_json(path)
    except (OSError, JSONDecodeError) as error:
        raise PaperToolError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(report, dict):
        raise PaperToolError(f"JSON root must be an object: {path}")
    return report


def require_privacy_review(
    source: Path,
    review_root: Path,
    acknowledged: bool,
    override_reason: str | None,
) -> dict[str, Any]:
    review_dir = review_path(review_root, source)
    report_path = review_dir / "report.json"
    if not report_path.is_file():
        raise PaperToolError(
            f"run inspect-file first: python3 scripts/paper_tool.py inspect-file {source}"
        )
    report = _load_report(report_path)
    if report.get("sha256") != sha256_file(source):
        raise PaperToolError("privacy review is stale; run inspect-file again")
    expected_type = source.suffix.casefold().removeprefix(".")
    if (
        report.get("schema_version") != 1
        or report.get("file_type") != expected_type
        or report.get("manual_review_required") is not True
    ):
        raise PaperToolError("privacy review report is invalid; run inspect-file again")
    reason = (override_reason or "").strip()
    if override_reason is not None and not reason:
        raise PaperToolError("--privacy-override requires a non-empty reason")
    if acknowledged and override_reason is not None:
        raise PaperToolError(
            "use either --privacy-reviewed or --privacy-override, not both"
        )
    if reason:
        return {
            "status": "overridden",
            "reason": reason,
            "source_sha256": report["sha256"],
            "inspection_status": str(report.get("inspection_status", "unknown")),
            "recorded_at": utc_now_seconds().isoformat(),
        }
    if report.get("inspection_status") != "completed":
        raise PaperToolError(
            "privacy inspection failed; rerun in a working environment or use "
            '--privacy-override "reason"'
        )
    if expected_type == "pdf":
        pages = report.get("rendered_pages")
        if (
            not isinstance(pages, list)
            or not pages
            or any(
                not isinstance(page, str)
                or not (
                    review_dir / safe_relative_path(page, PaperToolError)
                ).is_file()
                for page in pages
            )
        ):
            raise PaperToolError(
                "PDF privacy review images are missing; run inspect-file again"
            )
    if not acknowledged:
        raise PaperToolError(
            "manual privacy review is required; after reviewing the report and every "
            "PDF page, rerun with --privacy-reviewed"
        )
    return {
        "status": "reviewed",
        "reason": "",
        "source_sha256": report["sha256"],
        "inspection_status": "completed",
        "recorded_at": utc_now_seconds().isoformat(),
    }


def privacy_review_for_path(
    review: dict[str, Any], target: Path
) -> dict[str, Any]:
    return {"path": str(target), **review}
