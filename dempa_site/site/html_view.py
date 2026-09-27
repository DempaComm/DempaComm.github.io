"""Adapt a public HTML copy without rewriting its protected source or MathML."""

from __future__ import annotations

from html.parser import HTMLParser
import re


class _PublicHTML(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0]
        self.line_offsets.extend(match.end() for match in re.finditer("\n", source))
        self.edits: list[tuple[int, int, str]] = []
        self.tables: list[bool] = []
        self.math: list[bool] = []
        self.heading_number = 0
        self.identifiers = set(re.findall(r'\bid=["\']([^"\']+)["\']', source))

    def source_offset(self) -> int:
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        raw = self.get_starttag_text()
        rewritten = raw
        if tag == "html":
            # The archive's manuscript prose is Japanese, including papers
            # whose titles are in English. The original files remain intact.
            rewritten = re.sub(r'''(?i)\s(?:xml:)?lang\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''', "", raw)
            rewritten = rewritten[:-1] + ' lang="ja">'
        if tag == "article" and "ltx_document" in classes:
            if "data-pagefind-body" not in attributes:
                rewritten = rewritten[:-1] + ' data-pagefind-body>'
        if classes & {"ltx_authors", "ltx_dates"}:
            if "data-pagefind-ignore" not in attributes:
                rewritten = rewritten[:-1] + ' data-pagefind-ignore>'
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and not attributes.get("id"):
            self.heading_number += 1
            identifier = f"dempa-heading-{self.heading_number}"
            while identifier in self.identifiers:
                self.heading_number += 1
                identifier = f"dempa-heading-{self.heading_number}"
            self.identifiers.add(identifier)
            rewritten = rewritten[:-1] + f' id="{identifier}">'
        start = self.source_offset()
        if rewritten != raw:
            self.edits.append((start, start + len(raw), rewritten))
        if tag == "table":
            wrap = not any(self.tables) and bool(
                classes & {"ltx_equation", "ltx_equationgroup", "ltx_tabular"}
            )
            self.tables.append(wrap)
            if wrap:
                self.edits.append((start, start, '<div class="math-scroll" tabindex="-1">'))
        if tag == "math":
            wrap = not any(self.tables)
            self.math.append(wrap)
            if wrap:
                inline = attributes.get("display") != "block"
                css = "math-scroll math-inline" if inline else "math-scroll"
                # A span preserves paragraph structure around inline MathML.
                # The reader script enables focus only when this region overflows.
                self.edits.append((start, start, f'<span class="{css}" tabindex="-1">'))

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            start = self.source_offset()
            self.edits.append((start, start, '<script src="/html-reader.js" defer></script>'))
        closing = ""
        if tag == "table" and self.tables and self.tables.pop():
            closing = "</div>"
        if tag == "math" and self.math and self.math.pop():
            closing = "</span>"
        if closing:
            end = self.source.index(">", self.source_offset()) + 1
            self.edits.append((end, end, closing))


def rendered_public_html(source: str) -> str:
    """Add language, search boundaries and scroll wrappers only to the export."""
    parser = _PublicHTML(source)
    parser.feed(source)
    parser.close()
    pieces: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(parser.edits, key=lambda item: (item[0], item[1])):
        pieces.extend((source[cursor:start], replacement))
        cursor = end
    pieces.append(source[cursor:])
    return "".join(pieces)
