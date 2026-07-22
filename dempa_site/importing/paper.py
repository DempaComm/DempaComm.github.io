"""Import a normal multi-file paper or a blog-link-only record from JSON."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from dempa_site.config import (
    BLOG_ONLY_KIND,
    DEFAULT_BUILD_ENGINE,
    LATEXMKRC_BY_ENGINE,
)
from dempa_site.dates import parse_iso_datetime
from dempa_site.errors import PaperToolError
from dempa_site.files import normalize_nfc
from dempa_site.importing.common import (
    ImportResult,
    copy_byte_identical,
    load_json_object,
    write_and_validate_manifest,
)
from dempa_site.paths import RepositoryPaths, safe_relative_path
from dempa_site.protection.privacy import (
    privacy_review_for_path,
    require_privacy_review,
)


def resolve_source_dir(spec_path: Path, spec: dict[str, Any]) -> Path:
    raw_value = spec.get("source_dir")
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise PaperToolError("spec.source_dir is required")
    raw = Path(raw_value)
    return (raw if raw.is_absolute() else spec_path.parent / raw).resolve()


def import_paper(
    *,
    paths: RepositoryPaths,
    review_root: Path,
    spec_file: str,
    privacy_reviewed: bool,
    privacy_override: str | None,
    emit: Callable[[str], None] = print,
) -> ImportResult:
    spec_path = Path(spec_file).resolve()
    spec = load_json_object(spec_path)
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
        raise PaperToolError(
            f"spec.files may be empty only for kind={BLOG_ONLY_KIND}"
        )
    source_dir = resolve_source_dir(spec_path, spec) if files else spec_path.parent
    if files and not source_dir.is_dir():
        raise PaperToolError(f"source_dir does not exist: {source_dir}")
    destination = paths.papers / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    reviewed_flag = bool(privacy_reviewed or spec.get("privacy_reviewed", False))
    override_value = (
        privacy_override
        if privacy_override is not None
        else spec.get("privacy_override")
    )
    if override_value is not None and not isinstance(override_value, str):
        raise PaperToolError("privacy_override must be a string")
    prepared_files: list[tuple[dict[str, Any], Path, Path]] = []
    privacy_reviews: list[dict[str, Any]] = []
    if blog_only:
        emit(f"BLOG ARTICLE LINK TO IMPORT: {spec['original_url']}")
    else:
        emit("PUBLIC FILES TO IMPORT:")
    for entry in files:
        source_relative = safe_relative_path(str(entry["source"]), PaperToolError)
        target_relative = safe_relative_path(
            normalize_nfc(str(entry["path"])), PaperToolError
        )
        source = (source_dir / source_relative).resolve()
        try:
            source.relative_to(source_dir)
        except ValueError as error:
            raise PaperToolError(f"source escapes source_dir: {source}") from error
        if not source.is_file():
            raise PaperToolError(f"source file does not exist: {source}")
        is_public = bool(entry.get("public", True))
        if is_public:
            emit(f"- {target_relative} ({entry.get('role', 'file')})")
        if is_public and target_relative.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(
                source, review_root, reviewed_flag, override_value
            )
            privacy_reviews.append(
                privacy_review_for_path(review, target_relative)
            )
        prepared_files.append((entry, source, target_relative))

    manifest_files: list[dict[str, Any]] = []
    try:
        destination.mkdir(parents=True)
        for entry, source, target_relative in prepared_files:
            source_hash = copy_byte_identical(
                source, destination / target_relative
            )
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
            "migration_record_id": str(
                spec.get("migration_record_id", "")
            ).strip(),
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
                    "root": normalize_nfc(
                        str(spec.get("build_root", "main.tex"))
                    ),
                    "engine": build_engine,
                }
                if build_enabled
                else {"enabled": False, "engine": build_engine}
            ),
            "files": manifest_files,
            "approved_changes": [],
            "privacy_reviews": privacy_reviews,
        }
        write_and_validate_manifest(destination, manifest)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    message = (
        f"IMPORTED {slug} as {BLOG_ONLY_KIND}"
        if blog_only
        else f"IMPORTED {slug} with byte-identical protected files"
    )
    return ImportResult(slug, message)

