"""Verify byte-protected files against their approved SHA-256 values."""

from __future__ import annotations

from pathlib import Path
from typing import Type

from dempa_site.errors import DempaSiteError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path


def protected_file_errors(
    manifest_path: Path,
    paper: Paper,
    error_type: Type[DempaSiteError] = DempaSiteError,
) -> list[str]:
    errors: list[str] = []
    paper_dir = manifest_path.parent
    for entry in paper.files:
        relative = safe_relative_path(entry.path, error_type)
        target = paper_dir / relative
        if not target.is_file():
            errors.append(f"{paper.slug}/{relative}: missing")
            continue
        actual = sha256_file(target)
        if actual != entry.sha256:
            errors.append(
                f"{paper.slug}/{relative}: SHA-256 mismatch "
                f"(expected {entry.sha256}, got {actual})"
            )
    return errors

