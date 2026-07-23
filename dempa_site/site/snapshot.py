"""Create, compare, and approve deterministic public-site inventories."""

from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import Any, Callable

from dempa_site.errors import SiteSnapshotError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.loader import load_manifest


Emitter = Callable[[str], None]


def generated_pdf_paths(papers_dir: Path) -> set[str]:
    """Return staged PDFs whose bytes can vary between TeX environments."""
    paths: set[str] = set()
    for manifest_path in sorted(papers_dir.glob("*/paper.json")):
        manifest = load_manifest(manifest_path, SiteSnapshotError)
        if not manifest.build.enabled:
            continue
        for slug in (manifest.slug, *manifest.legacy_slugs):
            if not slug:
                raise SiteSnapshotError(f"{manifest_path}: invalid slug")
            paths.add(f"papers/{slug}/main.pdf")
    return paths


def snapshot(site_root: Path, papers_dir: Path) -> dict[str, Any]:
    site_root = site_root.resolve()
    if not site_root.is_dir():
        raise SiteSnapshotError(f"staged site does not exist: {site_root}")
    ignored_hashes = generated_pdf_paths(papers_dir)
    entries: list[dict[str, Any]] = []
    for path in sorted(site_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(site_root).as_posix()
        entries.append(
            {
                "path": relative,
                "sha256": None if relative in ignored_hashes else sha256_file(path),
            }
        )
    present = {entry["path"] for entry in entries}
    missing_generated = sorted(ignored_hashes - present)
    if missing_generated:
        raise SiteSnapshotError(
            "generated PDF is missing from staged site: "
            + ", ".join(missing_generated)
        )
    return {
        "schema_version": 1,
        "hash_policy": {
            "ignored_paths": sorted(ignored_hashes),
            "reason": (
                "TeX-generated PDFs are checked for presence only because build "
                "metadata may vary by environment."
            ),
        },
        "files": entries,
    }


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        value = read_json(path)
    except FileNotFoundError as error:
        raise SiteSnapshotError(f"baseline does not exist: {path}") from error
    except (OSError, JSONDecodeError) as error:
        raise SiteSnapshotError(f"cannot read baseline {path}: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SiteSnapshotError(f"unsupported baseline format: {path}")
    if not isinstance(value.get("files"), list):
        raise SiteSnapshotError(f"baseline has no files list: {path}")
    return value


def file_map(value: dict[str, Any], label: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for entry in value["files"]:
        if not isinstance(entry, dict):
            raise SiteSnapshotError(f"{label}: invalid file entry")
        path = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or (digest is not None and not isinstance(digest, str))
        ):
            raise SiteSnapshotError(f"{label}: invalid file entry")
        if path in result:
            raise SiteSnapshotError(f"{label}: duplicate path: {path}")
        result[path] = digest
    return result


def snapshot_differences(
    site_root: Path, papers_dir: Path, baseline_path: Path
) -> tuple[str, ...]:
    expected = load_baseline(baseline_path)
    actual = snapshot(site_root, papers_dir)
    expected_files = file_map(expected, "baseline")
    actual_files = file_map(actual, "staged site")
    differences: list[str] = []
    differences.extend(
        f"added: {path}" for path in sorted(set(actual_files) - set(expected_files))
    )
    differences.extend(
        f"removed: {path}" for path in sorted(set(expected_files) - set(actual_files))
    )
    differences.extend(
        f"changed: {path}"
        for path in sorted(set(expected_files) & set(actual_files))
        if expected_files[path] != actual_files[path]
    )
    if expected.get("hash_policy") != actual["hash_policy"]:
        differences.append("generated-PDF hash policy changed")
    return tuple(differences)


def write_baseline(
    site_root: Path,
    papers_dir: Path,
    baseline_path: Path,
    emit: Emitter = print,
) -> None:
    value = snapshot(site_root, papers_dir)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(baseline_path, value)
    ignored = len(value["hash_policy"]["ignored_paths"])
    emit(
        f"WROTE {baseline_path} ({len(value['files'])} files; "
        f"{ignored} generated PDFs presence-only)"
    )


def check_baseline(
    site_root: Path,
    papers_dir: Path,
    baseline_path: Path,
    emit: Emitter = print,
) -> None:
    differences = snapshot_differences(site_root, papers_dir, baseline_path)
    if differences:
        raise SiteSnapshotError("\n".join(differences))
    actual = snapshot(site_root, papers_dir)
    ignored = len(actual["hash_policy"]["ignored_paths"])
    emit(
        f"OK  public site snapshot ({len(actual['files'])} files; "
        f"{ignored} generated PDFs presence-only)"
    )
