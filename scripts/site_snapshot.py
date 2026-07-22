#!/usr/bin/env python3
"""Create and verify a deterministic inventory of the staged public site."""

from __future__ import annotations

import argparse
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dempa_site.errors import SiteSnapshotError  # noqa: E402
from dempa_site.files import read_json, sha256_file, write_json  # noqa: E402
from dempa_site.manifests.loader import load_manifest  # noqa: E402
from dempa_site.paths import RepositoryPaths  # noqa: E402


PATHS = RepositoryPaths.from_environment("PAPER_REPO_ROOT", __file__)
ROOT = PATHS.root
PAPERS_DIR = PATHS.papers
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "site-baseline.json"

sha256 = sha256_file


def generated_pdf_paths() -> set[str]:
    """Return staged PDFs whose bytes can vary between TeX environments."""
    paths: set[str] = set()
    for manifest_path in sorted(PAPERS_DIR.glob("*/paper.json")):
        manifest = load_manifest(manifest_path, SiteSnapshotError)
        if not manifest.build.enabled:
            continue
        slugs = [manifest.slug, *manifest.legacy_slugs]
        for slug in slugs:
            if not isinstance(slug, str) or not slug:
                raise SiteSnapshotError(f"{manifest_path}: invalid slug")
            paths.add(f"papers/{slug}/main.pdf")
    return paths


def snapshot(site_root: Path) -> dict[str, Any]:
    site_root = site_root.resolve()
    if not site_root.is_dir():
        raise SiteSnapshotError(f"staged site does not exist: {site_root}")
    ignored_hashes = generated_pdf_paths()
    entries: list[dict[str, Any]] = []
    for path in sorted(site_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(site_root).as_posix()
        entries.append(
            {
                "path": relative,
                "sha256": None if relative in ignored_hashes else sha256(path),
            }
        )
    present = {entry["path"] for entry in entries}
    missing_generated = sorted(ignored_hashes - present)
    if missing_generated:
        raise SiteSnapshotError(
            "generated PDF is missing from staged site: " + ", ".join(missing_generated)
        )
    return {
        "schema_version": 1,
        "hash_policy": {
            "ignored_paths": sorted(ignored_hashes),
            "reason": "TeX-generated PDFs are checked for presence only because build metadata may vary by environment.",
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


def write_baseline(site_root: Path, baseline_path: Path) -> None:
    value = snapshot(site_root)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(baseline_path, value)
    ignored = len(value["hash_policy"]["ignored_paths"])
    print(
        f"WROTE {baseline_path} ({len(value['files'])} files; "
        f"{ignored} generated PDFs presence-only)"
    )


def check_baseline(site_root: Path, baseline_path: Path) -> None:
    expected = load_baseline(baseline_path)
    actual = snapshot(site_root)
    expected_files = file_map(expected, "baseline")
    actual_files = file_map(actual, "staged site")
    errors: list[str] = []
    for path in sorted(set(actual_files) - set(expected_files)):
        errors.append(f"added: {path}")
    for path in sorted(set(expected_files) - set(actual_files)):
        errors.append(f"removed: {path}")
    for path in sorted(set(expected_files) & set(actual_files)):
        if expected_files[path] != actual_files[path]:
            errors.append(f"changed: {path}")
    expected_policy = expected.get("hash_policy")
    if expected_policy != actual["hash_policy"]:
        errors.append("generated-PDF hash policy changed")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise SiteSnapshotError(
            "public site differs from the approved baseline; review the difference "
            "and rewrite the baseline only for an intentional public change"
        )
    ignored = len(actual["hash_policy"]["ignored_paths"])
    print(
        f"OK  public site snapshot ({len(actual_files)} files; "
        f"{ignored} generated PDFs presence-only)"
    )


def baseline_path(value: str | None) -> Path:
    return Path(value).resolve() if value else DEFAULT_BASELINE


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Create or verify the staged public-site baseline."
    )
    subparsers = result.add_subparsers(dest="command", required=True)
    write_parser = subparsers.add_parser("write", help="write an approved baseline")
    write_parser.add_argument("site")
    write_parser.add_argument("--baseline")
    check_parser = subparsers.add_parser("check", help="compare a site with the baseline")
    check_parser.add_argument("site")
    check_parser.add_argument("--baseline")
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        site_root = Path(args.site)
        target = baseline_path(args.baseline)
        if args.command == "write":
            write_baseline(site_root, target)
        else:
            check_baseline(site_root, target)
        return 0
    except SiteSnapshotError as error:
        print(f"site-snapshot: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
