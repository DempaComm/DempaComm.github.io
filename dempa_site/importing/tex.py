"""Import a single TeX file as a source-only paper."""

from __future__ import annotations

import re
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.importing.common import ImportResult, create_single_file_paper
from dempa_site.paths import RepositoryPaths


def extracted_tex_title(source: str) -> str:
    """Extract a conservative plain-text title from a TeX title command."""
    match = re.search(r"\\title\s*\{", source)
    if not match:
        return ""
    start = match.end()
    depth = 1
    escaped = False
    end = start
    for end in range(start, len(source)):
        character = source[end]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                break
    if depth != 0:
        return ""
    title = source[start:end]
    previous = None
    while title != previous:
        previous = title
        title = re.sub(
            r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", title
        )
    title = re.sub(r"\\[A-Za-z@]+\*?", "", title)
    title = title.replace("~", " ").replace("{", "").replace("}", "")
    return " ".join(title.split()).strip()


def import_tex(
    *,
    paths: RepositoryPaths,
    review_root: Path,
    tex_file: str,
    title: str | None,
    published_at: str | None,
    sequence: int | None,
    original_url: str | None,
    privacy_reviewed: bool,
    privacy_override: str | None,
) -> ImportResult:
    source = Path(tex_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"TeX file does not exist: {source}")
    if source.suffix.casefold() != ".tex":
        raise PaperToolError(f"expected a .tex file: {source}")
    try:
        source_text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise PaperToolError(f"cannot read TeX file: {source}: {error}") from error
    resolved_title = (title or extracted_tex_title(source_text) or source.stem).strip()
    if not resolved_title:
        resolved_title = "無題のTeX原稿"
    result = create_single_file_paper(
        paths=paths,
        review_root=review_root,
        source=source,
        target_name="source.tex",
        role="manuscript",
        label="TeXソース",
        title=resolved_title,
        kind="TeX原稿",
        summary="TeX原稿を公開しています。",
        published_at=published_at,
        sequence=sequence,
        original_url=original_url,
        privacy_reviewed=privacy_reviewed,
        privacy_override=privacy_override,
    )
    return ImportResult(
        result.slug,
        f"IMPORTED {result.slug} as a source-only paper with byte-identical TeX",
    )

