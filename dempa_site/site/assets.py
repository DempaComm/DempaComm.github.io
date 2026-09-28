"""Deterministic public assets; source file layout does not change public URLs."""
from pathlib import Path
import shutil

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

STYLE_PARTS = ('00-base.css', '10-catalog.css', '20-exploration.css', '30-reader.css', '40-search.css', '50-responsive.css')
ROOT_SCRIPTS = ("search.js", "full-text-search.js", "statements.js")
PACKAGE_SCRIPTS = {
    "html-reader.js": "html_reader.js",
    "discovery.js": "discovery.js",
    "search-engine.js": "search_engine.js",
    "search-results.js": "search_results.js",
}


def stylesheet_bytes(root: Path) -> bytes:
    """Keep the established cascade order, including whitespace between rules."""
    return b"".join((root / "assets" / "styles" / name).read_bytes() for name in STYLE_PARTS)


def copy_site_assets(root: Path, output: Path) -> None:
    (output / "styles.css").write_bytes(stylesheet_bytes(root))
    for name in (*ROOT_SCRIPTS, *STATIC_ASSETS):
        shutil.copy2(root / name, output / name)
    for name, source in PACKAGE_SCRIPTS.items():
        shutil.copy2(Path(__file__).with_name(source), output / name)
