"""Shared filesystem fixtures for command-line integration tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_TOOL = REPO_ROOT / "scripts" / "paper_tool.py"


def run_paper_tool(
    environment: dict[str, str], *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PAPER_TOOL), *arguments],
        check=check,
        capture_output=True,
        text=True,
        env=environment,
    )


def prepare_paper_repository(root: Path) -> dict[str, str]:
    (root / "papers").mkdir()
    (root / "index.html").write_text(
        "\n".join(
            [
                "<!-- GENERATED:PAPERS:START -->",
                "<!-- GENERATED:PAPERS:END -->",
                "<!-- GENERATED:TAGS:START -->",
                "<!-- GENERATED:TAGS:END -->",
                "<!-- GENERATED:YEARS:START -->",
                "<!-- GENERATED:YEARS:END -->",
            ]
        ),
        encoding="utf-8",
    )
    (root / "styles.css").write_text("/* fixture */\n", encoding="utf-8")
    (root / "search.js").write_text("// fixture\n", encoding="utf-8")
    for asset in (
        "favicon.ico",
        "favicon-16.png",
        "favicon-32.png",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "og-image.png",
    ):
        (root / asset).write_bytes(b"test image placeholder")
    (root / "site.webmanifest").write_text(
        '{"name":"Test","start_url":"/"}', encoding="utf-8"
    )
    return {**os.environ, "PAPER_REPO_ROOT": str(root)}


def add_privacy_review_receipt(root: Path, source: Path) -> None:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    review = root / ".privacy-review" / digest
    review.mkdir(parents=True, exist_ok=True)
    file_type = source.suffix.removeprefix(".")
    rendered_pages = ["page-1.png"] if file_type == "pdf" else []
    if rendered_pages:
        (review / rendered_pages[0]).write_bytes(b"test image placeholder")
    (review / "report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sha256": digest,
                "file_type": file_type,
                "manual_review_required": True,
                "rendered_pages": rendered_pages,
                "inspection_status": "completed",
            }
        ),
        encoding="utf-8",
    )
