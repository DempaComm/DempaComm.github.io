"""Extract conservative statement-title hints from an original LaTeX source."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StatementHint:
    kind: str
    title: str | None


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


def extract_statement_hints(source: str) -> tuple[StatementHint, ...]:
    """Read environment kinds and optional titles without changing the LaTeX source."""
    document = source.split(r"\end{document}", 1)[0]
    document = re.sub(
        r"\\begin\{comment\}.*?\\end\{comment\}", "", document, flags=re.DOTALL
    )
    document = re.sub(r"(?m)(?<!\\)%.*$", "", document)
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
