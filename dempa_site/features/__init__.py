"""Extension points for independently generated site features."""

from dempa_site.features.base import FunctionFeature, SiteFeature
from dempa_site.features.registry import configured_features
from dempa_site.features.runner import FeatureResult, run_site_features

__all__ = (
    "FeatureResult",
    "FunctionFeature",
    "SiteFeature",
    "configured_features",
    "run_site_features",
)
