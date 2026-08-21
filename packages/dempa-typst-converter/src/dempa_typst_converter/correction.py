"""Apply only explicit, semantics-preserving corrections to Tylax output."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import asdict, dataclass

from dempa_typst_converter.latex_hints import StatementHint


@dataclass(frozen=True)
class AppliedRule:
    rule_id: str
    description: str
    replacements: int


@dataclass(frozen=True)
class CorrectionReport:
    schema_version: int
    source_sha256: str
    output_sha256: str
    applied_rules: tuple[AppliedRule, ...]
    blocking_findings: tuple[str, ...]
    review_findings: tuple[str, ...] = ()
    manual_review_required: bool = True
    publishable: bool = False

    def to_dict(self) -> dict:
        value = asdict(self)
        value["applied_rules"] = [asdict(rule) for rule in self.applied_rules]
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


_LABEL = r"[A-Za-z][A-Za-z0-9:_.-]*"
_PROTECTED = re.compile(r'(/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*")', re.DOTALL)
_STRING_OR_LINE_COMMENT = re.compile(r'(//[^\n]*|"(?:\\.|[^"\\])*")')
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


def _remove_tylax_title_separator(source: str) -> tuple[str, AppliedRule | None]:
    pattern = re.compile(
        r"(?m)^[ \t]*\\\*[ \t]+\\\*[ \t]+\\\*[ \t]*\n"
        r"(?=[ \t]*\n?[ \t]*/\*\s*\\maketitle\s*\*/)"
    )
    corrected, count = pattern.subn("", source)
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


def _without_protected_text(source: str) -> str:
    return _PROTECTED.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        source,
    )


def _without_strings_and_line_comments(source: str) -> str:
    return _STRING_OR_LINE_COMMENT.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        source,
    )


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
        label_match = re.match(rf"^<(?P<label>{_LABEL})>\s*", body)
        suffix = ""
        if label_match is not None:
            label = label_match.group("label")
            labels.append(label)
            body = body[label_match.end() :]
            suffix = f" <{label}>"
        title = None
        if hints is not None:
            body, title = hints.apply(match.group("kind"), body)
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


def _replace_proofs(source: str) -> tuple[str, AppliedRule | None]:
    pattern = re.compile(
        r"_Proof\._(?P<body>.*?)#h\(1fr\)\s*\$square\.stroked\$",
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        return f"#proof[\n  {match.group('body').strip()}\n]"

    pieces = _PROTECTED.split(source)
    count = 0
    for index in range(0, len(pieces), 2):
        pieces[index], replacements = pattern.subn(replace, pieces[index])
        count += replacements
    corrected = "".join(pieces)
    if not count:
        return source, None
    return corrected, AppliedRule(
        rule_id="proof-environments",
        description=(
            "Convert a Tylax proof with an explicit square end marker to dempa-style proof"
        ),
        replacements=count,
    )


def _replace_statement_references(
    source: str, labels: tuple[str, ...]
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    known = set(labels)
    unresolved: set[str] = set()
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        label = match.group("label")
        if label not in known:
            unresolved.add(label)
            return match.group(0)
        count += 1
        return f"#ref(<{label}>, supplement: none)"

    pieces = _PROTECTED.split(source)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(rf"@(?P<label>{_LABEL})", replace, pieces[index])
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
    if re.search(
        r"/\*\s*(?:Begin|End)\s+(?:df|prop|thm|lem|cor|fact|exam|proof)\s*\*/",
        marker_inspectable,
    ):
        findings.append(
            "unpaired or unsupported Tylax statement markers remain"
        )
    inspectable = _without_protected_text(source)
    if re.search(rf"(?m)^\s*<{_LABEL}>\s*", inspectable):
        findings.append(
            "raw labels remain outside supported statement elements"
        )
    if "_Proof._" in inspectable:
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
    remaining_references = sorted(set(re.findall(rf"@({_LABEL})", inspectable)))
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
    source: str, statement_hints: tuple[StatementHint, ...] | None = None
) -> CorrectionResult:
    """Return corrected text and a fail-closed report without mutating the input."""
    corrected = source
    applied: list[AppliedRule] = []
    hint_tracker = _HintTracker(statement_hints) if statement_hints is not None else None
    if hint_tracker is not None:
        hint_tracker.validate_sequence(_statement_kind_sequence(source))
    corrected, rule = _replace_latex_neq(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_tylax_title_separator(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_latex_displaystyle_token(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _unwrap_fraction_in_absolute_value(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _replace_tylax_bibliography(corrected)
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
    corrected, rule = _replace_proofs(corrected)
    if rule is not None:
        applied.append(rule)
    counts = Counter(labels)
    duplicate_labels = tuple(sorted(label for label, count in counts.items() if count > 1))
    corrected, rule, unresolved_references = _replace_statement_references(
        corrected, labels
    )
    if rule is not None:
        applied.append(rule)
    if any(
        item.rule_id in {
            "statement-environments",
            "flattened-statements",
            "proof-environments",
            "tylax-bibliography",
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
    )
    return CorrectionResult(corrected, report)
