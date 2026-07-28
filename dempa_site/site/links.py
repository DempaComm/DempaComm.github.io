"""Check links and fragments inside a generated local site."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


_VALUE = r'''(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s"'=<>`]+))'''
_ID_RE = re.compile(r"(?is)<[^>]*?\bid\s*=\s*" + _VALUE)
_LINK_TAG_RE = re.compile(r"(?is)<(?P<tag>a|link|script)\b(?P<attrs>[^>]*)>")
_HREF_RE = re.compile(r"(?is)\bhref\s*=\s*" + _VALUE)
_SRC_RE = re.compile(r"(?is)\bsrc\s*=\s*" + _VALUE)


def _matched_value(match: re.Match[str]) -> str:
    return html.unescape(
        match.group("double") or match.group("single") or match.group("bare") or ""
    )


def scanned_links_and_ids(source: str) -> tuple[list[str], set[str]]:
    """Extract only the attributes needed by local publication checks."""
    ids = {_matched_value(match) for match in _ID_RE.finditer(source)}
    ids.discard("")
    links: list[str] = []
    for tag_match in _LINK_TAG_RE.finditer(source):
        attribute_re = _SRC_RE if tag_match.group("tag").casefold() == "script" else _HREF_RE
        attribute = attribute_re.search(tag_match.group("attrs"))
        if attribute is not None:
            value = _matched_value(attribute)
            if value:
                links.append(value)
    return links, ids


def local_link_errors(site_root: Path) -> list[str]:
    errors: list[str] = []
    page_ids: dict[Path, set[str]] = {}
    resolved_root = site_root.resolve()
    for page in sorted(site_root.rglob("*.html")):
        links, ids = scanned_links_and_ids(page.read_text(encoding="utf-8"))
        page_ids[page.resolve()] = ids
        for raw_link in links:
            parsed = urlsplit(raw_link)
            if parsed.scheme or parsed.netloc or raw_link.startswith(("mailto:", "tel:")):
                continue
            decoded_path = unquote(parsed.path)
            if not decoded_path:
                target = page
            elif decoded_path.startswith("/"):
                target = site_root / decoded_path.lstrip("/")
            else:
                target = page.parent / decoded_path
            if decoded_path.endswith("/"):
                target /= "index.html"
            target = target.resolve()
            try:
                target.relative_to(resolved_root)
            except ValueError:
                errors.append(f"{page.relative_to(site_root)}: unsafe link {raw_link}")
                continue
            if not target.is_file():
                errors.append(
                    f"{page.relative_to(site_root)}: missing target {raw_link}"
                )
                continue
            if parsed.fragment and target.suffix.casefold() == ".html":
                target_ids = page_ids.get(target)
                if target_ids is None:
                    _, target_ids = scanned_links_and_ids(
                        target.read_text(encoding="utf-8")
                    )
                    page_ids[target] = target_ids
                fragment = unquote(parsed.fragment)
                if fragment not in target_ids:
                    errors.append(
                        f"{page.relative_to(site_root)}: missing fragment {raw_link}"
                    )
    return errors
