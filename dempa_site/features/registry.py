"""Single registration point for features enabled in normal publication."""

from __future__ import annotations

from dempa_site.features.base import SiteFeature


# Add production feature instances here. Keeping this immutable makes the
# publication configuration explicit and avoids process-wide runtime changes.
SITE_FEATURES: tuple[SiteFeature, ...] = ()


def configured_features() -> tuple[SiteFeature, ...]:
    """Return the features used by the ordinary ``stage`` command."""
    return SITE_FEATURES
