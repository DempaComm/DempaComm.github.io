#!/usr/bin/env python3
"""Import, protect, catalog, and stage public LaTeX papers."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dempa_site.catalog.metadata import rendered_keywords  # noqa: E402
from dempa_site.errors import PaperToolError  # noqa: E402
from dempa_site.features import feature_result_lines  # noqa: E402
from dempa_site.importing.paper import import_paper  # noqa: E402
from dempa_site.importing.pdf import import_pdf  # noqa: E402
from dempa_site.importing.tex import import_tex  # noqa: E402
from dempa_site.manifests.loader import load_manifest_directory  # noqa: E402
from dempa_site.manifests.model import Paper  # noqa: E402
from dempa_site.paths import (  # noqa: E402
    RepositoryPaths,
    safe_relative_path as shared_safe_relative_path,
)
from dempa_site.protection.approval import approve_changes  # noqa: E402
from dempa_site.protection.hashes import protected_file_errors  # noqa: E402
from dempa_site.protection.privacy import inspect_file  # noqa: E402
from dempa_site.site.links import local_link_errors  # noqa: E402
from dempa_site.site.rendering import rendered_home_page  # noqa: E402
from dempa_site.site.staging import stage_site  # noqa: E402
from tools.check_all import complete_check_steps, run_check_suite  # noqa: E402


PATHS = RepositoryPaths.from_environment("PAPER_REPO_ROOT", __file__)
ROOT = PATHS.root
PAPERS_DIR = PATHS.papers
INDEX_PATH = PATHS.index
PRIVACY_REVIEW_DIR = Path(
    os.environ.get("PAPER_PRIVACY_REVIEW_DIR", PATHS.privacy_review)
).resolve()


def safe_relative_path(value: str) -> Path:
    return shared_safe_relative_path(value, PaperToolError)


def manifests(slugs: Iterable[str] | None = None) -> list[tuple[Path, Paper]]:
    return load_manifest_directory(PAPERS_DIR, slugs, PaperToolError)


def verify_one(manifest_path: Path, manifest: Paper) -> list[str]:
    return protected_file_errors(manifest_path, manifest, PaperToolError)


def command_verify(args: argparse.Namespace) -> None:
    errors: list[str] = []
    selected = manifests(args.slugs)
    for manifest_path, manifest in selected:
        paper_errors = verify_one(manifest_path, manifest)
        errors.extend(paper_errors)
        if not paper_errors:
            print(f"OK  {manifest.slug}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"verification failed with {len(errors)} error(s)")


def command_audit(args: argparse.Namespace) -> None:
    selected = manifests(args.slugs)
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(verify_one(manifest_path, manifest))
        for entry in manifest.files:
            state = (
                "original"
                if entry.sha256 == entry.original_sha256
                else "approved-modified"
            )
            print(f"{state:17} {manifest.slug}/{entry.path}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"audit failed with {len(errors)} error(s)")


def rendered_index() -> str:
    return rendered_home_page(manifests())


def command_catalog(args: argparse.Namespace) -> None:
    rendered = rendered_index()
    current = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        stale_keywords: list[str] = []
        for manifest_path, manifest in manifests():
            target = manifest_path.parent / "keywords.txt"
            if not target.is_file() or target.read_text(encoding="utf-8") != rendered_keywords(manifest):
                stale_keywords.append(manifest["slug"])
        if rendered != current:
            raise PaperToolError("index.html is not synchronized with paper.json files")
        if stale_keywords:
            raise PaperToolError(
                "keywords.txt is not synchronized for: " + ", ".join(stale_keywords)
            )
        print("OK  index.html catalog")
        return
    INDEX_PATH.write_text(rendered, encoding="utf-8")
    for manifest_path, manifest in manifests():
        (manifest_path.parent / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
    print("WROTE index.html and keywords.txt files")


def command_build_roots(args: argparse.Namespace) -> None:
    """List only TeX roots whose manifests explicitly enable compilation."""
    for manifest_path, manifest in manifests():
        if not manifest.build.enabled:
            continue
        root = safe_relative_path(str(manifest.build.root))
        print((manifest_path.parent / root).relative_to(ROOT))


def command_check_links(args: argparse.Namespace) -> None:
    site_root = Path(args.site).resolve()
    if not site_root.is_dir():
        raise PaperToolError(f"site directory does not exist: {site_root}")
    errors = local_link_errors(site_root)
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"link check failed with {len(errors)} error(s)")
    print(f"OK  links in {site_root}")


def command_stage(args: argparse.Namespace) -> None:
    selected = manifests()
    output = Path(args.output).resolve()
    report = stage_site(PATHS, selected, output)
    print(f"STAGED {report.paper_count} papers in {report.destination}")
    for line in feature_result_lines(report.feature_results):
        print(line)


def command_check_all(args: argparse.Namespace) -> None:
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve()
    steps = complete_check_steps(PROJECT_ROOT, output)
    run_check_suite(steps, ROOT)


def command_inspect_file(args: argparse.Namespace) -> None:
    source = Path(args.file).expanduser().resolve()
    result = inspect_file(source, PRIVACY_REVIEW_DIR)
    print(f"PRIVACY REVIEW FILES: {result.output}")
    for finding in result.findings:
        print(f"WARN {finding}")
    print("MANUAL REVIEW REQUIRED before using --privacy-reviewed")


def command_import_tex(args: argparse.Namespace) -> None:
    result = import_tex(
        paths=PATHS,
        review_root=PRIVACY_REVIEW_DIR,
        tex_file=args.tex_file,
        title=args.title,
        published_at=args.published_at,
        sequence=args.sequence,
        original_url=args.original_url,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(result.message)


def command_import_pdf(args: argparse.Namespace) -> None:
    result = import_pdf(
        paths=PATHS,
        review_root=PRIVACY_REVIEW_DIR,
        pdf_file=args.pdf_file,
        title=args.title,
        published_at=args.published_at,
        sequence=args.sequence,
        original_url=args.original_url,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(result.message)


def command_import(args: argparse.Namespace) -> None:
    result = import_paper(
        paths=PATHS,
        review_root=PRIVACY_REVIEW_DIR,
        spec_file=args.spec,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(result.message)


def command_approve(args: argparse.Namespace) -> None:
    selected = manifests([args.slug])
    manifest_path, typed_manifest = selected[0]
    count = approve_changes(
        manifest_path,
        typed_manifest,
        PRIVACY_REVIEW_DIR,
        args.reason,
        args.files,
        args.privacy_reviewed,
        args.privacy_override,
    )
    print(f"APPROVED {count} explicitly requested change(s) for {args.slug}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Manage byte-protected LaTeX papers and the generated catalog."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="verify current approved hashes")
    verify_parser.add_argument("slugs", nargs="*")
    verify_parser.set_defaults(func=command_verify)

    audit_parser = subparsers.add_parser(
        "audit", help="show original versus explicitly approved file state"
    )
    audit_parser.add_argument("slugs", nargs="*")
    audit_parser.set_defaults(func=command_audit)

    catalog_parser = subparsers.add_parser("catalog", help="generate index.html cards")
    catalog_parser.add_argument("--check", action="store_true")
    catalog_parser.set_defaults(func=command_catalog)

    build_roots_parser = subparsers.add_parser(
        "build-roots", help="list manifest-approved TeX roots for CI compilation"
    )
    build_roots_parser.set_defaults(func=command_build_roots)

    stage_parser = subparsers.add_parser("stage", help="prepare the GitHub Pages directory")
    stage_parser.add_argument("output")
    stage_parser.set_defaults(func=command_stage)

    links_parser = subparsers.add_parser(
        "check-links", help="check local links in a staged site"
    )
    links_parser.add_argument("site")
    links_parser.set_defaults(func=command_check_links)

    check_all_parser = subparsers.add_parser(
        "check-all", help="run every routine check and prepare the local site"
    )
    check_all_parser.add_argument(
        "--output",
        default="_site",
        metavar="DIR",
        help="staged site directory (default: _site)",
    )
    check_all_parser.set_defaults(func=command_check_all)

    inspect_parser = subparsers.add_parser(
        "inspect-file", help="prepare a mandatory privacy review for a TeX or PDF file"
    )
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=command_inspect_file)

    import_parser = subparsers.add_parser(
        "import-paper", help="copy a new paper byte-for-byte from a JSON spec"
    )
    import_parser.add_argument("spec")
    import_parser.add_argument("--privacy-reviewed", action="store_true")
    import_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_parser.add_argument("--no-catalog", action="store_true")
    import_parser.set_defaults(func=command_import)

    import_tex_parser = subparsers.add_parser(
        "import-tex", help="create a source-only paper from one TeX file"
    )
    import_tex_parser.add_argument("tex_file")
    import_tex_parser.add_argument("--title")
    import_tex_parser.add_argument("--published-at")
    import_tex_parser.add_argument("--sequence", type=int)
    import_tex_parser.add_argument("--original-url")
    import_tex_parser.add_argument("--privacy-reviewed", action="store_true")
    import_tex_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_tex_parser.add_argument("--no-catalog", action="store_true")
    import_tex_parser.set_defaults(func=command_import_tex)

    import_pdf_parser = subparsers.add_parser(
        "import-pdf", help="create a paper from one published PDF file"
    )
    import_pdf_parser.add_argument("pdf_file")
    import_pdf_parser.add_argument("--title")
    import_pdf_parser.add_argument("--published-at")
    import_pdf_parser.add_argument("--sequence", type=int)
    import_pdf_parser.add_argument("--original-url")
    import_pdf_parser.add_argument("--privacy-reviewed", action="store_true")
    import_pdf_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_pdf_parser.add_argument("--no-catalog", action="store_true")
    import_pdf_parser.set_defaults(func=command_import_pdf)

    approve_parser = subparsers.add_parser(
        "approve-change", help="record an explicitly requested source-file change"
    )
    approve_parser.add_argument("slug")
    approve_parser.add_argument("--reason", required=True)
    approve_parser.add_argument("--file", dest="files", action="append", required=True)
    approve_privacy = approve_parser.add_mutually_exclusive_group()
    approve_privacy.add_argument("--privacy-reviewed", action="store_true")
    approve_privacy.add_argument(
        "--privacy-override", metavar="REASON", help="approve after an alternate review"
    )
    approve_parser.set_defaults(func=command_approve)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except PaperToolError as error:
        print(f"paper-tool: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
