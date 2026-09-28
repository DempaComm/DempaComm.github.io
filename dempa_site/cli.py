"""CLI construction and error presentation, separate from command handlers."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dempa_site.cli_parser import build_parser
from dempa_site.commands import build_commands
from dempa_site.commands.context import CommandContext
from dempa_site.errors import DempaSiteError
from dempa_site.paths import RepositoryPaths


def command_context() -> CommandContext:
    code_root = Path(__file__).resolve().parents[1]
    paths = RepositoryPaths.from_environment("PAPER_REPO_ROOT", str(code_root / "scripts/paper_tool.py"))
    review = Path(os.environ.get("PAPER_PRIVACY_REVIEW_DIR", paths.privacy_review)).resolve()
    return CommandContext(paths, code_root, review)


def parser() -> argparse.ArgumentParser:
    return build_parser(build_commands(command_context()))


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except DempaSiteError as error:
        print(f"paper-tool: {error}", file=sys.stderr)
        return 1
