"""Typed, fully preflighted input for normal multi-file imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from dempa_site.config import BLOG_ONLY_KIND, LATEXMKRC_BY_ENGINE
from dempa_site.dates import parse_iso_datetime
from dempa_site.errors import PaperToolError


def _required_string(value: Mapping[str, Any], key: str) -> str:
    if key not in value:
        raise PaperToolError(f"import spec missing field: {key}")
    result = value[key]
    if not isinstance(result, str):
        raise PaperToolError(f"spec.{key} must be a string")
    return result


def _optional_string(value: Mapping[str, Any], key: str, default: str = "") -> str:
    result = value.get(key, default)
    if not isinstance(result, str):
        raise PaperToolError(f"spec.{key} must be a string")
    return result


def _string_list(value: Mapping[str, Any], key: str) -> tuple[str, ...]:
    result = value.get(key)
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise PaperToolError(f"spec.{key} must be an array of strings")
    return tuple(result)


def _optional_boolean(
    value: Mapping[str, Any], key: str, default: bool
) -> bool:
    result = value.get(key, default)
    if not isinstance(result, bool):
        raise PaperToolError(f"spec.{key} must be true or false")
    return result


@dataclass(frozen=True)
class ImportFileSpec:
    source: str
    path: str
    role: str
    label: str
    public: bool

    @classmethod
    def from_value(cls, value: Any, index: int) -> "ImportFileSpec":
        prefix = f"spec.files[{index}]"
        if not isinstance(value, dict):
            raise PaperToolError(f"{prefix} must be an object")
        for key in ("source", "path", "role"):
            if not isinstance(value.get(key), str) or not value[key]:
                raise PaperToolError(f"{prefix}.{key} must be a non-empty string")
        label = value.get("label", "")
        if not isinstance(label, str):
            raise PaperToolError(f"{prefix}.label must be a string")
        public = value.get("public", True)
        if not isinstance(public, bool):
            raise PaperToolError(f"{prefix}.public must be true or false")
        return cls(value["source"], value["path"], value["role"], label, public)


@dataclass(frozen=True)
class ImportSpec:
    title: str
    published_at: str
    published: datetime
    sequence: int
    kind: str
    summary: str
    original_url: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]
    files: tuple[ImportFileSpec, ...]
    source_dir: str
    migration_record_id: str
    legacy_slugs: tuple[str, ...]
    math_section: str
    build_enabled: bool
    build_root: str
    build_engine: str
    privacy_reviewed: bool
    privacy_override: str | None

    @property
    def blog_only(self) -> bool:
        return self.kind == BLOG_ONLY_KIND

    @property
    def slug(self) -> str:
        return f"{self.published:%Y-%m-%d}-{self.sequence:02d}"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ImportSpec":
        title = _required_string(value, "title")
        published_at = _required_string(value, "published_at")
        try:
            published = parse_iso_datetime(published_at)
        except ValueError as error:
            raise PaperToolError("spec.published_at must be ISO 8601") from error
        sequence = value.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise PaperToolError("spec.sequence must be a positive integer")
        kind = _required_string(value, "kind")
        summary = _required_string(value, "summary")
        original_url = _required_string(value, "original_url")
        tags = _string_list(value, "tags")
        keywords = _string_list(value, "keywords")
        raw_files = value.get("files")
        if not isinstance(raw_files, list):
            raise PaperToolError("spec.files must be an array")
        files = tuple(
            ImportFileSpec.from_value(item, index)
            for index, item in enumerate(raw_files)
        )
        blog_only = kind == BLOG_ONLY_KIND
        if not files and not blog_only:
            raise PaperToolError(
                f"spec.files may be empty only for kind={BLOG_ONLY_KIND}"
            )
        if files and blog_only:
            raise PaperToolError(f"kind={BLOG_ONLY_KIND} must not contain files")
        source_dir = _optional_string(value, "source_dir")
        if files and not source_dir.strip():
            raise PaperToolError("spec.source_dir is required")
        migration_record_id = _optional_string(
            value, "migration_record_id"
        ).strip()
        legacy_slugs = (
            _string_list(value, "legacy_slugs")
            if "legacy_slugs" in value
            else ()
        )
        math_section = _optional_string(value, "math_section").strip()
        build_enabled = _optional_boolean(value, "build_enabled", not blog_only)
        if blog_only and build_enabled:
            raise PaperToolError(f"kind={BLOG_ONLY_KIND} cannot enable a TeX build")
        build_root = _optional_string(value, "build_root", "main.tex")
        if build_enabled and not build_root:
            raise PaperToolError("spec.build_root must be a non-empty string")
        build_engine = _optional_string(value, "build_engine").strip()
        if build_engine and build_engine not in LATEXMKRC_BY_ENGINE:
            raise PaperToolError(
                "build_engine must be one of: "
                + ", ".join(sorted(LATEXMKRC_BY_ENGINE))
            )
        reviewed = _optional_boolean(value, "privacy_reviewed", False)
        override = value.get("privacy_override")
        if override is not None and not isinstance(override, str):
            raise PaperToolError("privacy_override must be a string")
        return cls(
            title=title,
            published_at=published_at,
            published=published,
            sequence=sequence,
            kind=kind,
            summary=summary,
            original_url=original_url,
            tags=tags,
            keywords=keywords,
            files=files,
            source_dir=source_dir,
            migration_record_id=migration_record_id,
            legacy_slugs=legacy_slugs,
            math_section=math_section,
            build_enabled=build_enabled,
            build_root=build_root,
            build_engine=build_engine,
            privacy_reviewed=reviewed,
            privacy_override=override,
        )
