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
from dempa_site.cli_parser import build_parser  # noqa: E402
from dempa_site.conversion.latexml import (  # noqa: E402
    run_latexml_trial,
    unconverted_tex_slugs,
)
from dempa_site.conversion.latexml_publication import (  # noqa: E402
    publish_latexml_trial,
)
from dempa_site.errors import DempaSiteError, PaperToolError  # noqa: E402
from dempa_site.features import feature_result_lines  # noqa: E402
from dempa_site.files import write_json  # noqa: E402
from dempa_site.importing.paper import import_paper  # noqa: E402
from dempa_site.importing.pdf import import_pdf  # noqa: E402
from dempa_site.importing.tex import import_tex  # noqa: E402
from dempa_site.manifests.loader import load_manifest_directory  # noqa: E402
from dempa_site.manifests.model import Paper  # noqa: E402
from dempa_site.paths import (  # noqa: E402
    RepositoryPaths,
    safe_relative_path as shared_safe_relative_path,
)
from dempa_site.paper_checks import check_paper  # noqa: E402
from dempa_site.protection.approval import approve_changes  # noqa: E402
from dempa_site.protection.change_workflow import (  # noqa: E402
    allowed_public_changes,
    changed_protected_files,
    review_changes,
    resumable_change_count,
    unexpected_public_differences,
)
from dempa_site.protection.hashes import protected_file_errors  # noqa: E402
from dempa_site.protection.privacy import inspect_file  # noqa: E402
from dempa_site.site.links import local_link_errors  # noqa: E402
from dempa_site.site.pagefind import build_pagefind_index  # noqa: E402
from dempa_site.site.rendering import rendered_home_page  # noqa: E402
from dempa_site.site.staging import stage_site  # noqa: E402
from dempa_site.site.snapshot import (  # noqa: E402
    check_baseline,
    snapshot_differences,
    write_baseline,
)
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
        if args.engine and manifest.build.effective_engine != args.engine:
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


def command_check_paper(args: argparse.Namespace) -> None:
    manifest_path, paper = manifests([args.slug])[0]
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


def command_pagefind_index(args: argparse.Namespace) -> None:
    site_root = Path(args.site)
    if not site_root.is_absolute():
        site_root = ROOT / site_root
    report = build_pagefind_index(site_root)
    print(
        f"PAGEFIND indexed={report.page_count} "
        f"bundle={report.bundle.relative_to(ROOT)}"
    )


def command_latexml_trial(args: argparse.Namespace) -> None:
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    report = run_latexml_trial(
        root=ROOT,
        papers=manifests(),
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


def command_publish_latexml(args: argparse.Namespace) -> None:
    if not args.reviewed:
        raise PaperToolError(
            "LaTeXML HTMLを目視確認してから --reviewed を付けてください"
        )
    selected = manifests([args.slug])
    paper = selected[0][1]
    trial = Path(args.trial)
    if not trial.is_absolute():
        trial = ROOT / trial
    publication = publish_latexml_trial(
        root=ROOT,
        paper=paper,
        trial_output=trial,
    )
    command_catalog(argparse.Namespace(check=False))
    print(
        f"PUBLISHED LATEXML {paper.slug} files={publication.file_count} "
        f"html={publication.html_path}"
    )


def command_latexml_batch(args: argparse.Namespace) -> None:
    selected = manifests()
    candidates, without_tex, already_converted = unconverted_tex_slugs(selected)
    if not candidates:
        raise PaperToolError("一括変換できる未変換TeX原稿がありません")
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output

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
        root=ROOT,
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
                root=ROOT,
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
        command_catalog(argparse.Namespace(check=False))
    blocked = len(report["results"]) - len(publications)
    print(
        f"LATEXML BATCH DONE published={len(publications)} blocked={blocked} "
        f"publication_failed={len(publication_failures)} report={output / 'report.json'}",
        flush=True,
    )


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


def command_review_change(args: argparse.Namespace) -> None:
    manifest_path, paper = manifests([args.slug])[0]
    reviewed = review_changes(
        manifest_path, paper, PRIVACY_REVIEW_DIR, args.files
    )
    for result in reviewed:
        if result.report_directory is None:
            print(f"REVIEW {result.path}: automatic privacy inspection not required")
            continue
        print(f"PRIVACY REVIEW FILES: {result.report_directory}")
        for finding in result.findings:
            print(f"WARN {result.path}: {finding}")
    print("MANUAL REVIEW REQUIRED before using finish-change --privacy-reviewed")


def command_finish_change(args: argparse.Namespace) -> None:
    if not args.accept_public_change:
        raise PaperToolError(
            "finish-change requires --accept-public-change after reviewing the "
            "local PDF, source, and privacy report"
        )
    manifest_path, paper = manifests([args.slug])[0]
    allowed = allowed_public_changes(paper, args.files)
    if changed_protected_files(manifest_path, paper):
        count = approve_changes(
            manifest_path,
            paper,
            PRIVACY_REVIEW_DIR,
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
        output = ROOT / output
    output = output.resolve()
    steps = complete_check_steps(PROJECT_ROOT, output)[:-1]
    run_check_suite(steps, ROOT)

    baseline = ROOT / "tests" / "fixtures" / "site-baseline.json"
    differences = snapshot_differences(output, PAPERS_DIR, baseline)
    for difference in differences:
        print(f"PUBLIC {difference}")
    unexpected = unexpected_public_differences(differences, allowed)
    if unexpected:
        raise PaperToolError(
            "refusing to approve unrelated public differences: "
            + "; ".join(unexpected)
        )
    write_baseline(output, PAPERS_DIR, baseline)
    check_baseline(output, PAPERS_DIR, baseline)
    print(f"FINISHED {count} protected change(s) for {args.slug}")
    print("NEXT git status, then commit and push the intended files")


COMMANDS = {
    "verify": command_verify,
    "audit": command_audit,
    "catalog": command_catalog,
    "build-roots": command_build_roots,
    "stage": command_stage,
    "check-links": command_check_links,
    "check-all": command_check_all,
    "check-paper": command_check_paper,
    "pagefind-index": command_pagefind_index,
    "latexml-trial": command_latexml_trial,
    "publish-latexml": command_publish_latexml,
    "latexml-batch": command_latexml_batch,
    "inspect-file": command_inspect_file,
    "import": command_import,
    "import-tex": command_import_tex,
    "import-pdf": command_import_pdf,
    "approve": command_approve,
    "review-change": command_review_change,
    "finish-change": command_finish_change,
}


def parser() -> argparse.ArgumentParser:
    return build_parser(COMMANDS)


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except DempaSiteError as error:
        print(f"paper-tool: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
