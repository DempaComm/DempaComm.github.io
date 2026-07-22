"""Isolated execution and integration of additional site features."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.errors import PaperToolError
from dempa_site.features.base import SiteFeature


@dataclass(frozen=True)
class FeatureResult:
    """Outcome of one registered feature in a publication run."""

    name: str
    required: bool
    paper_slug: str
    status: str
    error: str = ""
    phase: str = ""


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


def _failure_result(
    feature: SiteFeature, error: Exception, phase: str
) -> FeatureResult:
    return FeatureResult(
        name=feature.name,
        required=feature.required,
        paper_slug=feature.paper_slug,
        status="failed",
        error=str(error),
        phase=phase,
    )


def _raise_if_required(feature: SiteFeature, error: Exception) -> None:
    if feature.required:
        raise PaperToolError(
            f"required site feature failed: {feature.name}: {error}"
        ) from error


def run_site_features(
    catalog: SiteCatalog,
    site_output: Path,
    scratch_parent: Path,
    features: Iterable[SiteFeature],
) -> list[FeatureResult]:
    """Run enabled features independently and merge only complete outputs."""
    results: list[FeatureResult] = []
    for feature in features:
        if not feature.enabled:
            results.append(
                FeatureResult(
                    name=feature.name,
                    required=feature.required,
                    paper_slug=feature.paper_slug,
                    status="disabled",
                )
            )
            continue

        try:
            feature.validate(catalog)
        except Exception as error:
            results.append(_failure_result(feature, error, "validation"))
            _raise_if_required(feature, error)
            continue

        scratch: Path | None = None
        try:
            scratch = Path(
                tempfile.mkdtemp(
                    prefix=f".{site_output.name}.{feature.name}-",
                    dir=scratch_parent,
                )
            )
            feature.generate(catalog, scratch)
            _merge_feature_output(scratch, site_output)
        except Exception as error:
            results.append(_failure_result(feature, error, "generation"))
            _raise_if_required(feature, error)
        else:
            results.append(
                FeatureResult(
                    name=feature.name,
                    required=feature.required,
                    paper_slug=feature.paper_slug,
                    status="generated",
                    phase="generation",
                )
            )
        finally:
            if scratch is not None:
                shutil.rmtree(scratch, ignore_errors=True)
    return results
