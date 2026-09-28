"""Maintenance command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
from pathlib import Path
from dempa_site.maintenance import apply_local_cleanup, human_bytes, local_cleanup_plan
from dempa_site.local_admin import serve_local_admin
from dempa_site.protection.privacy import inspect_file
from .context import CommandContext


def command_inspect_file(args: argparse.Namespace, context: CommandContext) -> None:
    source = Path(args.file).expanduser().resolve()
    result = inspect_file(source, context.review_root)
    print(f"PRIVACY REVIEW FILES: {result.output}")
    for finding in result.findings:
        print(f"WARN {finding}")
    print("MANUAL REVIEW REQUIRED before using --privacy-reviewed")


def command_clean_local(args: argparse.Namespace, context: CommandContext) -> None:
    plan = local_cleanup_plan(
        context.paths.root,
        (paper for _, paper in context.manifests()),
        include_experiments=args.include_experiments,
    )
    if not plan.groups:
        print("CLEAN LOCAL: cleanup candidates were not found")
        return
    for group in plan.groups:
        print(
            f"CLEAN {group.name}: paths={len(group.paths)} "
            f"size={human_bytes(group.bytes)}"
        )
    print(f"CLEAN TOTAL: paths={plan.path_count} size={human_bytes(plan.bytes)}")
    if not args.apply:
        print("DRY RUN: add --apply to remove these generated files")
        return
    apply_local_cleanup(plan)
    print("CLEAN LOCAL DONE")


def command_local_admin(args: argparse.Namespace, context: CommandContext) -> None:
    serve_local_admin(context.paths.root, host=args.host, port=args.port)
