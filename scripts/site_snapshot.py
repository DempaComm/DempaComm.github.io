#!/usr/bin/env python3
"""Create and verify a deterministic inventory of the staged public site."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dempa_site.errors import SiteSnapshotError  # noqa: E402
from dempa_site.paths import RepositoryPaths  # noqa: E402
from dempa_site.site.snapshot import (  # noqa: E402
    check_baseline as shared_check_baseline,
    generated_pdf_paths as shared_generated_pdf_paths,
    snapshot as shared_snapshot,
    write_baseline as shared_write_baseline,
)


PATHS = RepositoryPaths.from_environment("PAPER_REPO_ROOT", __file__)
ROOT = PATHS.root
PAPERS_DIR = PATHS.papers
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "site-baseline.json"


def generated_pdf_paths() -> set[str]:
    return shared_generated_pdf_paths(PAPERS_DIR)


def snapshot(site_root: Path):
    return shared_snapshot(site_root, PAPERS_DIR)


def write_baseline(site_root: Path, baseline_path: Path) -> None:
    shared_write_baseline(site_root, PAPERS_DIR, baseline_path)


def check_baseline(site_root: Path, baseline_path: Path) -> None:
    try:
        shared_check_baseline(site_root, PAPERS_DIR, baseline_path)
    except SiteSnapshotError as error:
        for line in str(error).splitlines():
            print(f"ERR {line}", file=sys.stderr)
        raise SiteSnapshotError(
            "public site differs from the approved baseline; review the difference "
            "and rewrite the baseline only for an intentional public change"
        ) from error


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
