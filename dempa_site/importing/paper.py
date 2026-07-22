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
from dempa_site.errors import PaperToolError
from dempa_site.files import normalize_nfc
from dempa_site.importing.common import (
    ImportResult,
    copy_byte_identical,
    load_json_object,
    write_and_validate_manifest,
)
from dempa_site.importing.spec import ImportFileSpec, ImportSpec
from dempa_site.paths import RepositoryPaths, safe_relative_path
from dempa_site.protection.privacy import (
    privacy_review_for_path,
    require_privacy_review,
)


def resolve_source_dir(spec_path: Path, spec: ImportSpec) -> Path:
    raw = Path(spec.source_dir)
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
    spec = ImportSpec.from_dict(load_json_object(spec_path))
    source_dir = (
        resolve_source_dir(spec_path, spec) if spec.files else spec_path.parent
    )
    if spec.files and not source_dir.is_dir():
        raise PaperToolError(f"source_dir does not exist: {source_dir}")
    destination = paths.papers / spec.slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    reviewed_flag = privacy_reviewed or spec.privacy_reviewed
    override_value = (
        privacy_override
        if privacy_override is not None
        else spec.privacy_override
    )
    prepared_files: list[tuple[ImportFileSpec, Path, Path]] = []
    target_paths: set[Path] = set()
    for entry in spec.files:
        source_relative = safe_relative_path(entry.source, PaperToolError)
        target_relative = safe_relative_path(
            normalize_nfc(entry.path), PaperToolError
        )
        source = (source_dir / source_relative).resolve()
        try:
            source.relative_to(source_dir)
        except ValueError as error:
            raise PaperToolError(f"source escapes source_dir: {source}") from error
        if not source.is_file():
            raise PaperToolError(f"source file does not exist: {source}")
        if target_relative in target_paths:
            raise PaperToolError(f"duplicate import target: {target_relative}")
        target_paths.add(target_relative)
        prepared_files.append((entry, source, target_relative))

    normalized_build_root: Path | None = None
    if spec.build_enabled:
        normalized_build_root = safe_relative_path(
            normalize_nfc(spec.build_root), PaperToolError
        )
        if normalized_build_root not in target_paths:
            raise PaperToolError("spec.build_root must appear in spec.files paths")

    privacy_reviews: list[dict[str, Any]] = []
    if spec.blog_only:
        emit(f"BLOG ARTICLE LINK TO IMPORT: {spec.original_url}")
    else:
        emit("PUBLIC FILES TO IMPORT:")
    for entry, source, target_relative in prepared_files:
        if entry.public:
            emit(f"- {target_relative} ({entry.role})")
        if entry.public and target_relative.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(
                source, review_root, reviewed_flag, override_value
            )
            privacy_reviews.append(
                privacy_review_for_path(review, target_relative)
            )

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
                    "role": entry.role,
                    "label": entry.label,
                    "public": entry.public,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            )
        effective_engine = spec.build_engine or DEFAULT_BUILD_ENGINE
        latexmkrc = destination / ".latexmkrc"
        if spec.build_enabled and not latexmkrc.exists():
            latexmkrc.write_text(
                LATEXMKRC_BY_ENGINE[effective_engine], encoding="utf-8"
            )
        manifest = {
            "schema_version": 2,
            "slug": spec.slug,
            "migration_record_id": spec.migration_record_id,
            "legacy_slugs": list(spec.legacy_slugs),
            "title": spec.title,
            "published_at": spec.published_at,
            "sequence": spec.sequence,
            "year": spec.published.year,
            "kind": spec.kind,
            "math_section": spec.math_section,
            "summary": spec.summary,
            "original_url": spec.original_url,
            "order": int(f"{spec.published:%Y%m%d}{spec.sequence:02d}"),
            "tags": list(spec.tags),
            "keywords": list(spec.keywords),
            "build": (
                {
                    "enabled": True,
                    "root": str(normalized_build_root),
                    "engine": spec.build_engine,
                }
                if spec.build_enabled
                else {"enabled": False, "engine": spec.build_engine}
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
        f"IMPORTED {spec.slug} as {BLOG_ONLY_KIND}"
        if spec.blog_only
        else f"IMPORTED {spec.slug} with byte-identical protected files"
    )
    return ImportResult(spec.slug, message)
