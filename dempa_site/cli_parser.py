"""Argument definitions for the stable ``paper_tool.py`` command line."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping

from dempa_site.config import LATEXMKRC_BY_ENGINE


def build_parser(
    commands: Mapping[str, Callable[[argparse.Namespace], None]],
) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Manage byte-protected LaTeX papers and the generated catalog."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="verify current approved hashes")
    verify_parser.add_argument("slugs", nargs="*")
    verify_parser.set_defaults(func=commands["verify"])

    audit_parser = subparsers.add_parser(
        "audit", help="show original versus explicitly approved file state"
    )
    audit_parser.add_argument("slugs", nargs="*")
    audit_parser.set_defaults(func=commands["audit"])

    catalog_parser = subparsers.add_parser("catalog", help="generate index.html cards")
    catalog_parser.add_argument("--check", action="store_true")
    catalog_parser.set_defaults(func=commands["catalog"])

    build_roots_parser = subparsers.add_parser(
        "build-roots", help="list manifest-approved TeX roots for CI compilation"
    )
    build_roots_parser.add_argument(
        "--engine",
        choices=sorted(LATEXMKRC_BY_ENGINE),
        help="list only roots using this effective TeX engine",
    )
    build_roots_parser.set_defaults(func=commands["build-roots"])

    stage_parser = subparsers.add_parser("stage", help="prepare the GitHub Pages directory")
    stage_parser.add_argument("output")
    stage_parser.set_defaults(func=commands["stage"])

    links_parser = subparsers.add_parser(
        "check-links", help="check local links in a staged site"
    )
    links_parser.add_argument("site")
    links_parser.set_defaults(func=commands["check-links"])

    check_all_parser = subparsers.add_parser(
        "check-all", help="run every routine check and prepare the local site"
    )
    check_all_parser.add_argument(
        "--output",
        default="_site",
        metavar="DIR",
        help="staged site directory (default: _site)",
    )
    check_all_parser.set_defaults(func=commands["check-all"])

    check_paper_parser = subparsers.add_parser(
        "check-paper",
        help="quickly check one approved paper during editing",
    )
    check_paper_parser.add_argument("slug", help="paper slug")
    check_paper_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="skip latexmk even when this paper enables automatic building",
    )
    check_paper_parser.set_defaults(func=commands["check-paper"])

    pagefind_parser = subparsers.add_parser(
        "pagefind-index",
        help="build the Japanese full-text index for a staged site",
    )
    pagefind_parser.add_argument("site", help="staged site directory")
    pagefind_parser.set_defaults(func=commands["pagefind-index"])

    latexml_parser = subparsers.add_parser(
        "latexml-trial",
        help="experimentally convert selected TeX papers to HTML with LaTeXML",
    )
    latexml_parser.add_argument(
        "slugs",
        nargs="*",
        help="paper slugs; omit to use experiments/latexml-trial.json",
    )
    latexml_parser.add_argument(
        "--output",
        default="_experiments/latexml",
        metavar="DIR",
        help="empty trial output directory (default: _experiments/latexml)",
    )
    latexml_parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        metavar="SECONDS",
        help="per-paper LaTeXML timeout (default: 180)",
    )
    latexml_parser.set_defaults(func=commands["latexml-trial"])

    publish_latexml_parser = subparsers.add_parser(
        "publish-latexml",
        help="promote a manually reviewed LaTeXML trial to public paper files",
    )
    publish_latexml_parser.add_argument("slug", help="paper slug")
    publish_latexml_parser.add_argument(
        "--trial",
        required=True,
        metavar="DIR",
        help="LaTeXML trial output containing report.json",
    )
    publish_latexml_parser.add_argument(
        "--reviewed",
        action="store_true",
        help="confirm that the HTML was compared with the PDF and approved",
    )
    publish_latexml_parser.set_defaults(func=commands["publish-latexml"])

    batch_parser = subparsers.add_parser(
        "latexml-batch",
        help="convert every unconverted TeX paper and publish automatic passes",
    )
    batch_parser.add_argument(
        "--output",
        default="_experiments/latexml-all",
        metavar="DIR",
        help="empty batch output directory (default: _experiments/latexml-all)",
    )
    batch_parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        metavar="SECONDS",
        help="per-paper LaTeXML timeout (default: 180)",
    )
    batch_parser.set_defaults(func=commands["latexml-batch"])

    inspect_parser = subparsers.add_parser(
        "inspect-file", help="prepare a mandatory privacy review for a TeX or PDF file"
    )
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=commands["inspect-file"])

    import_parser = subparsers.add_parser(
        "import-paper", help="copy a new paper byte-for-byte from a JSON spec"
    )
    import_parser.add_argument("spec")
    import_parser.add_argument("--privacy-reviewed", action="store_true")
    import_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_parser.add_argument("--no-catalog", action="store_true")
    import_parser.set_defaults(func=commands["import"])

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
    import_tex_parser.set_defaults(func=commands["import-tex"])

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
    import_pdf_parser.set_defaults(func=commands["import-pdf"])

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
    approve_parser.set_defaults(func=commands["approve"])

    review_change_parser = subparsers.add_parser(
        "review-change",
        help="inspect changed protected files before final approval",
    )
    review_change_parser.add_argument("slug")
    review_change_parser.add_argument(
        "--file", dest="files", action="append", required=True
    )
    review_change_parser.set_defaults(func=commands["review-change"])

    finish_change_parser = subparsers.add_parser(
        "finish-change",
        help="approve a reviewed change, run checks, and update the public baseline",
    )
    finish_change_parser.add_argument("slug")
    finish_change_parser.add_argument("--reason", required=True)
    finish_change_parser.add_argument(
        "--file", dest="files", action="append", required=True
    )
    finish_privacy = finish_change_parser.add_mutually_exclusive_group()
    finish_privacy.add_argument("--privacy-reviewed", action="store_true")
    finish_privacy.add_argument("--privacy-override", metavar="REASON")
    finish_change_parser.add_argument(
        "--accept-public-change",
        action="store_true",
        help="accept only public paths belonging to the requested paper and files",
    )
    finish_change_parser.add_argument(
        "--output", default="_site", metavar="DIR"
    )
    finish_change_parser.set_defaults(func=commands["finish-change"])
    return result
