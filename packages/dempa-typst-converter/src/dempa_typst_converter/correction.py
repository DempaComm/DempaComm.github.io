"""Apply only explicit, semantics-preserving corrections to Tylax output."""

from __future__ import annotations

import hashlib
import re
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _replace_latex_neq(source: str) -> tuple[str, AppliedRule | None]:
    protected = re.compile(r'(/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*")', re.DOTALL)
    math_comparison = re.compile(
        r"(?P<left>[A-Za-z][A-Za-z0-9_]*)\\neq\s*(?P<right>[A-Za-z0-9_]+)"
    )
    pieces = protected.split(source)
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


def _blocking_findings(source: str) -> tuple[str, ...]:
    findings: list[str] = []
    if re.search(r"/\*\s*Begin\s+(?:df|prop|thm|lem|cor|proof)\s*\*/", source):
        findings.append(
            "Tylax theorem markers remain; semantic environment conversion is required"
        )
    if re.search(r"(?m)^\s*<[A-Za-z][A-Za-z0-9:_.-]*>\s*", source):
        findings.append(
            "raw labels remain; attach labels to supported Typst statement elements"
        )
    if re.search(r"@[A-Za-z][A-Za-z0-9:_.-]*", source):
        findings.append(
            "references remain; verify that every reference targets a supported element"
        )
    residual_commands = sorted(set(re.findall(r"\\[A-Za-z@]+", source)))
    if residual_commands:
        findings.append(
            "unsupported LaTeX commands remain: " + ", ".join(residual_commands)
        )
    return tuple(findings)


def correct_tylax_source(source: str) -> CorrectionResult:
    """Return corrected text and a fail-closed report without mutating the input."""
    corrected = source
    applied: list[AppliedRule] = []
    corrected, rule = _replace_latex_neq(corrected)
    if rule is not None:
        applied.append(rule)
    report = CorrectionReport(
        schema_version=1,
        source_sha256=_sha256_text(source),
        output_sha256=_sha256_text(corrected),
        applied_rules=tuple(applied),
        blocking_findings=_blocking_findings(corrected),
    )
    return CorrectionResult(corrected, report)
