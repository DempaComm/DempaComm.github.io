"""Adapt a public HTML copy without rewriting its protected source or MathML."""

from __future__ import annotations

from html.parser import HTMLParser
from html import escape, unescape
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
        self.heading_id = ""
        self.heading_parts: list[str] = []
        self.heading_has_math = False
        self.heading_math_start: int | None = None
        self.heading_labels: dict[str, str] = {}
        self.head_end: int | None = None
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
            attributes["id"] = identifier
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_id = attributes["id"]
            self.heading_parts = []
            self.heading_has_math = False
        if tag == "math" and self.heading_id:
            self.heading_has_math = True
            self.heading_math_start = self.source_offset()
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
        if tag == "head":
            self.head_end = self.source_offset()
        if tag == "math" and self.heading_math_start is not None:
            end = self.source.index(">", self.source_offset()) + 1
            self.heading_parts.append(self.source[self.heading_math_start:end])
            self.heading_math_start = None
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.heading_id:
            if self.heading_has_math:
                self.heading_labels[self.heading_id] = "".join(self.heading_parts).strip()
            self.heading_id = ""
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

    def handle_data(self, data: str) -> None:
        if self.heading_id and self.heading_math_start is None:
            self.heading_parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(unescape(f"&#{name};"))


def rendered_public_html(source: str) -> str:
    """Add language, search boundaries and scroll wrappers only to the export."""
    parser = _PublicHTML(source)
    parser.feed(source)
    parser.close()
    # Pagefind's anchor labels omit MathML even when it indexes its text.
    # Carry text and original MathML as metadata. The search UI reconstructs only
    # an allowlist of MathML elements, never arbitrary HTML or nested links.
    if parser.head_end is not None and parser.heading_labels:
        labels = "".join(
            f'<meta data-pagefind-meta="heading_html_{escape(identifier, quote=True)}[content]" '
            f'content="{escape(label, quote=True)}">'
            for identifier, label in parser.heading_labels.items()
        )
        parser.edits.append((parser.head_end, parser.head_end, labels))
    pieces: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(parser.edits, key=lambda item: (item[0], item[1])):
        pieces.extend((source[cursor:start], replacement))
        cursor = end
    pieces.append(source[cursor:])
    return "".join(pieces)
