"""Importing command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
from dempa_site.importing.paper import import_paper
from dempa_site.importing.pdf import import_pdf
from dempa_site.importing.tex import import_tex
from .context import CommandContext
from .catalog import command_catalog


def command_import_tex(args: argparse.Namespace, context: CommandContext) -> None:
    result = import_tex(
        paths=context.paths,
        review_root=context.review_root,
        tex_file=args.tex_file,
        title=args.title,
        published_at=args.published_at,
        sequence=args.sequence,
        original_url=args.original_url,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False), context)
    print(result.message)


def command_import_pdf(args: argparse.Namespace, context: CommandContext) -> None:
    result = import_pdf(
        paths=context.paths,
        review_root=context.review_root,
        pdf_file=args.pdf_file,
        title=args.title,
        published_at=args.published_at,
        sequence=args.sequence,
        original_url=args.original_url,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False), context)
    print(result.message)


def command_import(args: argparse.Namespace, context: CommandContext) -> None:
    result = import_paper(
        paths=context.paths,
        review_root=context.review_root,
        spec_file=args.spec,
        privacy_reviewed=args.privacy_reviewed,
        privacy_override=args.privacy_override,
    )
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False), context)
    print(result.message)
