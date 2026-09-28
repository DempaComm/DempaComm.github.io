"""Conversion command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
from pathlib import Path
from dempa_site.conversion.latexml import run_latexml_trial, unconverted_tex_slugs
from dempa_site.conversion.latexml_publication import publish_latexml_trial
from dempa_site.conversion.typst import run_typst_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import write_json
from .context import CommandContext
from .catalog import command_catalog


def command_latexml_trial(args: argparse.Namespace, context: CommandContext) -> None:
    output = Path(args.output)
    if not output.is_absolute():
        output = context.paths.root / output
    report = run_latexml_trial(
        root=context.paths.root,
        papers=context.manifests(),
        output=output,
        requested_slugs=args.slugs,
        timeout=args.timeout,
    )
    generated = sum(item["status"].startswith("generated") for item in report["results"])
    partial = sum(item["status"] == "partial" for item in report["results"])
    failed = sum(item["status"] == "failed" for item in report["results"])
    for item in report["results"]:
        print(f"LATEXML {item['status']:9} {item['slug']} {item['category']}")
    print(
        f"LATEXML generated={generated} partial={partial} failed={failed} "
        f"report={output / 'report.json'}"
    )
    print("MANUAL REVIEW REQUIRED: 試験出力は自動公開されません")


def command_typst_trial(args: argparse.Namespace, context: CommandContext) -> None:
    output = Path(args.output)
    if not output.is_absolute():
        output = context.paths.root / output
    report = run_typst_trial(
        root=context.paths.root,
        papers=context.manifests(),
        output=output,
        requested_slugs=args.slugs,
        timeout=args.timeout,
    )
    for item in report["results"]:
        statuses = " ".join(
            f"{result['converter']}={result['status']}"
            for result in item["converters"]
        )
        print(f"TYPST {item['slug']} {item['category']} {statuses}")
    print(f"TYPST report={output / 'report.json'}")
    print("MANUAL REVIEW REQUIRED: 試験出力は自動公開されません")


def command_publish_latexml(args: argparse.Namespace, context: CommandContext) -> None:
    if not args.reviewed:
        raise PaperToolError(
            "LaTeXML HTMLを目視確認してから --reviewed を付けてください"
        )
    selected = context.manifests([args.slug])
    paper = selected[0][1]
    trial = Path(args.trial)
    if not trial.is_absolute():
        trial = context.paths.root / trial
    publication = publish_latexml_trial(
        root=context.paths.root,
        paper=paper,
        trial_output=trial,
    )
    command_catalog(argparse.Namespace(check=False), context)
    print(
        f"PUBLISHED LATEXML {paper.slug} files={publication.file_count} "
        f"html={publication.html_path}"
    )


def command_latexml_batch(args: argparse.Namespace, context: CommandContext) -> None:
    selected = context.manifests()
    candidates, without_tex, already_converted = unconverted_tex_slugs(selected)
    if not candidates:
        raise PaperToolError("一括変換できる未変換TeX原稿がありません")
    output = Path(args.output)
    if not output.is_absolute():
        output = context.paths.root / output

    def show_progress(position: int, total: int, item: dict) -> None:
        print(
            f"LATEXML [{position:03}/{total:03}] {item['status']:23} {item['slug']}",
            flush=True,
        )

    print(
        f"LATEXML BATCH candidates={len(candidates)} without_tex={len(without_tex)} "
        f"already_converted={len(already_converted)}",
        flush=True,
    )
    report = run_latexml_trial(
        root=context.paths.root,
        papers=selected,
        output=output,
        requested_slugs=candidates,
        timeout=args.timeout,
        progress=show_progress,
    )
    publications = []
    publication_failures = []
    by_slug = {paper.slug: paper for _, paper in selected}
    for item in report["results"]:
        if not item["automatic_checks_passed"]:
            continue
        paper = by_slug[item["slug"]]
        try:
            publication = publish_latexml_trial(
                root=context.paths.root,
                paper=paper,
                trial_output=output,
                automatically_published=True,
            )
        except PaperToolError as error:
            publication_failures.append({"slug": paper.slug, "error": str(error)})
            print(f"PUBLISH failed {paper.slug}: {error}", flush=True)
            continue
        publications.append(paper.slug)
        print(f"PUBLISH automatic {paper.slug} files={publication.file_count}", flush=True)

    report["batch_publication"] = {
        "mode": "automatic-passing-only",
        "published": publications,
        "publication_failures": publication_failures,
        "skipped_without_tex": list(without_tex),
        "skipped_already_converted": list(already_converted),
    }
    write_json(output / "report.json", report)
    if publications:
        command_catalog(argparse.Namespace(check=False), context)
    blocked = len(report["results"]) - len(publications)
    print(
        f"LATEXML BATCH DONE published={len(publications)} blocked={blocked} "
        f"publication_failed={len(publication_failures)} report={output / 'report.json'}",
        flush=True,
    )
