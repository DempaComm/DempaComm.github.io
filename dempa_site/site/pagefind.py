"""Build and verify the static Pagefind bundle after staging the site."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from dempa_site.errors import PaperToolError


# Date-shaped canonical slugs exclude compatibility copies such as
# ``papers/infinitude-of-primes/`` from duplicate search results.
PAGEFIND_GLOB = "papers/20??-??-??-??/html/index.html"


@dataclass(frozen=True)
class PagefindReport:
    page_count: int
    bundle: Path


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def missing_bundle_parts(bundle: Path) -> tuple[str, ...]:
    """Return missing fixed files or generated-file groups in a Pagefind bundle."""
    fixed = (
        "pagefind.js",
        "pagefind-entry.json",
        "pagefind-worker.js",
        "wasm.unknown.pagefind",
    )
    missing = [name for name in fixed if not (bundle / name).is_file()]
    groups = (
        ("pagefind.*.pf_meta", tuple(bundle.glob("pagefind.*.pf_meta"))),
        ("index/*.pf_index", tuple((bundle / "index").glob("*.pf_index"))),
        ("fragment/*.pf_fragment", tuple((bundle / "fragment").glob("*.pf_fragment"))),
    )
    missing.extend(label for label, matches in groups if not matches)
    return tuple(missing)


def pagefind_command(
    site_root: Path,
    executable: Sequence[str] = (sys.executable, "-m", "pagefind"),
) -> tuple[str, ...]:
    return (
        *executable,
        "--site",
        str(site_root),
        "--output-subdir",
        "pagefind",
        "--glob",
        PAGEFIND_GLOB,
        "--force-language",
        "ja",
        "--quiet",
    )


def build_pagefind_index(
    site_root: Path,
    *,
    executable: Sequence[str] = (sys.executable, "-m", "pagefind"),
    run_command: CommandRunner = subprocess.run,
) -> PagefindReport:
    """Index primary LaTeXML HTML pages and require a complete bundle."""
    site_root = site_root.resolve()
    if not (site_root / "search" / "index.html").is_file():
        raise PaperToolError(
            f"Pagefind検索ページを含む公開サイトがありません: {site_root}"
        )
    pages = tuple(sorted(site_root.glob(PAGEFIND_GLOB)))
    if not pages:
        raise PaperToolError("Pagefindで索引できるLaTeXML HTML版がありません")

    bundle = site_root / "pagefind"
    if bundle.exists():
        shutil.rmtree(bundle)
    command = pagefind_command(site_root, executable)
    try:
        completed = run_command(
            command,
            cwd=site_root.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise PaperToolError(f"Pagefindを起動できません: {error}") from error
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        suffix = f"\n{details}" if details else ""
        raise PaperToolError(
            "Pagefind索引を生成できません。"
            " `python3 -m pip install --user -r requirements-pagefind.txt` を"
            f"実行してください。{suffix}"
        )
    missing = missing_bundle_parts(bundle)
    if missing:
        raise PaperToolError(
            "Pagefind索引の必須ファイルがありません: "
            + ", ".join(f"pagefind/{name}" for name in missing)
        )
    return PagefindReport(len(pages), bundle)
