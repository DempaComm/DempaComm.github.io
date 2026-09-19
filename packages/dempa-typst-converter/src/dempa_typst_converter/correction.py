"""Apply only explicit, semantics-preserving corrections to Tylax output."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import asdict, dataclass

from dempa_typst_converter.latex_hints import (
    DescriptionItemHint,
    EquationNumberingHint,
    IntersectionHint,
    NumberedListHint,
    StatementHint,
)


@dataclass(frozen=True)
class AppliedRule:
    rule_id: str
    description: str
    replacements: int


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    token: str
    line: int
    column: int
    source: str = "input"


@dataclass(frozen=True)
class CorrectionReport:
    schema_version: int
    source_sha256: str
    output_sha256: str
    applied_rules: tuple[AppliedRule, ...]
    blocking_findings: tuple[str, ...]
    review_findings: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    manual_review_required: bool = True
    publishable: bool = False

    def to_dict(self) -> dict:
        value = asdict(self)
        value["applied_rules"] = [asdict(rule) for rule in self.applied_rules]
        value["diagnostics"] = [asdict(item) for item in self.diagnostics]
        return value


@dataclass(frozen=True)
class CorrectionResult:
    source: str
    report: CorrectionReport

    @property
    def safe_to_write(self) -> bool:
        return not self.report.blocking_findings

    @property
    def requires_style(self) -> bool:
        return '"dempa-style.typ"' in self.source


@dataclass(frozen=True)
class _StructureState:
    statement_labels: tuple[str, ...] = ()
    duplicate_labels: tuple[str, ...] = ()
    unresolved_references: tuple[str, ...] = ()
    flattened_statement_kinds: tuple[str, ...] = ()
    hint_findings: tuple[str, ...] = ()
    equation_findings: tuple[str, ...] = ()
    description_findings: tuple[str, ...] = ()
    intersection_findings: tuple[str, ...] = ()
    numbered_list_findings: tuple[str, ...] = ()
    proof_findings: tuple[str, ...] = ()
    proof_boundary_positions: tuple[int, ...] = ()
    ignored_diagnostic_spans: tuple[tuple[int, int], ...] = ()


class _HintTracker:
    def __init__(self, hints: tuple[StatementHint, ...]) -> None:
        self.original = hints
        self.queues: dict[str, list[StatementHint]] = {}
        for hint in hints:
            self.queues.setdefault(hint.kind, []).append(hint)
        self.findings: list[str] = []
        self.applied_titles = 0

    def validate_sequence(self, observed: tuple[str, ...]) -> None:
        expected = tuple(hint.kind for hint in self.original)
        if observed != expected:
            self.findings.append(
                "LaTeX and Tylax statement sequences differ: "
                f"expected {expected}, observed {observed}"
            )

    def apply(self, kind: str, body: str) -> tuple[str, str | None]:
        queue = self.queues.get(kind, [])
        if not queue:
            self.findings.append(f"no LaTeX statement hint remains for: {kind}")
            return body, None
        hint = queue.pop(0)
        if hint.title is None:
            return body, None
        if re.search(r"[\\\[\]#@$*_<>]", hint.title):
            self.findings.append(f"unsupported LaTeX in statement title: {hint.title}")
            return body, None
        if not body.startswith(hint.title):
            self.findings.append(
                f"statement title does not match Tylax output: {hint.title}"
            )
            return body, None
        self.applied_titles += 1
        return body[len(hint.title) :].lstrip(), hint.title

    def finish(self) -> tuple[str, ...]:
        for kind, queue in sorted(self.queues.items()):
            if queue:
                self.findings.append(
                    f"unused LaTeX statement hints for {kind}: {len(queue)}"
                )
        return tuple(self.findings)


_LABEL = r"(?:[A-Za-z][A-Za-z0-9:_.-]*|[0-9]+)"
_PROTECTED = re.compile(
    r'(/\*.*?\*/|(?<!:)//[^\n]*|"(?:\\.|[^"\\])*")', re.DOTALL
)
_STRING_OR_LINE_COMMENT = re.compile(
    r'((?<!:)//[^\n]*|"(?:\\.|[^"\\])*")'
)
_TYLAX_COMMENT_ENVIRONMENT = re.compile(
    r"/\*\s*Begin\s+comment\s*\*/.*?/\*\s*End\s+comment\s*\*/",
    re.DOTALL,
)
_TYLAX_COMMENT_MARKER = re.compile(
    r"/\*\s*(?:Begin|End)\s+comment\s*\*/"
)
_DESCRIPTION_ITEM = re.compile(
    r"(?m)^(?P<indent>[ \t]*)/[ \t]+(?P<label>.*?)"
    + "\0\0"
    + r"\\[ \t]+"
    r"(?P<body>[^\r\n]*)$"
)
_STYLE_IMPORT = (
    '#import "dempa-style.typ": definition, proposition, theorem, lemma, '
    "corollary, fact, example, proof, bibliography-entry\n\n"
)
_STATEMENT_FUNCTIONS = {
    "df": "definition",
    "prop": "proposition",
    "thm": "theorem",
    "lem": "lemma",
    "cor": "corollary",
    "fact": "fact",
    "exam": "example",
}
_FLATTENED_STATEMENT_FUNCTIONS = {
    "Fact": "fact",
    "Lemma": "lemma",
}


def _statement_kind_sequence(source: str) -> tuple[str, ...]:
    inspectable = _without_strings_and_line_comments(source)
    pattern = re.compile(
        r"/\*\s*Begin\s+(?P<marker>df|prop|thm|lem|cor|fact|exam)\s*\*/"
        r"|^[ \t]*\*(?P<flat>Fact|Lemma)\s+\d+\.\*",
        re.MULTILINE,
    )
    kinds: list[str] = []
    for match in pattern.finditer(inspectable):
        marker = match.group("marker")
        if marker is not None:
            kinds.append(marker)
        else:
            kinds.append("fact" if match.group("flat") == "Fact" else "lem")
    return tuple(kinds)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _replace_latex_neq(source: str) -> tuple[str, AppliedRule | None]:
    math_comparison = re.compile(
        r"(?P<left>[A-Za-z][A-Za-z0-9_]*)\\neq\s*(?P<right>[A-Za-z0-9_]+)"
    )
    pieces = _PROTECTED.split(source)
    count = 0
    for index in range(0, len(pieces), 2):
        pieces[index], replacements = math_comparison.subn(
            r"\g<left> != \g<right>", pieces[index]
        )
        count += replacements
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="latex-neq",
        description=(
            "Convert a residual identifier \\neq identifier comparison to Typst != "
            "syntax outside strings and comments"
        ),
        replacements=count,
    )


_TYLAX_TITLE_SEPARATOR = re.compile(
    r"(?m)^[ \t]*(?:\\\*[ \t]+){1,2}\\\*[ \t]*\n"
    r"(?=[ \t]*\n?[ \t]*/\*\s*\\maketitle\s*\*/)"
)


def _remove_tylax_title_separator(source: str) -> tuple[str, AppliedRule | None]:
    corrected, count = _TYLAX_TITLE_SEPARATOR.subn("", source)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="tylax-title-separator",
        description=(
            "Remove the standalone escaped-star artifact immediately before Tylax's "
            "maketitle comment"
        ),
        replacements=count,
    )


def _replace_tylax_card_operator(source: str) -> tuple[str, AppliedRule | None]:
    math = re.compile(r"\$(?P<body>.*?)\$", re.DOTALL)
    count = 0

    def replace_math(match: re.Match[str]) -> str:
        nonlocal count
        body, replacements = re.subn(
            r"#text\[\\rm\s+card\]", 'op("card")', match.group("body")
        )
        count += replacements
        return f"${body}$"

    pieces = _PROTECTED.split(source)
    for index in range(0, len(pieces), 2):
        pieces[index] = math.sub(replace_math, pieces[index])
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="tylax-card-operator",
        description=(
            "Convert Tylax's residual roman card text inside math to a Typst operator"
        ),
        replacements=count,
    )


def _replace_tylax_domain_operators(
    source: str,
) -> tuple[str, AppliedRule | None]:
    math = re.compile(r"\$(?P<body>.*?)\$", re.DOTALL)
    operator = re.compile(r"#text\[\\rm\s+(?P<name>dom|cod)\]")
    count = 0

    def replace_math(match: re.Match[str]) -> str:
        nonlocal count

        def replace_operator(operator_match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            name = operator_match.group("name")
            return f'op("{name}")'

        return f"${operator.sub(replace_operator, match.group('body'))}$"

    pieces = _PROTECTED.split(source)
    for index in range(0, len(pieces), 2):
        pieces[index] = math.sub(replace_math, pieces[index])
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="tylax-domain-operators",
        description=(
            "Convert Tylax's residual roman dom and cod text inside math to "
            "Typst operators"
        ),
        replacements=count,
    )


def _tylax_intersection_positions(source: str) -> tuple[int, ...]:
    inspectable = _mask_typst_protected_regions(source)
    math = re.compile(r"\$(?P<body>.*?)\$", re.DOTALL)
    token = re.compile(r"(?<![A-Za-z0-9_])sect(?![A-Za-z0-9_])")
    positions: list[int] = []
    for math_match in math.finditer(inspectable):
        body_start = math_match.start("body")
        positions.extend(
            body_start + match.start()
            for match in token.finditer(math_match.group("body"))
        )
    return tuple(positions)


def _replace_tylax_intersections(
    source: str,
    hint: IntersectionHint | None,
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    positions = _tylax_intersection_positions(source)
    if not positions:
        return source, None, ()
    if hint is None:
        return source, None, (
            "Tylax sect tokens require a read-only LaTeX intersection hint",
        )
    if len(positions) != hint.occurrences:
        return source, None, (
            "LaTeX and Tylax intersection counts differ: "
            f"expected {hint.occurrences}, observed {len(positions)}",
        )
    pieces: list[str] = []
    cursor = 0
    for position in positions:
        pieces.append(source[cursor:position])
        pieces.append("inter")
        cursor = position + len("sect")
    pieces.append(source[cursor:])
    return (
        "".join(pieces),
        AppliedRule(
            rule_id="tylax-intersections",
            description=(
                "Convert Tylax sect tokens to Typst intersections only when their "
                "count matches read-only LaTeX hints"
            ),
            replacements=len(positions),
        ),
        (),
    )


def _replace_numbered_lists(
    source: str,
    hints: tuple[NumberedListHint, ...] | None,
) -> tuple[str, AppliedRule | None, tuple[str, ...], tuple[str, ...]]:
    pattern = re.compile(
        r"(?m)^[ \t]*label=\(\\arabic\*\)[ \t]*\n"
        r"(?P<items>(?:^[ \t]*\+[ \t]+[^\r\n]*(?:\n|$))+)",
    )
    matches = list(pattern.finditer(source))
    if not matches:
        return source, None, (), ()
    if hints is None:
        return source, None, (), (
            "Tylax decimal lists require read-only LaTeX numbered-list hints",
        )
    if len(matches) != len(hints):
        return source, None, (), (
            "LaTeX and Tylax decimal-list counts differ: "
            f"expected {len(hints)}, observed {len(matches)}",
        )

    replacements: list[tuple[re.Match[str], str]] = []
    all_labels: list[str] = []
    for list_index, (match, hint) in enumerate(zip(matches, hints), start=1):
        item_lines = tuple(
            line for line in match.group("items").splitlines() if line.strip()
        )
        if len(item_lines) != len(hint.labels):
            return source, None, (), (
                f"LaTeX and Tylax item counts differ in decimal list {list_index}: "
                f"expected {len(hint.labels)}, observed {len(item_lines)}",
            )
        converted = ["#numbered-list-start()"]
        for item_index, (line, latex_label) in enumerate(
            zip(item_lines, hint.labels), start=1
        ):
            item = re.match(
                rf"^[ \t]*\+[ \t]+(?:<(?P<label>{_LABEL})>[ \t]+)?(?P<body>.*)$",
                line,
            )
            if item is None or not item.group("body").strip():
                return source, None, (), (
                    f"Tylax decimal list {list_index} item {item_index} lacks a safe body",
                )
            observed_label = item.group("label")
            expected_label = (
                latex_label.replace(":", "-") if latex_label is not None else None
            )
            if observed_label != expected_label:
                return source, None, (), (
                    f"LaTeX and Tylax labels differ in decimal list {list_index} "
                    f"item {item_index}",
                )
            suffix = f" <{observed_label}>" if observed_label is not None else ""
            converted.append(
                f"#numbered-item[{item.group('body').strip()}]{suffix}"
            )
            if observed_label is not None:
                all_labels.append(observed_label)
        replacements.append((match, "\n".join(converted) + "\n"))

    pieces: list[str] = []
    cursor = 0
    for match, replacement in replacements:
        pieces.append(source[cursor : match.start()])
        pieces.append(replacement)
        cursor = match.end()
    pieces.append(source[cursor:])
    return (
        "".join(pieces),
        AppliedRule(
            rule_id="numbered-lists",
            description=(
                "Convert decimal Tylax lists only when item counts and labels match "
                "read-only LaTeX hints"
            ),
            replacements=len(matches),
        ),
        tuple(all_labels),
        (),
    )


def _remove_tylax_comment_environments(
    source: str,
) -> tuple[str, AppliedRule | None]:
    spans = _tylax_comment_environment_spans(source)
    count = len(spans)
    if not count:
        return source, None
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor:])
    corrected = "".join(pieces)
    return corrected, AppliedRule(
        rule_id="tylax-comment-environments",
        description=(
            "Remove content enclosed by paired Tylax markers for a LaTeX comment "
            "environment"
        ),
        replacements=count,
    )


def _remove_latex_displaystyle_token(source: str) -> tuple[str, AppliedRule | None]:
    math = re.compile(r"\$(?P<body>.*?)\$", re.DOTALL)
    count = 0

    def replace_math(match: re.Match[str]) -> str:
        nonlocal count
        body, replacements = re.subn(r"(?<![A-Za-z0-9_])display\s+", "", match.group("body"))
        count += replacements
        return f"${body}$"

    pieces = _PROTECTED.split(source)
    for index in range(0, len(pieces), 2):
        pieces[index] = math.sub(replace_math, pieces[index])
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="latex-displaystyle",
        description="Remove Tylax's residual display token inside Typst math",
        replacements=count,
    )


def _apply_equation_numbering_hint(
    source: str, hint: EquationNumberingHint | None
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    if hint is None:
        return source, None, ()
    if hint.has_numbered_display and hint.has_unnumbered_display:
        return source, None, (
            "LaTeX mixes numbered and unnumbered display math; Tylax's global numbering cannot preserve both",
        )
    if hint.has_numbered_display:
        return source, None, ()
    pattern = re.compile(
        r'(?m)^#set math\.equation\(numbering:\s*"\(1\)"\)\s*\n?'
    )
    corrected, count = pattern.subn("", source)
    if not count:
        return source, None, ()
    return corrected, AppliedRule(
        rule_id="unnumbered-display-math",
        description=(
            "Remove Tylax's global equation numbering when the read-only LaTeX "
            "source has no numbered display environment"
        ),
        replacements=count,
    ), ()


def _description_label_matches(
    label: str, hint: DescriptionItemHint
) -> bool:
    normalized = re.sub(r"\s+", " ", label).strip()
    fragments = hint.text_fragments
    if not fragments or not normalized.startswith(fragments[0]):
        return False
    cursor = 0
    for fragment in fragments:
        position = normalized.find(fragment, cursor)
        if position == -1:
            return False
        cursor = position + len(fragment)
    return normalized.endswith(fragments[-1])


def _replace_description_items(
    source: str,
    hints: tuple[DescriptionItemHint, ...] | None,
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    inspectable = _mask_typst_protected_regions(source)
    matches = list(_DESCRIPTION_ITEM.finditer(inspectable))
    if not matches:
        return source, None, ()
    if hints is None:
        return source, None, (
            "Tylax description item boundaries require read-only LaTeX hints",
        )
    if len(matches) != len(hints):
        return source, None, (
            "LaTeX and Tylax description item counts differ: "
            f"expected {len(hints)}, observed {len(matches)}",
        )
    if any(not hint.text_fragments for hint in hints):
        return source, None, (
            "a LaTeX description item lacks a safely verifiable label boundary",
        )
    for match, hint in zip(matches, hints, strict=True):
        label_start, label_end = match.span("label")
        if not _description_label_matches(source[label_start:label_end], hint):
            return source, None, (
                "a LaTeX description label does not match Tylax output",
            )

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        label_start, label_end = match.span("label")
        body_start, body_end = match.span("body")
        indent = match.group("indent")
        pieces.append(source[cursor : match.start()])
        pieces.append(
            f"{indent}/ {source[label_start:label_end].rstrip()}:\n"
            f"{indent}  {source[body_start:body_end].lstrip()}"
        )
        cursor = match.end()
    pieces.append(source[cursor:])
    return (
        "".join(pieces),
        AppliedRule(
            rule_id="description-items",
            description=(
                "Restore Tylax description item boundaries only when read-only "
                "LaTeX labels match"
            ),
            replacements=len(matches),
        ),
        (),
    )


def _unwrap_fraction_in_absolute_value(source: str) -> tuple[str, AppliedRule | None]:
    math = re.compile(r"\$(?P<body>.*?)\$", re.DOTALL)
    wrapped_fraction = re.compile(
        r"abs\(\{\s*(?P<fraction>frac\([^{}]*\))\s*\}\)"
    )
    count = 0

    def replace_math(match: re.Match[str]) -> str:
        nonlocal count
        body, replacements = wrapped_fraction.subn(
            r"abs(\g<fraction>)", match.group("body")
        )
        count += replacements
        return f"${body}$"

    pieces = _PROTECTED.split(source)
    for index in range(0, len(pieces), 2):
        pieces[index] = math.sub(replace_math, pieces[index])
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="absolute-fraction-braces",
        description=(
            "Remove Tylax's set-producing braces around a single fraction inside abs"
        ),
        replacements=count,
    )


def _replace_tylax_bibliography(source: str) -> tuple[str, AppliedRule | None]:
    entry = re.compile(
        r'#figure\(kind:\s*"bib",\s*supplement:\s*none,\s*caption:\s*'
        r"\[(?P<number>[^\[\]]+)\]\)\[(?P<body>[^\[\]]*)\]"
        rf"(?P<label>\s*<{_LABEL}>)?"
    )

    def replace_entry(match: re.Match[str]) -> str:
        label = match.group("label") or ""
        return (
            f"#bibliography-entry([{match.group('number').strip()}], "
            f"[{match.group('body').strip()}]){label}"
        )

    corrected, count = entry.subn(replace_entry, source)
    if not count:
        return source, None
    corrected = re.sub(
        r'(?m)^#show figure\.where\(kind:\s*"bib"\):[^\n]*\n?', "", corrected
    )
    corrected = re.sub(
        r"(?m)^= References\s*$", "#heading(numbering: none)[参考文献]", corrected
    )
    return corrected, AppliedRule(
        rule_id="tylax-bibliography",
        description="Convert Tylax bibliography figures to simple numbered entries",
        replacements=count,
    )


_TYLAX_BIBLIOGRAPHY_CONTROL_TAIL = re.compile(
    r"(?m)^[ \t]*\\\*[ \t]+"
    r"/\*\s*\\bibliographystyle\s*\*/[^\r\n]*?"
    r"/\*\s*\\bibliography\s*\*/[^\r\n]*[ \t]*$"
)


def _remove_tylax_bibliography_control_tail(
    source: str,
) -> tuple[str, AppliedRule | None]:
    if "#bibliography-entry(" not in source:
        return source, None
    corrected, count = _TYLAX_BIBLIOGRAPHY_CONTROL_TAIL.subn("", source)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="tylax-bibliography-control-tail",
        description=(
            "Remove Tylax's residual nocite wildcard, bibliography style, and "
            "database control line after bibliography entries were recovered"
        ),
        replacements=count,
    )


def _without_protected_text(source: str) -> str:
    return _PROTECTED.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        source,
    )


def _mask_typst_math(source: str) -> str:
    return re.sub(
        r"\$.*?\$",
        lambda match: "\n".join("\0" * len(part) for part in match.group(0).split("\n")),
        source,
        flags=re.DOTALL,
    )


def _without_strings_and_line_comments(source: str) -> str:
    return _STRING_OR_LINE_COMMENT.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        source,
    )


def _mask_matches(source: str, pattern: re.Pattern[str]) -> str:
    return pattern.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        source,
    )


def _mask_spans_with_nuls(
    source: str, spans: tuple[tuple[int, int], ...]
) -> str:
    """Mask spans while retaining offsets and preventing cross-span joins."""
    masked = list(source)
    for start, end in spans:
        for index in range(start, end):
            if masked[index] != "\n":
                masked[index] = "\0"
    return "".join(masked)


def _mask_typst_protected_regions(
    source: str, *, preserve_comment_markers: bool = False
) -> str:
    """Mask strings and nested comments without creating matchable whitespace."""
    masked = list(source)

    def hide(start: int, end: int) -> None:
        for index in range(start, end):
            if masked[index] != "\n":
                masked[index] = "\0"

    index = 0
    while index < len(source):
        if source.startswith("//", index) and (
            index == 0 or source[index - 1] != ":"
        ):
            start = index
            newline = source.find("\n", index + 2)
            index = len(source) if newline == -1 else newline
            hide(start, index)
            continue
        if source.startswith("/*", index):
            start = index
            depth = 1
            index += 2
            while index < len(source) and depth:
                if source.startswith("/*", index):
                    depth += 1
                    index += 2
                elif source.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            is_top_level_comment_marker = (
                depth == 0
                and _TYLAX_COMMENT_MARKER.fullmatch(source[start:index]) is not None
            )
            if not (preserve_comment_markers and is_top_level_comment_marker):
                hide(start, index)
            continue
        if source[index] == '"':
            start = index
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index = min(index + 2, len(source))
                elif source[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            hide(start, index)
            continue
        index += 1
    return "".join(masked)


def _tylax_comment_environment_spans(
    source: str,
) -> tuple[tuple[int, int], ...]:
    inspectable = _mask_typst_protected_regions(
        source, preserve_comment_markers=True
    )
    return tuple(
        match.span() for match in _TYLAX_COMMENT_ENVIRONMENT.finditer(inspectable)
    )


def _proof_input_positions(source: str) -> tuple[int, ...]:
    """Locate proof starts in the input that survive comment-environment removal."""
    without_comment_environments = _mask_spans_with_nuls(
        source, _tylax_comment_environment_spans(source)
    )
    inspectable = _mask_typst_protected_regions(without_comment_environments)
    return tuple(
        match.start() for match in re.finditer(re.escape("_Proof._"), inspectable)
    )


def _line_column(source: str, index: int) -> tuple[int, int]:
    line = source.count("\n", 0, index) + 1
    previous_newline = source.rfind("\n", 0, index)
    return line, index - previous_newline


def _diagnostics(
    input_source: str, corrected_source: str, state: _StructureState
) -> tuple[Diagnostic, ...]:
    input_inspectable = _mask_typst_protected_regions(input_source)
    input_with_markers = _mask_matches(input_source, _STRING_OR_LINE_COMMENT)
    input_comment_markers = _mask_typst_protected_regions(
        input_source, preserve_comment_markers=True
    )
    corrected_inspectable = _mask_typst_protected_regions(corrected_source)
    corrected_with_markers = _without_strings_and_line_comments(corrected_source)
    corrected_comment_markers = _mask_typst_protected_regions(
        corrected_source, preserve_comment_markers=True
    )
    pending: list[tuple[str, str, str, re.Pattern[str], str]] = []

    marker_patterns = (
        (
            "statement-marker",
            "Unpaired or unsupported Tylax statement marker",
            re.compile(
                r"/\*\s*(?:Begin|End)\s+(?:df|prop|thm|lem|cor|fact|exam|proof)\s*\*/"
            ),
        ),
        (
            "comment-marker",
            "Unpaired Tylax comment environment marker",
            re.compile(r"/\*\s*(?:Begin|End)\s+comment\s*\*/"),
        ),
        (
            "legacy-proof-marker",
            "Legacy LaTeX proof marker without safe boundaries",
            re.compile(r"/\*\s*\\proof\s*\*/"),
        ),
        (
            "unsupported-diagram",
            "Tylax CD diagram requires a dedicated structure conversion",
            re.compile(r"/\*\s*(?:Begin|End)\s+CD\s*\*/"),
        ),
    )
    for code, message, pattern in marker_patterns:
        corrected_searchable = (
            corrected_comment_markers
            if code == "comment-marker"
            else corrected_with_markers
        )
        remaining = {
            match.group(0) for match in pattern.finditer(corrected_searchable)
        }
        for token in remaining:
            source_kind = "comment-markers" if code == "comment-marker" else "markers"
            pending.append((code, message, token, re.compile(re.escape(token)), source_kind))

    raw_labels = {
        match.group(0).strip()
        for match in re.finditer(r"(?m)^\s*<[^<>\r\n]+>\s*", corrected_inspectable)
    }
    for token in raw_labels:
        pending.append(
            (
                "raw-label",
                "Raw label remains outside a supported statement",
                token,
                re.compile(re.escape(token)),
                "inspectable",
            )
        )

    if _DESCRIPTION_ITEM.search(corrected_inspectable):
        pending.append(
            (
                "description-boundary",
                "Tylax description item remains without a verified term boundary",
                '""\\',
                _DESCRIPTION_ITEM,
                "inspectable",
            )
        )

    for label in state.duplicate_labels:
        token = f"<{label}>"
        pending.append(
            (
                "duplicate-label",
                f"Duplicate statement label: {label}",
                token,
                re.compile(re.escape(token)),
                "inspectable",
            )
        )
    for label in state.unresolved_references:
        token = f"@{label}"
        pending.append(
            (
                "unresolved-reference",
                f"Reference has no converted statement target: {label}",
                token,
                re.compile(re.escape(token)),
                "inspectable",
            )
        )

    residual_commands = sorted(set(re.findall(r"\\[A-Za-z@]+", corrected_inspectable)))
    for token in residual_commands:
        pending.append(
            (
                "unsupported-latex-command",
                f"Unsupported LaTeX command remains: {token}",
                token,
                re.compile(re.escape(token)),
                "inspectable",
            )
        )
    residual_symbols = sorted(set(re.findall(r"\\[^A-Za-z@\s]", corrected_inspectable)))
    for token in residual_symbols:
        pending.append(
            (
                "unsupported-escaped-symbol",
                f"Unsupported escaped symbol remains: {token}",
                token,
                re.compile(re.escape(token)),
                "inspectable",
            )
        )

    found: list[tuple[int, Diagnostic]] = []
    seen: set[tuple[str, int, str]] = set()
    for input_index in state.proof_boundary_positions:
        key = ("proof-boundary", input_index, "_Proof._")
        seen.add(key)
        line, column = _line_column(input_source, input_index)
        found.append(
            (
                input_index,
                Diagnostic(
                    code="proof-boundary",
                    message=(
                        "Proof remains without the supported explicit square end marker"
                    ),
                    token="_Proof._",
                    line=line,
                    column=column,
                ),
            )
        )
    for code, message, token, pattern, source_kind in pending:
        if source_kind == "markers":
            searchable = input_with_markers
        elif source_kind == "comment-markers":
            searchable = input_comment_markers
        else:
            searchable = input_inspectable
        for match in pattern.finditer(searchable):
            if code == "unsupported-escaped-symbol" and any(
                start <= match.start() < end
                for start, end in state.ignored_diagnostic_spans
            ):
                continue
            key = (code, match.start(), token)
            if key in seen:
                continue
            seen.add(key)
            line, column = _line_column(input_source, match.start())
            found.append(
                (
                    match.start(),
                    Diagnostic(
                        code=code,
                        message=message,
                        token=token,
                        line=line,
                        column=column,
                    ),
                )
            )
    return tuple(item for _, item in sorted(found, key=lambda pair: pair[0]))


def _replace_statement_environments(
    source: str,
    hints: _HintTracker | None,
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    pattern = re.compile(
        r"/\*\s*Begin\s+(?P<kind>df|prop|thm|lem|cor|fact|exam)\s*\*/"
        r"(?P<body>.*?)"
        r"/\*\s*End\s+(?P=kind)\s*\*/",
        re.DOTALL,
    )
    labels: list[str] = []

    def replace(match: re.Match[str]) -> str:
        body = match.group("body").strip()
        suffix = ""

        def consume_label(value: str) -> str:
            nonlocal suffix
            label_match = re.match(rf"^<(?P<label>{_LABEL})>\s*", value)
            if label_match is None:
                return value
            label = label_match.group("label")
            labels.append(label)
            suffix = f" <{label}>"
            return value[label_match.end() :]

        body = consume_label(body)
        title = None
        if hints is not None:
            body, title = hints.apply(match.group("kind"), body)
            if not suffix:
                body = consume_label(body)
        function = _STATEMENT_FUNCTIONS[match.group("kind")]
        title_argument = f"(title: [{title}])" if title is not None else ""
        return f"#{function}{title_argument}[\n  {body}\n]{suffix}"

    pieces = _STRING_OR_LINE_COMMENT.split(source)
    count = 0
    for index in range(0, len(pieces), 2):
        pieces[index], replacements = pattern.subn(replace, pieces[index])
        count += replacements
    corrected = "".join(pieces)
    if not count:
        return source, None, ()
    return (
        corrected,
        AppliedRule(
            rule_id="statement-environments",
            description=(
                "Convert paired Tylax statement markers to dempa-style statement calls"
            ),
            replacements=count,
        ),
        tuple(labels),
    )


def _replace_flattened_statements(
    source: str,
    hints: _HintTracker | None,
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    """Recover statement structure that Tylax rendered as broken emphasis.

    Tylax discards the boundary between an optional theorem title and its body in this
    representation. Without verified LaTeX hints, the complete text is retained as the
    body instead of guessing a title.
    """
    pattern = re.compile(
        r"(?ms)^[ \t]*\*(?P<kind>Fact|Lemma)\s+\d+\.\*[ \t]*_"
        r"(?P<body>.*?)[ \t]+_[ \t]*$"
    )
    kinds: list[str] = []

    def replace(match: re.Match[str]) -> str:
        kind = match.group("kind")
        kinds.append(kind)
        function = _FLATTENED_STATEMENT_FUNCTIONS[kind]
        body = match.group("body").strip()
        title = None
        if hints is not None:
            body, title = hints.apply("fact" if kind == "Fact" else "lem", body)
        title_argument = f"(title: [{title}])" if title is not None else ""
        return f"#{function}{title_argument}[\n  {body}\n]"

    pieces = _STRING_OR_LINE_COMMENT.split(source)
    count = 0
    for index in range(0, len(pieces), 2):
        pieces[index], replacements = pattern.subn(replace, pieces[index])
        count += replacements
    corrected = "".join(pieces)
    if not count:
        return source, None, ()
    return (
        corrected,
        AppliedRule(
            rule_id="flattened-statements",
            description=(
                "Recover Tylax Fact and Lemma displays as shared-numbered dempa-style "
                "statements while retaining all title and body text"
            ),
            replacements=count,
        ),
        tuple(kinds),
    )


def _replace_proofs(
    source: str,
) -> tuple[str, AppliedRule | None, tuple[int, ...]]:
    pattern = re.compile(
        r"_Proof\._(?P<body>(?:(?!_Proof\._).)*?)"
        r"#h\(1fr\)\s*\$square\.stroked\$",
        re.DOTALL,
    )
    inspectable = _mask_typst_protected_regions(source)
    starts = list(re.finditer(re.escape("_Proof._"), inspectable))
    matches = list(pattern.finditer(inspectable))
    converted_starts = {match.start() for match in matches}
    remaining_ordinals = tuple(
        ordinal
        for ordinal, start in enumerate(starts)
        if start.start() not in converted_starts
    )
    pieces: list[str] = []
    cursor = 0
    for match in matches:
        body_start, body_end = match.span("body")
        pieces.append(source[cursor : match.start()])
        pieces.append(f"#proof[\n  {source[body_start:body_end].strip()}\n]")
        cursor = match.end()
    pieces.append(source[cursor:])
    corrected = "".join(pieces)
    count = len(matches)
    if not count:
        return source, None, remaining_ordinals
    return (
        corrected,
        AppliedRule(
            rule_id="proof-environments",
            description=(
                "Convert a Tylax proof with an explicit square end marker to "
                "dempa-style proof"
            ),
            replacements=count,
        ),
        remaining_ordinals,
    )


def _replace_single_line_legacy_proofs(
    source: str,
) -> tuple[str, AppliedRule | None]:
    pattern = re.compile(
        r"(?m)^[ \t]*/\*\s*\\proof\s*\*/[ \t]*(?P<body>[^\r\n]+?)[ \t]*$"
    )

    def replace(match: re.Match[str]) -> str:
        return f"#proof[\n  {match.group('body').strip()}\n]"

    pieces = _STRING_OR_LINE_COMMENT.split(source)
    count = 0
    for index in range(0, len(pieces), 2):
        pieces[index], replacements = pattern.subn(replace, pieces[index])
        count += replacements
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="single-line-legacy-proofs",
        description=(
            "Convert a legacy Tylax proof marker only when its body has an explicit "
            "single-line boundary"
        ),
        replacements=count,
    )


def _replace_statement_references(
    source: str, labels: tuple[str, ...]
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    known = set(labels)
    unresolved: set[str] = set()
    count = 0
    inspectable = _mask_typst_math(_mask_typst_protected_regions(source))
    matches = list(re.finditer(rf"@(?P<label>{_LABEL})", inspectable))
    pieces: list[str] = []
    cursor = 0
    for match in matches:
        label = match.group("label")
        pieces.append(source[cursor : match.start()])
        if label in known:
            pieces.append(f"#ref(<{label}>, supplement: none)")
            count += 1
        else:
            pieces.append(source[match.start() : match.end()])
            unresolved.add(label)
        cursor = match.end()
    pieces.append(source[cursor:])
    corrected = "".join(pieces)
    if not count:
        return corrected, None, tuple(sorted(unresolved))
    return (
        corrected,
        AppliedRule(
            rule_id="statement-references",
            description=(
                "Convert references to labels on converted statements to number-only "
                "Typst references"
            ),
            replacements=count,
        ),
        tuple(sorted(unresolved)),
    )


def _blocking_findings(source: str, state: _StructureState) -> tuple[str, ...]:
    findings: list[str] = []
    marker_inspectable = _without_strings_and_line_comments(source)
    comment_marker_inspectable = _mask_typst_protected_regions(
        source, preserve_comment_markers=True
    )
    if re.search(
        r"/\*\s*(?:Begin|End)\s+(?:df|prop|thm|lem|cor|fact|exam|proof)\s*\*/",
        marker_inspectable,
    ):
        findings.append(
            "unpaired or unsupported Tylax statement markers remain"
        )
    if re.search(
        r"/\*\s*(?:Begin|End)\s+comment\s*\*/",
        comment_marker_inspectable,
    ):
        findings.append("unpaired Tylax comment environment marker remains")
    if re.search(r"/\*\s*(?:Begin|End)\s+CD\s*\*/", marker_inspectable):
        findings.append("a Tylax CD diagram remains unsupported")
    if re.search(r"/\*\s*\\proof\s*\*/", marker_inspectable):
        findings.append("a legacy LaTeX proof marker remains without safe boundaries")
    inspectable = _mask_typst_protected_regions(source)
    if re.search(r"(?m)^\s*<[^<>\r\n]+>\s*", inspectable):
        findings.append(
            "raw labels remain outside supported statement elements"
        )
    if state.proof_boundary_positions:
        findings.append(
            "a proof without the supported explicit square end marker remains"
        )
    if state.duplicate_labels:
        findings.append("duplicate statement labels: " + ", ".join(state.duplicate_labels))
    if state.unresolved_references:
        findings.append(
            "references without a converted statement target: "
            + ", ".join(state.unresolved_references)
        )
    findings.extend(state.hint_findings)
    findings.extend(state.equation_findings)
    findings.extend(state.description_findings)
    findings.extend(state.intersection_findings)
    findings.extend(state.numbered_list_findings)
    findings.extend(state.proof_findings)
    reference_inspectable = _mask_typst_math(inspectable)
    remaining_references = sorted(
        set(re.findall(rf"@({_LABEL})", reference_inspectable))
    )
    if remaining_references and not state.unresolved_references:
        findings.append("unsupported references remain: " + ", ".join(remaining_references))
    residual_commands = sorted(set(re.findall(r"\\[A-Za-z@]+", inspectable)))
    if residual_commands:
        findings.append(
            "unsupported LaTeX commands remain: " + ", ".join(residual_commands)
        )
    residual_symbols = sorted(set(re.findall(r"\\[^A-Za-z@\s]", inspectable)))
    if residual_symbols:
        findings.append(
            "unsupported escaped symbols remain: " + ", ".join(residual_symbols)
        )
    return tuple(findings)


def correct_tylax_source(
    source: str,
    statement_hints: tuple[StatementHint, ...] | None = None,
    equation_numbering_hint: EquationNumberingHint | None = None,
    description_item_hints: tuple[DescriptionItemHint, ...] | None = None,
    intersection_hint: IntersectionHint | None = None,
    numbered_list_hints: tuple[NumberedListHint, ...] | None = None,
) -> CorrectionResult:
    """Return corrected text and a fail-closed report without mutating the input."""
    ignored_diagnostic_spans = tuple(
        match.span() for match in _TYLAX_TITLE_SEPARATOR.finditer(source)
    )
    if '#figure(kind: "bib"' in source:
        ignored_diagnostic_spans += tuple(
            match.span()
            for match in _TYLAX_BIBLIOGRAPHY_CONTROL_TAIL.finditer(source)
        )
    corrected = source
    proof_input_positions = _proof_input_positions(source)
    applied: list[AppliedRule] = []
    hint_tracker = _HintTracker(statement_hints) if statement_hints is not None else None
    corrected, rule = _remove_tylax_comment_environments(corrected)
    if rule is not None:
        applied.append(rule)
    if hint_tracker is not None:
        hint_tracker.validate_sequence(_statement_kind_sequence(corrected))
    corrected, rule = _replace_latex_neq(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_tylax_title_separator(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_latex_displaystyle_token(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule, equation_findings = _apply_equation_numbering_hint(
        corrected, equation_numbering_hint
    )
    if rule is not None:
        applied.append(rule)
    corrected, rule, description_findings = _replace_description_items(
        corrected, description_item_hints
    )
    if rule is not None:
        applied.append(rule)
    corrected, rule = _unwrap_fraction_in_absolute_value(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _replace_tylax_bibliography(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_tylax_bibliography_control_tail(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule, numbered_list_labels, numbered_list_findings = (
        _replace_numbered_lists(corrected, numbered_list_hints)
    )
    if rule is not None:
        applied.append(rule)
    corrected, rule, labels = _replace_statement_environments(corrected, hint_tracker)
    if rule is not None:
        applied.append(rule)
    corrected, rule, flattened_kinds = _replace_flattened_statements(
        corrected, hint_tracker
    )
    if rule is not None:
        applied.append(rule)
    corrected, rule, remaining_proof_ordinals = _replace_proofs(corrected)
    if rule is not None:
        applied.append(rule)
    proof_occurrence_count = len(remaining_proof_ordinals) + (
        rule.replacements if rule is not None else 0
    )
    if proof_occurrence_count == len(proof_input_positions):
        proof_boundary_positions = tuple(
            proof_input_positions[ordinal] for ordinal in remaining_proof_ordinals
        )
        proof_findings: tuple[str, ...] = ()
    else:
        proof_boundary_positions = ()
        proof_findings = (
            "proof occurrences changed before boundary conversion; "
            "input diagnostic locations are unavailable",
        )
    corrected, rule = _replace_single_line_legacy_proofs(corrected)
    if rule is not None:
        applied.append(rule)
    labels = labels + numbered_list_labels
    counts = Counter(labels)
    duplicate_labels = tuple(sorted(label for label, count in counts.items() if count > 1))
    corrected, rule, unresolved_references = _replace_statement_references(
        corrected, labels
    )
    if rule is not None:
        applied.append(rule)
    corrected, rule = _replace_tylax_card_operator(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _replace_tylax_domain_operators(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule, intersection_findings = _replace_tylax_intersections(
        corrected, intersection_hint
    )
    if rule is not None:
        applied.append(rule)
    if any(
        item.rule_id in {
            "statement-environments",
            "flattened-statements",
            "proof-environments",
            "single-line-legacy-proofs",
            "tylax-bibliography",
            "numbered-lists",
        }
        for item in applied
    ):
        corrected = _STYLE_IMPORT + corrected
    hint_findings = hint_tracker.finish() if hint_tracker is not None else ()
    if hint_tracker is not None and hint_tracker.applied_titles:
        applied.append(
            AppliedRule(
                rule_id="statement-titles",
                description=(
                    "Separate optional statement titles only when they match the read-only LaTeX hints"
                ),
                replacements=hint_tracker.applied_titles,
            )
        )
    state = _StructureState(
        statement_labels=labels,
        duplicate_labels=duplicate_labels,
        unresolved_references=unresolved_references,
        flattened_statement_kinds=flattened_kinds,
        hint_findings=hint_findings,
        equation_findings=equation_findings,
        description_findings=description_findings,
        intersection_findings=intersection_findings,
        numbered_list_findings=numbered_list_findings,
        proof_findings=proof_findings,
        proof_boundary_positions=proof_boundary_positions,
        ignored_diagnostic_spans=ignored_diagnostic_spans,
    )
    review_findings: list[str] = []
    if statement_hints is None and any(
        item.rule_id == "statement-environments" for item in applied
    ):
        review_findings.append(
            "Tylax statement markers do not preserve optional title boundaries; review statement headings"
        )
    if statement_hints is None and flattened_kinds:
        review_findings.append(
            "Tylax flattened optional statement titles into body text for: "
            + ", ".join(sorted(set(flattened_kinds)))
        )
    report = CorrectionReport(
        schema_version=2,
        source_sha256=_sha256_text(source),
        output_sha256=_sha256_text(corrected),
        applied_rules=tuple(applied),
        blocking_findings=_blocking_findings(corrected, state),
        review_findings=tuple(review_findings),
        diagnostics=_diagnostics(source, corrected, state),
    )
    return CorrectionResult(corrected, report)
