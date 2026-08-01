from __future__ import annotations

import re
from dataclasses import dataclass, field


SUPPORTED_COMMANDS = {
    "alpha", "beta", "brace", "cdot", "emptyset", "exists", "forall",
    "frac", "geq", "in", "infty", "mathbb", "mid", "min", "neq",
    "nin", "paren", "sqrt", "text", "times", "to", "dempa-factorial",
}


@dataclass
class MathResult:
    source: str
    rules: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def applied(self, rule: str, count: int = 1) -> None:
        self.rules[rule] = self.rules.get(rule, 0) + count


def _replace_text_commands(text: str, result: MathResult) -> str:
    """Convert LaTeX text-in-math, including nested $...$, recursively."""
    output: list[str] = []
    cursor = 0
    marker = re.compile(r"\\text\s*\{")
    while match := marker.search(text, cursor):
        output.append(text[cursor:match.start()])
        depth = 1
        pos = match.end()
        while pos < len(text) and depth:
            if text[pos] == "{" and (pos == 0 or text[pos - 1] != "\\"):
                depth += 1
            elif text[pos] == "}" and (pos == 0 or text[pos - 1] != "\\"):
                depth -= 1
            pos += 1
        if depth:
            result.errors.append("MATH_UNCLOSED_TEXT: \\text{...} is not closed")
            return text
        inner = text[match.end():pos - 1]

        def nested_math(found: re.Match[str]) -> str:
            nested = convert_math(found.group(1))
            for rule, count in nested.rules.items():
                result.applied(rule, count)
            result.errors.extend(nested.errors)
            flattened = nested.source
            for command, symbol in {
                r"\neq": "≠", r"\geq": "≥", r"\in": "∈", r"\nin": "∉",
            }.items():
                flattened = flattened.replace(command, symbol)
            flattened = flattened.replace("{", "").replace("}", "")
            if "\\" in flattened:
                result.errors.append(
                    "MATH_TEXT_COMPLEX_NESTED_MATH: nested math in \\text cannot be flattened safely"
                )
            return flattened

        inner, count = re.subn(r"\$([^$]+)\$", nested_math, inner)
        if count:
            result.applied("MATH_TEXT_NESTED_MATH_FLATTENED", count)
        output.append(r"\text!{" + inner.strip() + "}")
        result.applied("MATH_TEXT")
        cursor = pos
    output.append(text[cursor:])
    return "".join(output)


def convert_math(source: str) -> MathResult:
    result = MathResult(source=source)
    text = source.strip()

    replacements = (
        (r"\\not\s*\\in\b", r"\\nin", "MATH_NOT_IN"),
        (r"\\notin\b", r"\\nin", "MATH_NOT_IN"),
        (r"\\ge\b", r"\\geq", "MATH_GE"),
        (r"\\dfrac\b", r"\\frac", "MATH_DFRAC"),
        (r"\\left\b|\\right\b", "", "MATH_DELIMITER_SIZE"),
        (r"\\[,!;:]", " ", "MATH_SPACING"),
        (r"\\\s", " ", "MATH_SPACING"),
    )
    for pattern, replacement, rule in replacements:
        text, count = re.subn(pattern, replacement, text)
        if count:
            result.applied(rule, count)

    text, count = re.subn(
        r"\\\{(.*?)\\\}",
        lambda match: r"\brace{" + match.group(1).strip() + "}",
        text,
        flags=re.DOTALL,
    )
    if count:
        result.applied("MATH_BRACE", count)

    text = _replace_text_commands(text, result)
    text = re.sub(r"\s+", " ", text).strip()
    text_argument_marker = "\u0000DEMPTEXTARG\u0000"
    text = text.replace(r"\text!{", text_argument_marker)
    if "!" in text:
        count = text.count("!")
        text = text.replace("!", r"\dempa-factorial")
        result.applied("MATH_FACTORIAL", count)
    text = text.replace(text_argument_marker, r"\text!{")
    text, count = re.subn(r"([_^])(?!\{)([A-Za-z0-9])", r"\1{\2}", text)
    if count:
        result.applied("MATH_BRACE_SCRIPT", count)

    commands = sorted(set(re.findall(r"\\([A-Za-z]+(?:-[A-Za-z]+)*)", text)))
    for command in commands:
        if command not in SUPPORTED_COMMANDS:
            result.errors.append(f"MATH_UNSUPPORTED_COMMAND: \\{command}")
    if "&" in text or r"\\" in text:
        result.errors.append("MATH_UNSUPPORTED_ALIGNMENT: aligned math is not supported")

    result.source = text
    return result
