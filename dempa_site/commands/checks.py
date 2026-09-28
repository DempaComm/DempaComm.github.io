"""Checks command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dempa_site.build_selection import selected_build_papers
from dempa_site.errors import PaperToolError
from dempa_site.features import feature_result_lines
from dempa_site.paper_checks import check_paper
from dempa_site.site.links import local_link_errors
from dempa_site.site.pagefind import build_pagefind_index
from dempa_site.site.staging import stage_site
from tools.check_all import complete_check_steps, run_check_suite
from .context import CommandContext


def command_verify(args: argparse.Namespace, context: CommandContext) -> None:
    errors: list[str] = []
    selected = context.manifests(args.slugs)
    for manifest_path, manifest in selected:
        paper_errors = context.verify_one(manifest_path, manifest)
        errors.extend(paper_errors)
        if not paper_errors:
            print(f"OK  {manifest.slug}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"verification failed with {len(errors)} error(s)")


def command_audit(args: argparse.Namespace, context: CommandContext) -> None:
    selected = context.manifests(args.slugs)
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(context.verify_one(manifest_path, manifest))
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


def command_build_roots(args: argparse.Namespace, context: CommandContext) -> None:
    """List only TeX roots whose manifests explicitly enable compilation."""
    loaded = context.manifests()
    changed_paths = None
    if args.changed_files:
        changed_paths = Path(args.changed_files).read_text(encoding="utf-8").splitlines()
    selected = selected_build_papers(
        [manifest for _, manifest in loaded], changed_paths
    )
    paths = {manifest.slug: manifest_path for manifest_path, manifest in loaded}
    for manifest in selected:
        if args.engine and manifest.build.effective_engine != args.engine:
            continue
        root = context.safe_relative_path(str(manifest.build.root))
        print((paths[manifest.slug].parent / root).relative_to(context.paths.root))


def command_check_links(args: argparse.Namespace, context: CommandContext) -> None:
    site_root = Path(args.site).resolve()
    if not site_root.is_dir():
        raise PaperToolError(f"site directory does not exist: {site_root}")
    errors = local_link_errors(site_root)
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"link check failed with {len(errors)} error(s)")
    print(f"OK  links in {site_root}")


def command_stage(args: argparse.Namespace, context: CommandContext) -> None:
    selected = context.manifests()
    output = Path(args.output).resolve()
    report = stage_site(context.paths, selected, output)
    print(f"STAGED {report.paper_count} papers in {report.destination}")
    for line in feature_result_lines(report.feature_results):
        print(line)


def command_check_all(args: argparse.Namespace, context: CommandContext) -> None:
    output = Path(args.output)
    if not output.is_absolute():
        output = context.paths.root / output
    output = output.resolve()
    steps = complete_check_steps(context.code_root, output)
    run_check_suite(steps, context.paths.root)


def command_check_paper(args: argparse.Namespace, context: CommandContext) -> None:
    manifest_path, paper = context.manifests([args.slug])[0]
    report = check_paper(
        manifest_path,
        paper,
        build=not args.skip_build,
    )
    build_status = (
        f"built={report.engine}" if report.built else "built=not-required"
    )
    print(
        f"PAPER OK {report.slug} protected={report.protected_files} "
        f"privacy-receipts={report.privacy_receipts} {build_status}"
    )
    print("FAST CHECK ONLY: コミット前には check-all を実行してください")


def command_pagefind_index(args: argparse.Namespace, context: CommandContext) -> None:
    site_root = Path(args.site)
    if not site_root.is_absolute():
        site_root = context.paths.root / site_root
    report = build_pagefind_index(site_root)
    print(
        f"PAGEFIND indexed={report.page_count} "
        f"bundle={report.bundle.relative_to(context.paths.root)}"
    )
