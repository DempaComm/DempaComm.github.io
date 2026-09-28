"""Catalog command adapters; public CLI behavior is unchanged."""

from __future__ import annotations

import argparse
from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.catalog.writing import write_catalog
from dempa_site.errors import PaperToolError
from .context import CommandContext


def command_catalog(args: argparse.Namespace, context: CommandContext) -> None:
    rendered = context.rendered_index()
    current = context.paths.index.read_text(encoding="utf-8")
    if args.check:
        stale_keywords: list[str] = []
        for manifest_path, manifest in context.manifests():
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
    write_catalog(context.paths, context.manifests(), home_page=rendered)
    print("WROTE index.html and keywords.txt files")
