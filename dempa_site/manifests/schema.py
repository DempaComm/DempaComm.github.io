"""Dependency-free validation for the JSON Schema subset used by paper.json."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Type

from dempa_site.errors import DempaSiteError


def _resolve_reference(schema: Mapping[str, Any], root: Mapping[str, Any]) -> Mapping[str, Any]:
    reference = schema.get("$ref")
    if not reference:
        return schema
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise ValueError(f"unsupported JSON Schema reference: {reference!r}")
    resolved: Any = root
    for part in reference[2:].split("/"):
        resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
    return resolved


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    raise ValueError(f"unsupported JSON Schema type: {expected}")


def _validate(
    value: Any,
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    location: str,
) -> None:
    schema = _resolve_reference(schema, root)
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        raise ValueError(f"{location} must be {expected_type}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{location} must be one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValueError(f"{location} must not be empty")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise ValueError(f"{location} has an invalid format")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{location} must be at least {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{location} has too few items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate(item, item_schema, root, f"{location}[{index}]")
    if isinstance(value, dict):
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise ValueError(f"{location} is missing: {', '.join(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ValueError(f"{location} has unknown fields: {', '.join(extras)}")
        for key, child in value.items():
            if key in properties:
                _validate(child, properties[key], root, f"{location}.{key}")


def validate_json_schema(
    value: Any,
    schema: Mapping[str, Any],
    path: Path,
    error_type: Type[DempaSiteError],
) -> None:
    try:
        _validate(value, schema, schema, "paper.json")
    except ValueError as error:
        raise error_type(f"{path}: schema validation failed: {error}") from error

