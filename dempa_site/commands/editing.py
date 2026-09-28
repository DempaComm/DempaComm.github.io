"""Editing command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
from pathlib import Path
from dempa_site.errors import PaperToolError
from dempa_site.manifests.notes import NOTE_KINDS, record_note
from dempa_site.protection.approval import approve_changes
from dempa_site.protection.change_workflow import allowed_public_changes, changed_protected_files, review_changes, resumable_change_count, unexpected_public_differences
from dempa_site.site.snapshot import check_baseline, snapshot_differences, write_baseline
from tools.check_all import preflight_check_steps, run_check_suite
from .context import CommandContext


def command_add_note(args: argparse.Namespace, context: CommandContext) -> None:
    manifest_path, paper = context.manifests([args.slug])[0]
    entry = record_note(
        manifest_path,
        paper,
        kind=args.note_kind,
        summary=args.summary,
        anchor=args.anchor,
        recorded_at=args.recorded_at,
    )
    print(
        f"RECORDED {NOTE_KINDS[args.note_kind]} {args.slug} "
        f"date={entry['recorded_at'][:10]}"
    )
    print("NEXT python3 scripts/paper_tool.py stage _site")
    print("REVIEW _site, then: python3 scripts/site_snapshot.py write _site")
    print("FINAL python3 scripts/paper_tool.py check-all")


def command_approve(args: argparse.Namespace, context: CommandContext) -> None:
    selected = context.manifests([args.slug])
    manifest_path, typed_manifest = selected[0]
    count = approve_changes(
        manifest_path,
        typed_manifest,
        context.review_root,
        args.reason,
        args.files,
        args.privacy_reviewed,
        args.privacy_override,
    )
    print(f"APPROVED {count} explicitly requested change(s) for {args.slug}")


def command_review_change(args: argparse.Namespace, context: CommandContext) -> None:
    manifest_path, paper = context.manifests([args.slug])[0]
    reviewed = review_changes(
        manifest_path, paper, context.review_root, args.files
    )
    for result in reviewed:
        if result.report_directory is None:
            print(f"REVIEW {result.path}: automatic privacy inspection not required")
            continue
        print(f"PRIVACY REVIEW FILES: {result.report_directory}")
        for finding in result.findings:
            print(f"WARN {result.path}: {finding}")
    print("MANUAL REVIEW REQUIRED before using finish-change --privacy-reviewed")


def command_finish_change(args: argparse.Namespace, context: CommandContext) -> None:
    if not args.accept_public_change:
        raise PaperToolError(
            "finish-change requires --accept-public-change after reviewing the "
            "local PDF, source, and privacy report"
        )
    manifest_path, paper = context.manifests([args.slug])[0]
    allowed = allowed_public_changes(paper, args.files)
    if changed_protected_files(manifest_path, paper):
        count = approve_changes(
            manifest_path,
            paper,
            context.review_root,
            args.reason,
            args.files,
            args.privacy_reviewed,
            args.privacy_override,
        )
    else:
        resumed = resumable_change_count(paper, args.files, args.reason)
        if resumed is None:
            raise PaperToolError(
                "no unapproved hash changes and the latest approval does not match "
                "this finish-change request"
            )
        count = resumed
        print("RESUMING the latest matching approved change")
    output = Path(args.output)
    if not output.is_absolute():
        output = context.paths.root / output
    output = output.resolve()
    steps = preflight_check_steps(context.code_root, output)
    run_check_suite(steps, context.paths.root)

    baseline = context.paths.root / "tests" / "fixtures" / "site-baseline.json"
    differences = snapshot_differences(output, context.paths.papers, baseline)
    for difference in differences:
        print(f"PUBLIC {difference}")
    unexpected = unexpected_public_differences(differences, allowed)
    if unexpected:
        raise PaperToolError(
            "refusing to approve unrelated public differences: "
            + "; ".join(unexpected)
        )
    write_baseline(output, context.paths.papers, baseline)
    check_baseline(output, context.paths.papers, baseline)
    print(f"FINISHED {count} protected change(s) for {args.slug}")
    print("NEXT git status, then commit and push the intended files")
