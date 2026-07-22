"""Transactional, independently testable stages for publishing the static site."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from dempa_site.catalog.metadata import (
    PaperSource,
    SiteCatalog,
    collect_metadata,
    rendered_keywords,
)
from dempa_site.config import MATH_SECTION_DETAILS, SITE_URL
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.paths import RepositoryPaths, safe_relative_path
from dempa_site.site.cards import has_pdf
from dempa_site.site.feeds import rendered_feed
from dempa_site.site.links import local_link_errors
from dempa_site.site.rendering import (
    rendered_archive_page,
    rendered_home_page,
    rendered_math_page,
    rendered_math_section_page,
    rendered_not_found_page,
    rendered_paper_page,
    rendered_tag_page,
)
from dempa_site.site.sitemap import rendered_sitemap


STATIC_ASSETS = (
    "favicon.ico",
    "favicon-16.png",
    "favicon-32.png",
    "apple-touch-icon.png",
    "icon-192.png",
    "icon-512.png",
    "og-image.png",
    "site.webmanifest",
)


FeatureGenerator = Callable[[SiteCatalog, Path], None]


@dataclass(frozen=True)
class StageFeature:
    """An isolated additional generator whose output is merged on success."""

    name: str
    generate: FeatureGenerator
    required: bool = False
    paper_slug: str = ""


@dataclass(frozen=True)
class FeatureResult:
    name: str
    required: bool
    paper_slug: str
    status: str
    error: str = ""


@dataclass
class StageContext:
    paths: RepositoryPaths
    destination: Path
    working_output: Path
    catalog: SiteCatalog
    feature_results: list[FeatureResult] = field(default_factory=list)


@dataclass(frozen=True)
class StageReport:
    destination: Path
    paper_count: int
    feature_results: tuple[FeatureResult, ...]


def validate_stage_sources(
    paths: RepositoryPaths, selected: list[PaperSource]
) -> None:
    """Reject changed protected files and stale generated catalog metadata."""
    errors: list[str] = []
    for manifest_path, paper in selected:
        source_dir = manifest_path.parent
        for entry in paper.files:
            relative = safe_relative_path(entry.path, PaperToolError)
            target = source_dir / relative
            if not target.is_file():
                errors.append(f"{paper.slug}/{relative}: missing")
                continue
            actual = sha256_file(target)
            if actual != entry.sha256:
                errors.append(
                    f"{paper.slug}/{relative}: SHA-256 mismatch "
                    f"(expected {entry.sha256}, got {actual})"
                )
    if errors:
        details = "\n".join(f"ERR {error}" for error in errors)
        raise PaperToolError(
            "refusing to stage files that failed verification\n" + details
        )

    if rendered_home_page(selected) != paths.index.read_text(encoding="utf-8"):
        raise PaperToolError("refusing to stage a stale index.html")
    for manifest_path, paper in selected:
        keyword_path = manifest_path.parent / "keywords.txt"
        if (
            not keyword_path.is_file()
            or keyword_path.read_text(encoding="utf-8") != rendered_keywords(paper)
        ):
            raise PaperToolError(
                f"refusing to stage stale keywords.txt for {paper.slug}"
            )


def generate_static_pages(context: StageContext) -> None:
    """Generate the basic HTML pages without copying public source files."""
    output = context.working_output
    selected = context.catalog.selected
    shutil.copy2(context.paths.index, output / "index.html")

    archive_dir = output / "archive"
    archive_dir.mkdir()
    (archive_dir / "index.html").write_text(
        rendered_archive_page(selected), encoding="utf-8"
    )
    (output / "404.html").write_text(rendered_not_found_page(), encoding="utf-8")

    for _, paper in selected:
        target_dir = output / "papers" / paper.slug
        target_dir.mkdir(parents=True)
        (target_dir / "index.html").write_text(
            rendered_paper_page(paper), encoding="utf-8"
        )

    for tag, papers in context.catalog.tags.items():
        if tag in {".", ".."} or "/" in tag or "\0" in tag:
            raise PaperToolError(f"tag cannot be used as a page path: {tag!r}")
        tag_dir = output / "tags" / tag
        tag_dir.mkdir(parents=True)
        (tag_dir / "index.html").write_text(
            rendered_tag_page(tag, papers), encoding="utf-8"
        )

    math_dir = output / "math"
    math_dir.mkdir()
    (math_dir / "index.html").write_text(
        rendered_math_page(selected), encoding="utf-8"
    )
    for section, papers in context.catalog.math_sections.items():
        section_dir = math_dir / str(MATH_SECTION_DETAILS[section]["slug"])
        section_dir.mkdir()
        (section_dir / "index.html").write_text(
            rendered_math_section_page(section, papers), encoding="utf-8"
        )


def copy_public_files(context: StageContext) -> None:
    """Copy site assets, protected public files, PDFs, and compatibility routes."""
    output = context.working_output
    root = context.paths.root
    shutil.copy2(root / "styles.css", output / "styles.css")
    shutil.copy2(context.paths.search_script, output / "search.js")
    for asset in STATIC_ASSETS:
        shutil.copy2(root / asset, output / asset)

    for manifest_path, paper in context.catalog.selected:
        source_dir = manifest_path.parent
        target_dir = output / "papers" / paper.slug
        shutil.copy2(manifest_path, target_dir / "paper.json")
        shutil.copy2(source_dir / "keywords.txt", target_dir / "keywords.txt")
        readme = source_dir / "README.md"
        if readme.is_file():
            shutil.copy2(readme, target_dir / "README.md")
        for entry in paper.files:
            if not entry.public:
                continue
            relative = safe_relative_path(entry.path, PaperToolError)
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / relative, target)
        if paper.build.enabled:
            pdf = source_dir / "main.pdf"
            if not pdf.is_file():
                raise PaperToolError(f"generated PDF is missing: {pdf}")
            shutil.copy2(pdf, target_dir / "main.pdf")
        elif has_pdf(paper):
            shutil.copy2(source_dir / "published.pdf", target_dir / "main.pdf")

        for legacy_slug in paper.legacy_slugs:
            legacy_dir = output / "papers" / legacy_slug
            if legacy_dir.exists():
                raise PaperToolError(f"legacy slug collision: {legacy_slug}")
            shutil.copytree(target_dir, legacy_dir)


def generate_discovery_files(context: StageContext) -> None:
    """Generate RSS, sitemap, and crawler instructions."""
    output = context.working_output
    selected = context.catalog.selected
    (output / "feed.xml").write_text(rendered_feed(selected), encoding="utf-8")
    (output / "sitemap.xml").write_text(
        rendered_sitemap(selected), encoding="utf-8"
    )
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def _merge_feature_output(source: Path, destination: Path) -> None:
    files = [path for path in source.rglob("*") if path.is_file()]
    collisions = [
        path.relative_to(source)
        for path in files
        if (destination / path.relative_to(source)).exists()
    ]
    if collisions:
        raise PaperToolError(
            "feature output must not replace basic site files: "
            + ", ".join(str(path) for path in collisions)
        )
    copied: list[Path] = []
    try:
        for source_file in files:
            relative = source_file.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
            copied.append(target)
    except Exception:
        for target in reversed(copied):
            target.unlink(missing_ok=True)
        raise


def generate_additional_features(
    context: StageContext, features: Iterable[StageFeature]
) -> None:
    """Run each feature in isolation and record required/optional outcomes."""
    for feature in features:
        scratch = Path(
            tempfile.mkdtemp(
                prefix=f".{context.destination.name}.{feature.name}-",
                dir=context.working_output.parent,
            )
        )
        try:
            feature.generate(context.catalog, scratch)
            _merge_feature_output(scratch, context.working_output)
        except Exception as error:
            result = FeatureResult(
                name=feature.name,
                required=feature.required,
                paper_slug=feature.paper_slug,
                status="failed",
                error=str(error),
            )
            context.feature_results.append(result)
            if feature.required:
                raise PaperToolError(
                    f"required site feature failed: {feature.name}: {error}"
                ) from error
        else:
            context.feature_results.append(
                FeatureResult(
                    name=feature.name,
                    required=feature.required,
                    paper_slug=feature.paper_slug,
                    status="generated",
                )
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


def check_generated_links(context: StageContext) -> None:
    errors = local_link_errors(context.working_output)
    if errors:
        details = "\n".join(f"ERR {error}" for error in errors)
        raise PaperToolError(
            f"refusing to publish a site with {len(errors)} broken link(s)\n{details}"
        )


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def promote_staged_site(working_output: Path, destination: Path) -> None:
    """Replace the completed destination, restoring the old site on failure."""
    backup = destination.with_name(
        f".{destination.name}.backup-{uuid.uuid4().hex}"
    )
    had_destination = destination.exists()
    if had_destination:
        destination.rename(backup)
    try:
        working_output.rename(destination)
    except Exception:
        if had_destination and backup.exists():
            backup.rename(destination)
        raise
    else:
        if backup.exists():
            try:
                _remove_path(backup)
            except OSError:
                # The completed destination is already active; a stale hidden
                # backup is safer than reporting a false publication failure.
                pass


def stage_site(
    paths: RepositoryPaths,
    selected: list[PaperSource],
    destination: Path,
    features: Iterable[StageFeature] = (),
) -> StageReport:
    """Run the complete publication pipeline and adopt only a complete site."""
    destination = destination.resolve()
    root = paths.root.resolve()
    if destination == root or destination in root.parents:
        raise PaperToolError(
            "stage output must not be the repository or one of its parents"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)

    validate_stage_sources(paths, selected)
    catalog = collect_metadata(selected)
    working_output = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.stage-", dir=destination.parent
        )
    )
    context = StageContext(paths, destination, working_output, catalog)
    try:
        generate_static_pages(context)
        copy_public_files(context)
        generate_discovery_files(context)
        generate_additional_features(context, features)
        check_generated_links(context)
        promote_staged_site(working_output, destination)
    except Exception:
        shutil.rmtree(working_output, ignore_errors=True)
        raise
    return StageReport(
        destination=destination,
        paper_count=len(selected),
        feature_results=tuple(context.feature_results),
    )
