#!/usr/bin/env python3
"""Import, protect, catalog, and stage public LaTeX papers."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from html.parser import HTMLParser
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dempa_site.config import (  # noqa: E402
    BLOG_ONLY_KIND,
    DEFAULT_BUILD_ENGINE,
    LATEXMKRC_BY_ENGINE,
    MATH_SECTION_DETAILS,
    SITE_URL,
)
from dempa_site.dates import (  # noqa: E402
    local_now_seconds,
    parse_iso_datetime,
    utc_now_seconds,
)
from dempa_site.errors import PaperToolError  # noqa: E402
from dempa_site.files import normalize_nfc, read_json, sha256_file, write_json  # noqa: E402
from dempa_site.manifests.loader import (  # noqa: E402
    load_manifest_directory,
    load_schema,
)
from dempa_site.manifests.model import Paper  # noqa: E402
from dempa_site.manifests.validation import validate_manifest_data  # noqa: E402
from dempa_site.paths import (  # noqa: E402
    RepositoryPaths,
    safe_relative_path as shared_safe_relative_path,
)
from dempa_site.site.cards import has_pdf  # noqa: E402
from dempa_site.site.feeds import rendered_feed  # noqa: E402
from dempa_site.site.rendering import (  # noqa: E402
    grouped_math_sections,
    grouped_tags,
    rendered_archive_page,
    rendered_home_page,
    rendered_math_page,
    rendered_math_section_page,
    rendered_not_found_page,
    rendered_paper_page,
    rendered_tag_page,
)
from dempa_site.site.sitemap import rendered_sitemap  # noqa: E402


PATHS = RepositoryPaths.from_environment("PAPER_REPO_ROOT", __file__)
ROOT = PATHS.root
PAPERS_DIR = PATHS.papers
INDEX_PATH = PATHS.index
SEARCH_SCRIPT_PATH = PATHS.search_script
PRIVACY_REVIEW_DIR = Path(
    os.environ.get("PAPER_PRIVACY_REVIEW_DIR", PATHS.privacy_review)
).resolve()
PRIVACY_TEX_COMMANDS = (
    "author",
    "email",
    "affiliation",
    "institute",
    "address",
    "thanks",
)
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


sha256 = sha256_file


def safe_relative_path(value: str) -> Path:
    return shared_safe_relative_path(value, PaperToolError)


def nfc_path(value: str) -> str:
    return normalize_nfc(value)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = read_json(path)
    except (OSError, JSONDecodeError) as error:
        raise PaperToolError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise PaperToolError(f"JSON root must be an object: {path}")
    return value


def validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    validate_manifest_data(manifest, path, load_schema(), PaperToolError)


def manifests(slugs: Iterable[str] | None = None) -> list[tuple[Path, Paper]]:
    return load_manifest_directory(PAPERS_DIR, slugs, PaperToolError)


def verify_one(manifest_path: Path, manifest: Paper) -> list[str]:
    errors: list[str] = []
    paper_dir = manifest_path.parent
    for entry in manifest.files:
        relative = safe_relative_path(entry.path)
        target = paper_dir / relative
        if not target.is_file():
            errors.append(f"{manifest.slug}/{relative}: missing")
            continue
        actual = sha256(target)
        if actual != entry.sha256:
            errors.append(
                f"{manifest.slug}/{relative}: SHA-256 mismatch "
                f"(expected {entry.sha256}, got {actual})"
            )
    return errors


def command_verify(args: argparse.Namespace) -> None:
    errors: list[str] = []
    selected = manifests(args.slugs)
    for manifest_path, manifest in selected:
        paper_errors = verify_one(manifest_path, manifest)
        errors.extend(paper_errors)
        if not paper_errors:
            print(f"OK  {manifest.slug}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"verification failed with {len(errors)} error(s)")


def command_audit(args: argparse.Namespace) -> None:
    selected = manifests(args.slugs)
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(verify_one(manifest_path, manifest))
        for entry in manifest.files:
            state = (
                "original"
                if entry.sha256 == entry.original_sha256
                else "approved-modified"
            )
            print(f"{state:17} {manifest.slug}/{entry.path}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"audit failed with {len(errors)} error(s)")


def rendered_index() -> str:
    return rendered_home_page(manifests())


def command_catalog(args: argparse.Namespace) -> None:
    rendered = rendered_index()
    current = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        stale_keywords: list[str] = []
        for manifest_path, manifest in manifests():
            target = manifest_path.parent / "keywords.txt"
            if not target.is_file() or target.read_text(encoding="utf-8") != rendered_keywords(manifest):
                stale_keywords.append(manifest["slug"])
        if rendered != current:
            raise PaperToolError("index.html is not synchronized with paper.json files")
        if stale_keywords:
            raise PaperToolError(
                "keywords.txt is not synchronized for: " + ", ".join(stale_keywords)
            )
        print("OK  index.html catalog")
        return
    INDEX_PATH.write_text(rendered, encoding="utf-8")
    for manifest_path, manifest in manifests():
        (manifest_path.parent / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
    print("WROTE index.html and keywords.txt files")


def command_build_roots(args: argparse.Namespace) -> None:
    """List only TeX roots whose manifests explicitly enable compilation."""
    for manifest_path, manifest in manifests():
        if not manifest.build.enabled:
            continue
        root = safe_relative_path(str(manifest.build.root))
        print((manifest_path.parent / root).relative_to(ROOT))


def rendered_keywords(manifest: Paper) -> str:
    lines = [
        "# タイトル",
        manifest["title"],
        "",
        "# 電波通信のタグ",
        *manifest["tags"],
        "",
        "# 検索キーワード",
        *manifest["keywords"],
        "",
    ]
    return "\n".join(lines)


class LocalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)
        attribute = "href" if tag in {"a", "link"} else "src" if tag == "script" else ""
        if not attribute:
            return
        for key, value in attrs:
            if key == attribute and value:
                self.links.append(value)


def local_link_errors(site_root: Path) -> list[str]:
    errors: list[str] = []
    page_ids: dict[Path, set[str]] = {}
    for page in sorted(site_root.rglob("*.html")):
        parser = LocalLinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        page_ids[page.resolve()] = parser.ids
        for raw_link in parser.links:
            parsed = urlsplit(raw_link)
            if parsed.scheme or parsed.netloc or raw_link.startswith(("mailto:", "tel:")):
                continue
            decoded_path = unquote(parsed.path)
            if not decoded_path:
                target = page
            elif decoded_path.startswith("/"):
                target = site_root / decoded_path.lstrip("/")
            else:
                target = page.parent / decoded_path
            if decoded_path.endswith("/"):
                target /= "index.html"
            target = target.resolve()
            try:
                target.relative_to(site_root.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(site_root)}: unsafe link {raw_link}")
                continue
            if not target.is_file():
                errors.append(
                    f"{page.relative_to(site_root)}: missing target {raw_link}"
                )
                continue
            if parsed.fragment and target.suffix.casefold() == ".html":
                target_ids = page_ids.get(target)
                if target_ids is None:
                    target_parser = LocalLinkParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                    target_ids = target_parser.ids
                    page_ids[target] = target_ids
                fragment = unquote(parsed.fragment)
                if fragment not in target_ids:
                    errors.append(
                        f"{page.relative_to(site_root)}: missing fragment {raw_link}"
                    )
    return errors


def command_check_links(args: argparse.Namespace) -> None:
    site_root = Path(args.site).resolve()
    if not site_root.is_dir():
        raise PaperToolError(f"site directory does not exist: {site_root}")
    errors = local_link_errors(site_root)
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"link check failed with {len(errors)} error(s)")
    print(f"OK  links in {site_root}")


def command_stage(args: argparse.Namespace) -> None:
    selected = manifests()
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(verify_one(manifest_path, manifest))
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError("refusing to stage files that failed verification")
    if rendered_index() != INDEX_PATH.read_text(encoding="utf-8"):
        raise PaperToolError("refusing to stage a stale index.html")
    for manifest_path, manifest in selected:
        keyword_path = manifest_path.parent / "keywords.txt"
        if (
            not keyword_path.is_file()
            or keyword_path.read_text(encoding="utf-8") != rendered_keywords(manifest)
        ):
            raise PaperToolError(
                f"refusing to stage stale keywords.txt for {manifest['slug']}"
            )

    output = Path(args.output).resolve()
    if output == ROOT or output in ROOT.parents:
        raise PaperToolError("stage output must not be the repository or one of its parents")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copy2(INDEX_PATH, output / "index.html")
    shutil.copy2(ROOT / "styles.css", output / "styles.css")
    shutil.copy2(SEARCH_SCRIPT_PATH, output / "search.js")
    for asset in (
        "favicon.ico",
        "favicon-16.png",
        "favicon-32.png",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "og-image.png",
        "site.webmanifest",
    ):
        shutil.copy2(ROOT / asset, output / asset)
    archive_dir = output / "archive"
    archive_dir.mkdir()
    (archive_dir / "index.html").write_text(
        rendered_archive_page(selected), encoding="utf-8"
    )
    (output / "404.html").write_text(
        rendered_not_found_page(), encoding="utf-8"
    )
    (output / "feed.xml").write_text(
        rendered_feed(selected), encoding="utf-8"
    )
    (output / "sitemap.xml").write_text(
        rendered_sitemap(selected), encoding="utf-8"
    )
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )

    for manifest_path, manifest in selected:
        source_dir = manifest_path.parent
        target_dir = output / "papers" / manifest["slug"]
        target_dir.mkdir(parents=True)
        shutil.copy2(manifest_path, target_dir / "paper.json")
        shutil.copy2(source_dir / "keywords.txt", target_dir / "keywords.txt")
        readme = source_dir / "README.md"
        if readme.is_file():
            shutil.copy2(readme, target_dir / "README.md")
        for entry in manifest["files"]:
            if not entry["public"]:
                continue
            relative = safe_relative_path(entry["path"])
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / relative, target)
        if manifest["build"]["enabled"]:
            pdf = source_dir / "main.pdf"
            if not pdf.is_file():
                raise PaperToolError(f"generated PDF is missing: {pdf}")
            shutil.copy2(pdf, target_dir / "main.pdf")
        elif has_pdf(manifest):
            shutil.copy2(source_dir / "published.pdf", target_dir / "main.pdf")
        (target_dir / "index.html").write_text(
            rendered_paper_page(manifest), encoding="utf-8"
        )
        for legacy_slug in manifest["legacy_slugs"]:
            legacy_dir = output / "papers" / legacy_slug
            if legacy_dir.exists():
                raise PaperToolError(f"legacy slug collision: {legacy_slug}")
            shutil.copytree(target_dir, legacy_dir)

    for tag, papers in grouped_tags(selected).items():
        if tag in {".", ".."} or "/" in tag or "\0" in tag:
            raise PaperToolError(f"tag cannot be used as a page path: {tag!r}")
        tag_dir = output / "tags" / tag
        tag_dir.mkdir(parents=True)
        (tag_dir / "index.html").write_text(
            rendered_tag_page(tag, papers), encoding="utf-8"
        )
    math_dir = output / "math"
    math_dir.mkdir()
    (math_dir / "index.html").write_text(
        rendered_math_page(selected), encoding="utf-8"
    )
    for section, papers in grouped_math_sections(selected).items():
        section_dir = math_dir / str(MATH_SECTION_DETAILS[section]["slug"])
        section_dir.mkdir()
        (section_dir / "index.html").write_text(
            rendered_math_section_page(section, papers), encoding="utf-8"
        )
    link_errors = local_link_errors(output)
    if link_errors:
        for error in link_errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(
            f"refusing to publish a site with {len(link_errors)} broken link(s)"
        )
    print(f"STAGED {len(selected)} papers in {output}")


def resolve_source_dir(spec_path: Path, spec: dict[str, Any]) -> Path:
    raw_value = spec.get("source_dir")
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise PaperToolError("spec.source_dir is required")
    raw = Path(raw_value)
    return (raw if raw.is_absolute() else spec_path.parent / raw).resolve()


def extracted_tex_title(source: str) -> str:
    """Extract a conservative plain-text title from a TeX title command."""
    match = re.search(r"\\title\s*\{", source)
    if not match:
        return ""
    start = match.end()
    depth = 1
    escaped = False
    end = start
    for end in range(start, len(source)):
        character = source[end]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                break
    if depth != 0:
        return ""
    title = source[start:end]
    previous = None
    while title != previous:
        previous = title
        title = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", title)
    title = re.sub(r"\\[A-Za-z@]+\*?", "", title)
    title = title.replace("~", " ").replace("{", "").replace("}", "")
    return " ".join(title.split()).strip()


def next_sequence_for_date(published: datetime) -> int:
    used: list[int] = []
    for manifest_path in sorted(PAPERS_DIR.glob("*/paper.json")):
        manifest = load_json(manifest_path)
        validate_manifest(manifest, manifest_path)
        if str(manifest["published_at"])[:10] == f"{published:%Y-%m-%d}":
            used.append(int(manifest["sequence"]))
    return max(used, default=0) + 1


def privacy_review_path(source: Path) -> Path:
    return PRIVACY_REVIEW_DIR / sha256(source)


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
            r"^(Author|Creator|Subject|Keywords):\s*(.+)$", re.MULTILINE | re.IGNORECASE
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


def command_inspect_file(args: argparse.Namespace) -> None:
    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"file does not exist: {source}")
    suffix = source.suffix.casefold()
    if suffix not in {".tex", ".pdf"}:
        raise PaperToolError("inspect-file supports only .tex and .pdf files")
    output = privacy_review_path(source)
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
                "sha256": sha256(source),
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
        "sha256": sha256(source),
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
    (output / "report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"PRIVACY REVIEW FILES: {output}")
    for finding in findings:
        print(f"WARN {finding}")
    print("MANUAL REVIEW REQUIRED before using --privacy-reviewed")


def require_privacy_review(
    source: Path, acknowledged: bool, override_reason: str | None
) -> dict[str, Any]:
    review_dir = privacy_review_path(source)
    report_path = review_dir / "report.json"
    if not report_path.is_file():
        raise PaperToolError(
            f"run inspect-file first: python3 scripts/paper_tool.py inspect-file {source}"
        )
    report = load_json(report_path)
    if report.get("sha256") != sha256(source):
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
            "--privacy-override \"reason\""
        )
    if expected_type == "pdf":
        pages = report.get("rendered_pages")
        if (
            not isinstance(pages, list)
            or not pages
            or any(
                not isinstance(page, str)
                or not (review_dir / safe_relative_path(page)).is_file()
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


def privacy_review_for_path(review: dict[str, Any], target: Path) -> dict[str, Any]:
    return {"path": str(target), **review}


def command_import_tex(args: argparse.Namespace) -> None:
    """Create a guaranteed-publishable source-only paper from one TeX file."""
    source = Path(args.tex_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"TeX file does not exist: {source}")
    if source.suffix.casefold() != ".tex":
        raise PaperToolError(f"expected a .tex file: {source}")
    privacy_review = require_privacy_review(
        source, args.privacy_reviewed, args.privacy_override
    )
    try:
        source_text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise PaperToolError(f"cannot read TeX file: {source}: {error}") from error

    if args.published_at:
        try:
            published = parse_iso_datetime(args.published_at)
        except ValueError as error:
            raise PaperToolError("--published-at must be ISO 8601") from error
        published_at = args.published_at
    else:
        published = local_now_seconds()
        published_at = published.isoformat()
    sequence = args.sequence or next_sequence_for_date(published)
    if sequence < 1:
        raise PaperToolError("--sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    title = (args.title or extracted_tex_title(source_text) or source.stem).strip()
    if not title:
        title = "無題のTeX原稿"
    target_name = "source.tex"
    try:
        destination.mkdir(parents=True)
        target = destination / target_name
        shutil.copy2(source, target)
        source_hash = sha256(source)
        if sha256(target) != source_hash:
            raise PaperToolError(f"copy verification failed: {source}")
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "legacy_slugs": [],
            "title": title,
            "published_at": published_at,
            "sequence": sequence,
            "year": published.year,
            "kind": "TeX原稿",
            "math_section": "",
            "summary": "TeX原稿を公開しています。",
            "original_url": args.original_url or "",
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": ["数学"],
            "keywords": [title],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": target_name,
                    "role": "manuscript",
                    "label": "TeXソース",
                    "public": True,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [privacy_review_for_path(privacy_review, Path(target_name))],
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, Paper.from_dict(manifest, manifest_path))
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(f"IMPORTED {slug} as a source-only paper with byte-identical TeX")


def command_import_pdf(args: argparse.Namespace) -> None:
    """Create a publishable paper from one byte-protected PDF file."""
    source = Path(args.pdf_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"PDF file does not exist: {source}")
    if source.suffix.casefold() != ".pdf":
        raise PaperToolError(f"expected a .pdf file: {source}")
    privacy_review = require_privacy_review(
        source, args.privacy_reviewed, args.privacy_override
    )
    try:
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PaperToolError(f"file does not have a PDF header: {source}")
    except OSError as error:
        raise PaperToolError(f"cannot read PDF file: {source}: {error}") from error

    if args.published_at:
        try:
            published = parse_iso_datetime(args.published_at)
        except ValueError as error:
            raise PaperToolError("--published-at must be ISO 8601") from error
        published_at = args.published_at
    else:
        published = local_now_seconds()
        published_at = published.isoformat()
    sequence = args.sequence or next_sequence_for_date(published)
    if sequence < 1:
        raise PaperToolError("--sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    title = (args.title or source.stem).strip() or "無題のPDF原稿"
    target_name = "published.pdf"
    try:
        destination.mkdir(parents=True)
        target = destination / target_name
        shutil.copy2(source, target)
        source_hash = sha256(source)
        if sha256(target) != source_hash:
            raise PaperToolError(f"copy verification failed: {source}")
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "legacy_slugs": [],
            "title": title,
            "published_at": published_at,
            "sequence": sequence,
            "year": published.year,
            "kind": "PDF原稿",
            "math_section": "",
            "summary": "PDF原稿を公開しています。",
            "original_url": args.original_url or "",
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": ["数学"],
            "keywords": [title],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": target_name,
                    "role": "published-pdf",
                    "label": "",
                    "public": True,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [privacy_review_for_path(privacy_review, Path(target_name))],
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, Paper.from_dict(manifest, manifest_path))
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(f"IMPORTED {slug} with a byte-identical published PDF")


def command_import(args: argparse.Namespace) -> None:
    spec_path = Path(args.spec).resolve()
    spec = load_json(spec_path)
    required = (
        "title",
        "kind",
        "summary",
        "original_url",
        "published_at",
        "sequence",
        "tags",
        "keywords",
        "files",
    )
    missing = [key for key in required if key not in spec]
    if missing:
        raise PaperToolError(f"import spec missing fields: {', '.join(missing)}")
    try:
        published = parse_iso_datetime(spec["published_at"])
    except ValueError as error:
        raise PaperToolError("spec.published_at must be ISO 8601") from error
    sequence = int(spec["sequence"])
    if sequence < 1:
        raise PaperToolError("spec.sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    files = spec["files"]
    if not isinstance(files, list):
        raise PaperToolError("spec.files must be an array")
    blog_only = spec["kind"] == BLOG_ONLY_KIND
    if not files and not blog_only:
        raise PaperToolError(f"spec.files may be empty only for kind={BLOG_ONLY_KIND}")
    source_dir = resolve_source_dir(spec_path, spec) if files else spec_path.parent
    if files and not source_dir.is_dir():
        raise PaperToolError(f"source_dir does not exist: {source_dir}")
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    reviewed_flag = bool(args.privacy_reviewed or spec.get("privacy_reviewed", False))
    override_value = (
        args.privacy_override
        if args.privacy_override is not None
        else spec.get("privacy_override")
    )
    if override_value is not None and not isinstance(override_value, str):
        raise PaperToolError("privacy_override must be a string")
    prepared_files: list[tuple[dict[str, Any], Path, Path]] = []
    privacy_reviews: list[dict[str, Any]] = []
    if blog_only:
        print(f"BLOG ARTICLE LINK TO IMPORT: {spec['original_url']}")
    else:
        print("PUBLIC FILES TO IMPORT:")
    for entry in files:
        source_relative = safe_relative_path(str(entry["source"]))
        target_relative = safe_relative_path(nfc_path(str(entry["path"])))
        source = (source_dir / source_relative).resolve()
        try:
            source.relative_to(source_dir)
        except ValueError as error:
            raise PaperToolError(f"source escapes source_dir: {source}") from error
        if not source.is_file():
            raise PaperToolError(f"source file does not exist: {source}")
        is_public = bool(entry.get("public", True))
        if is_public:
            print(f"- {target_relative} ({entry.get('role', 'file')})")
        if is_public and target_relative.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(source, reviewed_flag, override_value)
            privacy_reviews.append(privacy_review_for_path(review, target_relative))
        prepared_files.append((entry, source, target_relative))

    manifest_files: list[dict[str, Any]] = []
    try:
        destination.mkdir(parents=True)
        for entry, source, target_relative in prepared_files:
            target = destination / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            source_hash = sha256(source)
            if sha256(target) != source_hash:
                raise PaperToolError(f"copy verification failed: {source}")
            manifest_files.append(
                {
                    "path": str(target_relative),
                    "role": str(entry["role"]),
                    "label": str(entry.get("label", "")),
                    "public": bool(entry.get("public", True)),
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            )
        build_enabled = bool(spec.get("build_enabled", not blog_only))
        build_engine = str(spec.get("build_engine", "")).strip()
        if build_engine and build_engine not in LATEXMKRC_BY_ENGINE:
            raise PaperToolError(
                "build_engine must be one of: "
                + ", ".join(sorted(LATEXMKRC_BY_ENGINE))
            )
        effective_engine = build_engine or DEFAULT_BUILD_ENGINE
        latexmkrc = destination / ".latexmkrc"
        if build_enabled and not latexmkrc.exists():
            latexmkrc.write_text(
                LATEXMKRC_BY_ENGINE[effective_engine], encoding="utf-8"
            )
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "migration_record_id": str(spec.get("migration_record_id", "")).strip(),
            "legacy_slugs": list(spec.get("legacy_slugs", [])),
            "title": spec["title"],
            "published_at": spec["published_at"],
            "sequence": sequence,
            "year": published.year,
            "kind": spec["kind"],
            "math_section": str(spec.get("math_section", "")).strip(),
            "summary": spec["summary"],
            "original_url": spec["original_url"],
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": list(spec["tags"]),
            "keywords": list(spec["keywords"]),
            "build": (
                {
                    "enabled": True,
                    "root": nfc_path(str(spec.get("build_root", "main.tex"))),
                    "engine": build_engine,
                }
                if build_enabled
                else {"enabled": False, "engine": build_engine}
            ),
            "files": manifest_files,
            "approved_changes": [],
            "privacy_reviews": privacy_reviews,
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, Paper.from_dict(manifest, manifest_path))
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    if blog_only:
        print(f"IMPORTED {slug} as {BLOG_ONLY_KIND}")
    else:
        print(f"IMPORTED {slug} with byte-identical protected files")


def command_approve(args: argparse.Namespace) -> None:
    reason = args.reason.strip()
    if not reason:
        raise PaperToolError("approval reason must not be empty")
    selected = manifests([args.slug])
    manifest_path, typed_manifest = selected[0]
    manifest = typed_manifest.to_dict()
    requested = list(dict.fromkeys(args.files))
    requested_set = set(requested)
    entries = {entry["path"]: entry for entry in manifest["files"]}
    unknown = [path for path in requested if path not in entries]
    if unknown:
        raise PaperToolError(f"files are not protected by paper.json: {', '.join(unknown)}")
    for entry in manifest["files"]:
        if entry["path"] in requested_set:
            continue
        target = manifest_path.parent / safe_relative_path(entry["path"])
        if not target.is_file() or sha256(target) != entry["sha256"]:
            raise PaperToolError(
                f"unapproved change exists outside requested files: {entry['path']}"
            )
    changes: list[dict[str, str]] = []
    privacy_updates: dict[str, dict[str, Any]] = {}
    for value in requested:
        relative = safe_relative_path(value)
        target = manifest_path.parent / relative
        if not target.is_file():
            raise PaperToolError(f"cannot approve missing file: {target}")
        old_hash = entries[value]["sha256"]
        new_hash = sha256(target)
        if old_hash == new_hash:
            continue
        entry = entries[value]
        if entry["public"] and target.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(
                target, args.privacy_reviewed, args.privacy_override
            )
            privacy_updates[value] = privacy_review_for_path(review, relative)
        entries[value]["sha256"] = new_hash
        changes.append({"path": value, "from_sha256": old_hash, "to_sha256": new_hash})
    if not changes:
        raise PaperToolError("no hash changes to approve")
    manifest["approved_changes"].append(
        {
            "approved_at": utc_now_seconds().isoformat(),
            "reason": reason,
            "files": changes,
        }
    )
    if privacy_updates:
        existing_reviews = {
            str(review["path"]): review
            for review in manifest.get("privacy_reviews", [])
        }
        existing_reviews.update(privacy_updates)
        manifest["privacy_reviews"] = list(existing_reviews.values())
    validate_manifest(manifest, manifest_path)
    write_json(manifest_path, manifest)
    print(f"APPROVED {len(changes)} explicitly requested change(s) for {args.slug}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Manage byte-protected LaTeX papers and the generated catalog."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="verify current approved hashes")
    verify_parser.add_argument("slugs", nargs="*")
    verify_parser.set_defaults(func=command_verify)

    audit_parser = subparsers.add_parser(
        "audit", help="show original versus explicitly approved file state"
    )
    audit_parser.add_argument("slugs", nargs="*")
    audit_parser.set_defaults(func=command_audit)

    catalog_parser = subparsers.add_parser("catalog", help="generate index.html cards")
    catalog_parser.add_argument("--check", action="store_true")
    catalog_parser.set_defaults(func=command_catalog)

    build_roots_parser = subparsers.add_parser(
        "build-roots", help="list manifest-approved TeX roots for CI compilation"
    )
    build_roots_parser.set_defaults(func=command_build_roots)

    stage_parser = subparsers.add_parser("stage", help="prepare the GitHub Pages directory")
    stage_parser.add_argument("output")
    stage_parser.set_defaults(func=command_stage)

    links_parser = subparsers.add_parser(
        "check-links", help="check local links in a staged site"
    )
    links_parser.add_argument("site")
    links_parser.set_defaults(func=command_check_links)

    inspect_parser = subparsers.add_parser(
        "inspect-file", help="prepare a mandatory privacy review for a TeX or PDF file"
    )
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=command_inspect_file)

    import_parser = subparsers.add_parser(
        "import-paper", help="copy a new paper byte-for-byte from a JSON spec"
    )
    import_parser.add_argument("spec")
    import_parser.add_argument("--privacy-reviewed", action="store_true")
    import_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_parser.add_argument("--no-catalog", action="store_true")
    import_parser.set_defaults(func=command_import)

    import_tex_parser = subparsers.add_parser(
        "import-tex", help="create a source-only paper from one TeX file"
    )
    import_tex_parser.add_argument("tex_file")
    import_tex_parser.add_argument("--title")
    import_tex_parser.add_argument("--published-at")
    import_tex_parser.add_argument("--sequence", type=int)
    import_tex_parser.add_argument("--original-url")
    import_tex_parser.add_argument("--privacy-reviewed", action="store_true")
    import_tex_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_tex_parser.add_argument("--no-catalog", action="store_true")
    import_tex_parser.set_defaults(func=command_import_tex)

    import_pdf_parser = subparsers.add_parser(
        "import-pdf", help="create a paper from one published PDF file"
    )
    import_pdf_parser.add_argument("pdf_file")
    import_pdf_parser.add_argument("--title")
    import_pdf_parser.add_argument("--published-at")
    import_pdf_parser.add_argument("--sequence", type=int)
    import_pdf_parser.add_argument("--original-url")
    import_pdf_parser.add_argument("--privacy-reviewed", action="store_true")
    import_pdf_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_pdf_parser.add_argument("--no-catalog", action="store_true")
    import_pdf_parser.set_defaults(func=command_import_pdf)

    approve_parser = subparsers.add_parser(
        "approve-change", help="record an explicitly requested source-file change"
    )
    approve_parser.add_argument("slug")
    approve_parser.add_argument("--reason", required=True)
    approve_parser.add_argument("--file", dest="files", action="append", required=True)
    approve_privacy = approve_parser.add_mutually_exclusive_group()
    approve_privacy.add_argument("--privacy-reviewed", action="store_true")
    approve_privacy.add_argument(
        "--privacy-override", metavar="REASON", help="approve after an alternate review"
    )
    approve_parser.set_defaults(func=command_approve)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except PaperToolError as error:
        print(f"paper-tool: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
