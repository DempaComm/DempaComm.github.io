"""Apply only explicit, semantics-preserving corrections to Tylax output."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import asdict, dataclass


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


_LABEL = r"[A-Za-z][A-Za-z0-9:_.-]*"
_PROTECTED = re.compile(r'(/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*")', re.DOTALL)
_STRING_OR_LINE_COMMENT = re.compile(r'(//[^\n]*|"(?:\\.|[^"\\])*")')
_STYLE_IMPORT = (
    '#import "dempa-style.typ": definition, proposition, theorem, lemma, '
    "corollary, proof\n\n"
)
_STATEMENT_FUNCTIONS = {
    "df": "definition",
    "prop": "proposition",
    "thm": "theorem",
    "lem": "lemma",
    "cor": "corollary",
}


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
) -> tuple[str, AppliedRule | None, tuple[str, ...]]:
    pattern = re.compile(
        r"/\*\s*Begin\s+(?P<kind>df|prop|thm|lem|cor)\s*\*/"
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
        function = _STATEMENT_FUNCTIONS[match.group("kind")]
        return f"#{function}[\n  {body}\n]{suffix}"

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
                "Convert paired Tylax definition, proposition, theorem, lemma, and "
                "corollary markers to dempa-style statement calls"
            ),
            replacements=count,
        ),
        tuple(labels),
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
        r"/\*\s*(?:Begin|End)\s+(?:df|prop|thm|lem|cor|proof)\s*\*/",
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


def correct_tylax_source(source: str) -> CorrectionResult:
    """Return corrected text and a fail-closed report without mutating the input."""
    corrected = source
    applied: list[AppliedRule] = []
    corrected, rule = _replace_latex_neq(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule = _remove_tylax_title_separator(corrected)
    if rule is not None:
        applied.append(rule)
    corrected, rule, labels = _replace_statement_environments(corrected)
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
        item.rule_id in {"statement-environments", "proof-environments"}
        for item in applied
    ):
        corrected = _STYLE_IMPORT + corrected
    state = _StructureState(
        statement_labels=labels,
        duplicate_labels=duplicate_labels,
        unresolved_references=unresolved_references,
    )
    report = CorrectionReport(
        schema_version=1,
        source_sha256=_sha256_text(source),
        output_sha256=_sha256_text(corrected),
        applied_rules=tuple(applied),
        blocking_findings=_blocking_findings(corrected, state),
    )
    return CorrectionResult(corrected, report)
