"""Small, stable contract for optional site generators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from dempa_site.catalog.metadata import SiteCatalog


FeatureGenerator = Callable[[SiteCatalog, Path], None]
FeatureValidator = Callable[[SiteCatalog], None]


class SiteFeature(Protocol):
    """A feature that validates its inputs and writes derived site files."""

    name: str
    required: bool
    enabled: bool
    paper_slug: str

    def validate(self, catalog: SiteCatalog) -> None:
        """Raise an exception when this feature cannot use the catalog."""

    def generate(self, catalog: SiteCatalog, output: Path) -> None:
        """Write this feature's complete output below ``output``."""


@dataclass(frozen=True)
class FunctionFeature:
    """Adapt one or two plain functions to the :class:`SiteFeature` contract."""

    name: str
    generator: FeatureGenerator
    required: bool = False
    paper_slug: str = ""
    enabled: bool = True
    validator: FeatureValidator | None = None

    def validate(self, catalog: SiteCatalog) -> None:
        if self.validator is not None:
            self.validator(catalog)

    def generate(self, catalog: SiteCatalog, output: Path) -> None:
        self.generator(catalog, output)
