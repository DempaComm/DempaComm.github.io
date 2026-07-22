"""Immutable typed views of validated paper manifests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Tuple

from dempa_site.config import DEFAULT_BUILD_ENGINE
from dempa_site.dates import parse_iso_datetime


@dataclass(frozen=True)
class PaperFile:
    path: str
    role: str
    label: str
    public: bool
    original_sha256: str
    sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PaperFile":
        return cls(
            path=value["path"],
            role=value["role"],
            label=value["label"],
            public=value["public"],
            original_sha256=value["original_sha256"],
            sha256=value["sha256"],
        )


@dataclass(frozen=True)
class BuildSettings:
    enabled: bool
    engine: str
    root: Optional[str] = None

    @property
    def effective_engine(self) -> str:
        return self.engine or DEFAULT_BUILD_ENGINE

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BuildSettings":
        return cls(
            enabled=value["enabled"],
            engine=value.get("engine", ""),
            root=value.get("root"),
        )


@dataclass(frozen=True)
class PrivacyReview:
    path: str
    status: str
    reason: str
    source_sha256: str
    inspection_status: str
    recorded_at: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PrivacyReview":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class ApprovedChangeFile:
    path: str
    from_sha256: str
    to_sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ApprovedChangeFile":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class ApprovedChange:
    approved_at: str
    reason: str
    files: Tuple[ApprovedChangeFile, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ApprovedChange":
        return cls(
            approved_at=value["approved_at"],
            reason=value["reason"],
            files=tuple(ApprovedChangeFile.from_dict(item) for item in value["files"]),
        )


@dataclass(frozen=True)
class HistoryEvent:
    recorded_at: str
    kind: str
    summary: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HistoryEvent":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Correction:
    recorded_at: str
    summary: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Correction":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Statement:
    identifier: str
    kind: str
    title: str
    anchor: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Statement":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class PaperRelation:
    target_slug: str
    kind: str
    label: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PaperRelation":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Paper(Mapping[str, Any]):
    """Validated manifest with typed fields and a read-only legacy mapping view."""

    source_path: Path
    schema_version: int
    slug: str
    migration_record_id: str
    legacy_slugs: Tuple[str, ...]
    title: str
    published_at: datetime
    published_at_text: str
    sequence: int
    year: int
    kind: str
    math_section: str
    summary: str
    original_url: str
    order: int
    tags: Tuple[str, ...]
    keywords: Tuple[str, ...]
    build: BuildSettings
    files: Tuple[PaperFile, ...]
    approved_changes: Tuple[ApprovedChange, ...]
    privacy_reviews: Tuple[PrivacyReview, ...]
    history: Tuple[HistoryEvent, ...] = ()
    corrections: Tuple[Correction, ...] = ()
    statements: Tuple[Statement, ...] = ()
    relations: Tuple[PaperRelation, ...] = ()
    license: str = ""
    _raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], source_path: Path) -> "Paper":
        return cls(
            source_path=source_path,
            schema_version=value["schema_version"],
            slug=value["slug"],
            migration_record_id=value.get("migration_record_id", ""),
            legacy_slugs=tuple(value["legacy_slugs"]),
            title=value["title"],
            published_at=parse_iso_datetime(value["published_at"]),
            published_at_text=value["published_at"],
            sequence=value["sequence"],
            year=value["year"],
            kind=value["kind"],
            math_section=value.get("math_section", ""),
            summary=value["summary"],
            original_url=value["original_url"],
            order=value["order"],
            tags=tuple(value["tags"]),
            keywords=tuple(value["keywords"]),
            build=BuildSettings.from_dict(value["build"]),
            files=tuple(PaperFile.from_dict(item) for item in value["files"]),
            approved_changes=tuple(
                ApprovedChange.from_dict(item)
                for item in value["approved_changes"]
            ),
            privacy_reviews=tuple(
                PrivacyReview.from_dict(item)
                for item in value.get("privacy_reviews", [])
            ),
            history=tuple(
                HistoryEvent.from_dict(item) for item in value.get("history", [])
            ),
            corrections=tuple(
                Correction.from_dict(item)
                for item in value.get("corrections", [])
            ),
            statements=tuple(
                Statement.from_dict(item) for item in value.get("statements", [])
            ),
            relations=tuple(
                PaperRelation.from_dict(item) for item in value.get("relations", [])
            ),
            license=value.get("license", ""),
            _raw=deepcopy(dict(value)),
        )

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self._raw))

    def __getitem__(self, key: str) -> Any:
        return deepcopy(self._raw[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._raw)

    def __len__(self) -> int:
        return len(self._raw)
