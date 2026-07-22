"""Record explicitly requested changes to protected paper files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dempa_site.dates import utc_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.loader import load_schema
from dempa_site.manifests.model import Paper
from dempa_site.manifests.validation import validate_manifest_data
from dempa_site.paths import safe_relative_path
from dempa_site.protection.privacy import (
    privacy_review_for_path,
    require_privacy_review,
)


def approve_changes(
    manifest_path: Path,
    typed_manifest: Paper,
    review_root: Path,
    reason: str,
    requested_files: list[str],
    privacy_reviewed: bool,
    privacy_override: str | None,
) -> int:
    reason = reason.strip()
    if not reason:
        raise PaperToolError("approval reason must not be empty")
    manifest = typed_manifest.to_dict()
    requested = list(dict.fromkeys(requested_files))
    requested_set = set(requested)
    entries = {entry["path"]: entry for entry in manifest["files"]}
    unknown = [path for path in requested if path not in entries]
    if unknown:
        raise PaperToolError(
            f"files are not protected by paper.json: {', '.join(unknown)}"
        )
    for entry in manifest["files"]:
        if entry["path"] in requested_set:
            continue
        target = manifest_path.parent / safe_relative_path(
            entry["path"], PaperToolError
        )
        if not target.is_file() or sha256_file(target) != entry["sha256"]:
            raise PaperToolError(
                f"unapproved change exists outside requested files: {entry['path']}"
            )

    changes: list[dict[str, str]] = []
    privacy_updates: dict[str, dict[str, Any]] = {}
    for value in requested:
        relative = safe_relative_path(value, PaperToolError)
        target = manifest_path.parent / relative
        if not target.is_file():
            raise PaperToolError(f"cannot approve missing file: {target}")
        old_hash = entries[value]["sha256"]
        new_hash = sha256_file(target)
        if old_hash == new_hash:
            continue
        entry = entries[value]
        if entry["public"] and target.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(
                target,
                review_root,
                privacy_reviewed,
                privacy_override,
            )
            privacy_updates[value] = privacy_review_for_path(review, relative)
        entries[value]["sha256"] = new_hash
        changes.append(
            {"path": value, "from_sha256": old_hash, "to_sha256": new_hash}
        )
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
    validate_manifest_data(
        manifest, manifest_path, load_schema(), PaperToolError
    )
    write_json(manifest_path, manifest)
    return len(changes)

