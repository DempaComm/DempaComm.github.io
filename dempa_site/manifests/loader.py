"""Read paper.json files, validate them, and return typed models."""

from __future__ import annotations

from functools import lru_cache
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterable, Mapping, Type

from dempa_site.errors import DempaSiteError
from dempa_site.files import read_json

from .model import Paper
from .validation import validate_manifest_collection, validate_manifest_data


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "paper.schema.json"


@lru_cache(maxsize=None)
def load_schema(path: Path = DEFAULT_SCHEMA_PATH) -> Mapping[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"JSON Schema root must be an object: {path}")
    return value


def load_manifest(
    path: Path,
    error_type: Type[DempaSiteError] = DempaSiteError,
) -> Paper:
    try:
        value = read_json(path)
    except (OSError, JSONDecodeError) as error:
        raise error_type(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise error_type(f"JSON root must be an object: {path}")
    validate_manifest_data(value, path, load_schema(), error_type)
    return Paper.from_dict(value, path)


def load_manifest_directory(
    papers_dir: Path,
    slugs: Iterable[str] | None = None,
    error_type: Type[DempaSiteError] = DempaSiteError,
) -> list[tuple[Path, Paper]]:
    wanted = set(slugs or [])
    all_found: list[tuple[Path, Paper]] = []
    for path in sorted(papers_dir.glob("*/paper.json")):
        paper = load_manifest(path, error_type)
        all_found.append((path, paper))
    validate_manifest_collection((paper for _, paper in all_found), error_type)
    found = [
        item for item in all_found if not wanted or item[1].slug in wanted
    ]
    if wanted:
        missing = wanted - {paper.slug for _, paper in found}
        if missing:
            raise error_type(f"unknown paper slug(s): {', '.join(sorted(missing))}")
    if not found:
        raise error_type("no paper manifests found")
    return sorted(found, key=lambda item: (item[1].order, item[1].slug))
