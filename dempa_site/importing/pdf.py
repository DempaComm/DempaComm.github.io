"""Import a single finished PDF as a protected PDF-only paper."""

from __future__ import annotations

from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.importing.common import ImportResult, create_single_file_paper
from dempa_site.paths import RepositoryPaths


def import_pdf(
    *,
    paths: RepositoryPaths,
    review_root: Path,
    pdf_file: str,
    title: str | None,
    published_at: str | None,
    sequence: int | None,
    original_url: str | None,
    privacy_reviewed: bool,
    privacy_override: str | None,
) -> ImportResult:
    source = Path(pdf_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"PDF file does not exist: {source}")
    if source.suffix.casefold() != ".pdf":
        raise PaperToolError(f"expected a .pdf file: {source}")
    try:
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PaperToolError(f"file does not have a PDF header: {source}")
    except OSError as error:
        raise PaperToolError(f"cannot read PDF file: {source}: {error}") from error
    resolved_title = (title or source.stem).strip() or "無題のPDF原稿"
    result = create_single_file_paper(
        paths=paths,
        review_root=review_root,
        source=source,
        target_name="published.pdf",
        role="published-pdf",
        label="",
        title=resolved_title,
        kind="PDF原稿",
        summary="PDF原稿を公開しています。",
        published_at=published_at,
        sequence=sequence,
        original_url=original_url,
        privacy_reviewed=privacy_reviewed,
        privacy_override=privacy_override,
    )
    return ImportResult(
        result.slug,
        f"IMPORTED {result.slug} with a byte-identical published PDF",
    )

