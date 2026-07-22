"""Check links and fragments inside a generated local site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class LocalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)
        attribute = "href" if tag in {"a", "link"} else "src" if tag == "script" else ""
        if not attribute:
            return
        for key, value in attrs:
            if key == attribute and value:
                self.links.append(value)


def local_link_errors(site_root: Path) -> list[str]:
    errors: list[str] = []
    page_ids: dict[Path, set[str]] = {}
    resolved_root = site_root.resolve()
    for page in sorted(site_root.rglob("*.html")):
        parser = LocalLinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        page_ids[page.resolve()] = parser.ids
        for raw_link in parser.links:
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
                    target_parser = LocalLinkParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                    target_ids = target_parser.ids
                    page_ids[target] = target_ids
                fragment = unquote(parsed.fragment)
                if fragment not in target_ids:
                    errors.append(
                        f"{page.relative_to(site_root)}: missing fragment {raw_link}"
                    )
    return errors

