"""Safe helpers for reviewing and finishing intentional paper changes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path
from dempa_site.protection.privacy import inspect_file


@dataclass(frozen=True)
class ReviewedChange:
    path: str
    report_directory: Path | None
    findings: tuple[str, ...]


def _requested_entries(paper: Paper, requested_files: list[str]):
    requested = tuple(dict.fromkeys(requested_files))
    if not requested:
        raise PaperToolError("at least one --file is required")
    entries = {entry.path: entry for entry in paper.files}
    unknown = [path for path in requested if path not in entries]
    if unknown:
        raise PaperToolError(
            "files are not protected by paper.json: " + ", ".join(unknown)
        )
    return requested, entries


def changed_protected_files(manifest_path: Path, paper: Paper) -> set[str]:
    changed: set[str] = set()
    for entry in paper.files:
        target = manifest_path.parent / safe_relative_path(
            entry.path, PaperToolError
        )
        if not target.is_file() or sha256_file(target) != entry.sha256:
            changed.add(entry.path)
    return changed


def review_changes(
    manifest_path: Path,
    paper: Paper,
    review_root: Path,
    requested_files: list[str],
) -> tuple[ReviewedChange, ...]:
    """Inspect changed public TeX/PDF files without approving any hash."""
    requested, entries = _requested_entries(paper, requested_files)
    changed = changed_protected_files(manifest_path, paper)
    outside = sorted(changed - set(requested))
    if outside:
        raise PaperToolError(
            "unapproved change exists outside requested files: "
            + ", ".join(outside)
        )
    unchanged = [path for path in requested if path not in changed]
    if unchanged:
        raise PaperToolError(
            "requested files have no hash changes: " + ", ".join(unchanged)
        )

    reviewed: list[ReviewedChange] = []
    for path in requested:
        entry = entries[path]
        target = manifest_path.parent / safe_relative_path(path, PaperToolError)
        if entry.public and target.suffix.casefold() in {".tex", ".pdf"}:
            inspection = inspect_file(target, review_root)
            reviewed.append(
                ReviewedChange(path, inspection.output, inspection.findings)
            )
        else:
            reviewed.append(ReviewedChange(path, None, ()))
    return tuple(reviewed)


def allowed_public_changes(paper: Paper, requested_files: list[str]) -> set[str]:
    """Return snapshot paths that one protected-file approval may change."""
    requested, entries = _requested_entries(paper, requested_files)
    allowed: set[str] = set()
    for slug in (paper.slug, *paper.legacy_slugs):
        allowed.add(f"papers/{slug}/paper.json")
        for path in requested:
            if entries[path].public:
                allowed.add(f"papers/{slug}/{Path(path).as_posix()}")
    return allowed


def resumable_change_count(
    paper: Paper, requested_files: list[str], reason: str
) -> int | None:
    """Recognise the immediately preceding approval for a safe retry."""
    requested, entries = _requested_entries(paper, requested_files)
    if not paper.approved_changes:
        return None
    latest = paper.approved_changes[-1]
    if latest.reason != reason.strip():
        return None
    approved = {item.path: item.to_sha256 for item in latest.files}
    if set(approved) != set(requested):
        return None
    if any(entries[path].sha256 != digest for path, digest in approved.items()):
        return None
    return len(approved)


def unexpected_public_differences(
    differences: tuple[str, ...], allowed_paths: set[str]
) -> tuple[str, ...]:
    unexpected: list[str] = []
    for difference in differences:
        prefix = "changed: "
        if not difference.startswith(prefix):
            unexpected.append(difference)
            continue
        if difference.removeprefix(prefix) not in allowed_paths:
            unexpected.append(difference)
    return tuple(unexpected)
