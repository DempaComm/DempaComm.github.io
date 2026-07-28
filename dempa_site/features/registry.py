"""Single registration point for features enabled in normal publication."""

from __future__ import annotations

from dempa_site.features.base import FunctionFeature, SiteFeature
from dempa_site.features.explore import generate_explore
from dempa_site.features.lineage import generate_lineage
from dempa_site.features.reading_paths import (
    generate_reading_paths,
    validate_reading_paths,
)
from dempa_site.features.relation_graph import generate_relation_graph
from dempa_site.features.statements import generate_statements


# Add production feature instances here. Keeping this immutable makes the
# publication configuration explicit and avoids process-wide runtime changes.
SITE_FEATURES: tuple[SiteFeature, ...] = (
    FunctionFeature(
        name="reading-paths",
        generator=generate_reading_paths,
        validator=validate_reading_paths,
        required=True,
    ),
    FunctionFeature(
        name="lineage",
        generator=generate_lineage,
        required=True,
    ),
    FunctionFeature(
        name="relation-graph",
        generator=generate_relation_graph,
        required=True,
    ),
    FunctionFeature(
        name="explore",
        generator=generate_explore,
        required=True,
    ),
    FunctionFeature(
        name="statements",
        generator=generate_statements,
        required=True,
    ),
)


def configured_features() -> tuple[SiteFeature, ...]:
    """Return the features used by the ordinary ``stage`` command."""
    return SITE_FEATURES
