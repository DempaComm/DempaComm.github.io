"""Shared destination, copy, manifest, and rollback steps for imports."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.dates import local_now_seconds, parse_iso_datetime
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.loader import load_schema
from dempa_site.manifests.model import Paper
from dempa_site.manifests.validation import validate_manifest_data
from dempa_site.paths import RepositoryPaths
from dempa_site.protection.hashes import protected_file_errors
from dempa_site.protection.privacy import (
    privacy_review_for_path,
    require_privacy_review,
)


@dataclass(frozen=True)
class ImportResult:
    slug: str
    message: str


@dataclass(frozen=True)
class PublicationIdentity:
    published: datetime
    published_at: str
    sequence: int
    slug: str
    destination: Path


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = read_json(path)
    except (OSError, JSONDecodeError) as error:
        raise PaperToolError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise PaperToolError(f"JSON root must be an object: {path}")
    return value


def next_sequence_for_date(papers_dir: Path, published: datetime) -> int:
    used: list[int] = []
    for manifest_path in sorted(papers_dir.glob("*/paper.json")):
        manifest = load_json_object(manifest_path)
        validate_manifest_data(
            manifest, manifest_path, load_schema(), PaperToolError
        )
        if str(manifest["published_at"])[:10] == f"{published:%Y-%m-%d}":
            used.append(int(manifest["sequence"]))
    return max(used, default=0) + 1


def single_file_identity(
    paths: RepositoryPaths,
    published_at_value: str | None,
    sequence_value: int | None,
) -> PublicationIdentity:
    if published_at_value:
        try:
            published = parse_iso_datetime(published_at_value)
        except ValueError as error:
            raise PaperToolError("--published-at must be ISO 8601") from error
        published_at = published_at_value
    else:
        published = local_now_seconds()
        published_at = published.isoformat()
    sequence = sequence_value or next_sequence_for_date(paths.papers, published)
    if sequence < 1:
        raise PaperToolError("--sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    destination = paths.papers / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")
    return PublicationIdentity(
        published, published_at, sequence, slug, destination
    )


def copy_byte_identical(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    source_hash = sha256_file(source)
    if sha256_file(target) != source_hash:
        raise PaperToolError(f"copy verification failed: {source}")
    return source_hash


def write_and_validate_manifest(
    destination: Path, manifest: dict[str, Any]
) -> None:
    manifest_path = destination / "paper.json"
    write_json(manifest_path, manifest)
    (destination / "keywords.txt").write_text(
        rendered_keywords(manifest), encoding="utf-8"
    )
    validate_manifest_data(
        manifest, manifest_path, load_schema(), PaperToolError
    )
    errors = protected_file_errors(
        manifest_path,
        Paper.from_dict(manifest, manifest_path),
        PaperToolError,
    )
    if errors:
        raise PaperToolError("; ".join(errors))


def create_single_file_paper(
    *,
    paths: RepositoryPaths,
    review_root: Path,
    source: Path,
    target_name: str,
    role: str,
    label: str,
    title: str,
    kind: str,
    summary: str,
    published_at: str | None,
    sequence: int | None,
    original_url: str | None,
    privacy_reviewed: bool,
    privacy_override: str | None,
) -> ImportResult:
    privacy_review = require_privacy_review(
        source, review_root, privacy_reviewed, privacy_override
    )
    identity = single_file_identity(paths, published_at, sequence)
    try:
        identity.destination.mkdir(parents=True)
        source_hash = copy_byte_identical(
            source, identity.destination / target_name
        )
        manifest = {
            "schema_version": 2,
            "slug": identity.slug,
            "legacy_slugs": [],
            "title": title,
            "published_at": identity.published_at,
            "sequence": identity.sequence,
            "year": identity.published.year,
            "kind": kind,
            "math_section": "",
            "summary": summary,
            "original_url": original_url or "",
            "order": int(
                f"{identity.published:%Y%m%d}{identity.sequence:02d}"
            ),
            "tags": ["数学"],
            "keywords": [title],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": target_name,
                    "role": role,
                    "label": label,
                    "public": True,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [
                privacy_review_for_path(privacy_review, Path(target_name))
            ],
        }
        write_and_validate_manifest(identity.destination, manifest)
    except Exception:
        shutil.rmtree(identity.destination, ignore_errors=True)
        raise
    return ImportResult(identity.slug, "")

