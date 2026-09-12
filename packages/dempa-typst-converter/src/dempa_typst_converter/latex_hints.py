"""Extract conservative statement-title hints from an original LaTeX source."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StatementHint:
    kind: str
    title: str | None


@dataclass(frozen=True)
class EquationNumberingHint:
    has_numbered_display: bool
    has_unnumbered_display: bool


@dataclass(frozen=True)
class DescriptionItemHint:
    text_fragments: tuple[str, ...]


_KINDS = {
    "df": "df",
    "prop": "prop",
    "thm": "thm",
    "lem": "lem",
    "lemma": "lem",
    "cor": "cor",
    "fact": "fact",
    "exam": "exam",
}


def _document_content(source: str) -> str:
    document = source.split(r"\end{document}", 1)[0]
    document = re.sub(
        r"\\begin\{comment\}.*?\\end\{comment\}", "", document, flags=re.DOTALL
    )
    return re.sub(r"(?m)(?<!\\)%.*$", "", document)


def extract_statement_hints(source: str) -> tuple[StatementHint, ...]:
    """Read environment kinds and optional titles without changing the LaTeX source."""
    document = _document_content(source)
    pattern = re.compile(
        r"\\begin\{(?P<kind>df|prop|thm|lem|lemma|cor|fact|exam)\}"
        r"(?:\[(?P<title>[^\]\r\n]*)\])?"
    )
    return tuple(
        StatementHint(
            kind=_KINDS[match.group("kind")],
            title=(match.group("title") or "").strip() or None,
        )
        for match in pattern.finditer(document)
    )


def extract_equation_numbering_hint(source: str) -> EquationNumberingHint:
    """Classify explicit numbered and unnumbered display math conservatively."""
    document = _document_content(source)
    numbered = re.search(
        r"\\begin\{(?:equation|align|gather|multline|eqnarray)\}", document
    )
    unnumbered = re.search(
        r"\\\[|\\begin\{(?:equation|align|gather|multline|eqnarray)\*\}",
        document,
    )
    return EquationNumberingHint(
        has_numbered_display=numbered is not None,
        has_unnumbered_display=unnumbered is not None,
    )


def extract_description_item_hints(
    source: str,
) -> tuple[DescriptionItemHint, ...]:
    """Read verifiable description labels with an explicit empty line break."""
    document = _document_content(source)
    environments = re.finditer(
        r"\\begin\{description\}(?P<body>.*?)\\end\{description\}",
        document,
        flags=re.DOTALL,
    )
    hints: list[DescriptionItemHint] = []
    for environment in environments:
        body = environment.group("body")
        starts = list(re.finditer(r"\\item\b", body))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
            item = body[start.start() : end]
            match = re.match(
                r"\\item\s*\[(?P<label>.*?)\]\s*\\mbox\{\}\s*\\\\",
                item,
                flags=re.DOTALL,
            )
            if match is None:
                hints.append(DescriptionItemHint(()))
                continue
            fragments = tuple(
                normalized
                for part in re.split(r"\$.*?\$", match.group("label"), flags=re.DOTALL)
                if (normalized := re.sub(r"\s+", " ", part).strip())
            )
            if not fragments or any(re.search(r"[\\{}]", part) for part in fragments):
                hints.append(DescriptionItemHint(()))
            else:
                hints.append(DescriptionItemHint(fragments))
    return tuple(hints)
