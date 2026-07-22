"""Structural and semantic validation for paper manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Type

from dempa_site.config import (
    BLOG_ONLY_KIND,
    LATEXMKRC_BY_ENGINE,
    LEGACY_PRIVACY_EXEMPT_SLUGS,
    MATH_SECTIONS,
)
from dempa_site.dates import parse_iso_datetime
from dempa_site.errors import DempaSiteError
from dempa_site.files import normalize_nfc
from dempa_site.paths import safe_relative_path

from .model import Paper
from .schema import validate_json_schema


def _error(error_type: Type[DempaSiteError], path: Path, message: str) -> None:
    raise error_type(f"{path}: {message}")


def validate_manifest_data(
    manifest: Mapping[str, Any],
    path: Path,
    schema: Mapping[str, Any],
    error_type: Type[DempaSiteError],
) -> None:
    validate_json_schema(manifest, schema, path, error_type)

    if (
        manifest["schema_version"] == 1
        and manifest["slug"] not in LEGACY_PRIVACY_EXEMPT_SLUGS
    ):
        _error(
            error_type,
            path,
            "schema 1 privacy exemption is limited to migrated legacy papers",
        )
    if path.parent.name != manifest["slug"]:
        _error(error_type, path, "slug does not match directory name")

    try:
        published = parse_iso_datetime(manifest["published_at"])
    except ValueError as error:
        raise error_type(f"{path}: published_at must be ISO 8601") from error
    sequence = manifest["sequence"]
    expected_slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    if manifest["slug"] != expected_slug:
        _error(
            error_type,
            path,
            f"slug must match published date and sequence ({expected_slug})",
        )
    if manifest["year"] != published.year:
        _error(error_type, path, f"year must match published date ({published.year})")
    expected_order = int(f"{published:%Y%m%d}{sequence:02d}")
    if manifest["order"] != expected_order:
        _error(
            error_type,
            path,
            f"order must match published date and sequence ({expected_order})",
        )

    math_section = manifest.get("math_section", "")
    if math_section.strip() and math_section.strip() not in MATH_SECTIONS:
        _error(
            error_type,
            path,
            f"math_section must be one of: {', '.join(MATH_SECTIONS)}",
        )
    for field in ("legacy_slugs", "tags", "keywords"):
        values = manifest[field]
        if len(values) != len(set(values)):
            _error(error_type, path, f"{field} contains duplicates")
    for legacy_slug in manifest["legacy_slugs"]:
        relative = safe_relative_path(legacy_slug, error_type)
        if str(relative) != legacy_slug or "/" in legacy_slug:
            _error(error_type, path, f"invalid legacy slug: {legacy_slug}")

    files = manifest["files"]
    if not files and manifest["kind"] != BLOG_ONLY_KIND:
        _error(
            error_type,
            path,
            f"files may be empty only for kind={BLOG_ONLY_KIND}",
        )
    build = manifest["build"]
    engine = build.get("engine", "")
    if engine.strip() and engine.strip() not in LATEXMKRC_BY_ENGINE:
        _error(
            error_type,
            path,
            "build.engine must be one of: "
            + ", ".join(sorted(LATEXMKRC_BY_ENGINE)),
        )
    if build["enabled"] and "root" not in build:
        _error(error_type, path, "build.root is required when build is enabled")
    if manifest["kind"] == BLOG_ONLY_KIND:
        if build["enabled"]:
            _error(error_type, path, f"{BLOG_ONLY_KIND} cannot enable a TeX build")
        if files:
            _error(error_type, path, f"{BLOG_ONLY_KIND} must not contain files")
        if not manifest["original_url"].strip():
            _error(error_type, path, f"{BLOG_ONLY_KIND} requires original_url")

    seen: set[str] = set()
    for entry in files:
        raw_relative = entry["path"]
        if raw_relative != normalize_nfc(raw_relative):
            _error(
                error_type,
                path,
                f"file path must use NFC Unicode: {raw_relative}",
            )
        relative = str(safe_relative_path(raw_relative, error_type))
        if relative in seen:
            _error(error_type, path, f"duplicate file entry: {relative}")
        seen.add(relative)
    if build["enabled"]:
        root = build["root"]
        if root != normalize_nfc(root):
            _error(error_type, path, "build.root must use NFC Unicode")
        safe_relative_path(root, error_type)
        if root not in seen:
            _error(error_type, path, "build.root must appear in files")
    if not build["enabled"] and "published.pdf" not in seen and "main.tex" in seen:
        _error(
            error_type,
            path,
            "source-only papers must not use main.tex; use source.tex",
        )

    approved_paths = {
        change_file["path"]
        for change in manifest["approved_changes"]
        for change_file in change["files"]
    }
    unknown_approved = sorted(approved_paths - seen)
    if unknown_approved:
        _error(
            error_type,
            path,
            "approved change refers to unknown files: " + ", ".join(unknown_approved),
        )
    for change in manifest["approved_changes"]:
        try:
            parse_iso_datetime(change["approved_at"])
        except ValueError as error:
            raise error_type(f"{path}: approved_at must be ISO 8601") from error

    if manifest["schema_version"] == 2:
        reviews = manifest.get("privacy_reviews")
        if not isinstance(reviews, list):
            _error(error_type, path, "schema 2 requires privacy_reviews")
        expected = {
            entry["path"]: entry["sha256"]
            for entry in files
            if entry["public"]
            and Path(entry["path"]).suffix.casefold() in {".tex", ".pdf"}
        }
        reviewed: dict[str, str] = {}
        for review in reviews:
            relative = str(safe_relative_path(review["path"], error_type))
            if relative in reviewed:
                _error(error_type, path, f"duplicate privacy review for {relative}")
            if review["status"] == "overridden" and not review["reason"].strip():
                _error(error_type, path, f"privacy override reason is empty for {relative}")
            try:
                parse_iso_datetime(review["recorded_at"])
            except ValueError as error:
                raise error_type(f"{path}: recorded_at must be ISO 8601") from error
            reviewed[relative] = review["source_sha256"]
        if reviewed != expected:
            missing = sorted(set(expected) - set(reviewed))
            extra = sorted(set(reviewed) - set(expected))
            mismatched = sorted(
                relative
                for relative in set(expected) & set(reviewed)
                if expected[relative] != reviewed[relative]
            )
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("extra: " + ", ".join(extra))
            if mismatched:
                details.append("hash mismatch: " + ", ".join(mismatched))
            _error(
                error_type,
                path,
                f"invalid privacy review coverage ({'; '.join(details)})",
            )

    statement_ids = [item["identifier"] for item in manifest.get("statements", [])]
    if len(statement_ids) != len(set(statement_ids)):
        _error(error_type, path, "statements contain duplicate identifiers")


def validate_manifest_collection(
    papers: Iterable[Paper], error_type: Type[DempaSiteError]
) -> None:
    papers = tuple(papers)
    slugs = {paper.slug for paper in papers}
    for paper in papers:
        missing = sorted(
            {relation.target_slug for relation in paper.relations} - slugs
        )
        if missing:
            _error(
                error_type,
                paper.source_path,
                "relations refer to unknown paper slugs: " + ", ".join(missing),
            )

