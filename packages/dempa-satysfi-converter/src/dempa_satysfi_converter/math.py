from __future__ import annotations

import re
from dataclasses import dataclass, field


SUPPORTED_COMMANDS = {
    "Longleftrightarrow", "Longrightarrow", "abs", "alpha", "beta", "bigcup", "brace", "cap", "cdot",
    "cdots", "dempa-bar", "dempa-bigcup", "dempa-bigcup-sub", "dempa-ell", "dempa-factorial", "dempa-matrix", "dempa-pi-sub",
    "dempa-sum", "emptyset",
    "chi", "colon-rel", "cup", "epsilon", "equiv", "exists", "forall", "frac", "geq", "in",
    "infty", "int", "leq", "lim", "mathbb", "mathcal", "mathfrak", "mathop", "mathrm",
    "max", "mid", "min", "mu", "neq", "nin", "norm", "nu", "omega", "paren", "partial",
    "pi", "prec", "sqrt", "subset", "sum", "sup", "text", "theta", "times", "to",
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


def _replace_parenthesized_arrays(text: str, result: MathResult) -> str:
    pattern = re.compile(
        r"\\left\s*\(\s*\\begin\{array\}\{([^{}]+)\}"
        r"(.*?)\\end\{array\}\s*\\right\s*\)",
        flags=re.DOTALL,
    )

    def replace(found: re.Match[str]) -> str:
        columns = re.sub(r"\s+", "", found.group(1))
        if not columns or not re.fullmatch(r"[lcr]+", columns):
            result.errors.append(
                f"MATH_UNSUPPORTED_ARRAY_COLUMNS: {found.group(1).strip()}"
            )
            return found.group(0)
        rendered_rows: list[list[str]] = []
        for row_source in re.split(r"\\\\", found.group(2)):
            if not row_source.strip():
                continue
            cell_sources = row_source.split("&")
            if len(cell_sources) != len(columns) or any(not cell.strip() for cell in cell_sources):
                result.errors.append("MATH_ARRAY_SHAPE: every row must match the column count")
                return found.group(0)
            rendered_cells: list[str] = []
            for cell_source in cell_sources:
                cell = convert_math(cell_source)
                for rule, count in cell.rules.items():
                    result.applied(rule, count)
                result.errors.extend(cell.errors)
                rendered_cells.append(cell.source)
            rendered_rows.append(rendered_cells)
        if not rendered_rows:
            result.errors.append("MATH_EMPTY_ARRAY: array has no rows")
            return found.group(0)
        if len(columns) != 2 or len(rendered_rows) != 2:
            result.errors.append("MATH_ARRAY_SHAPE: only a 2x2 matrix is supported")
            return found.group(0)
        result.applied("MATH_MATRIX_ARRAY")
        values = [value for row in rendered_rows for value in row]
        return r"\dempa-matrix" + "".join("{" + value + "}" for value in values)

    converted = pattern.sub(replace, text)
    if r"\begin{array}" in converted or r"\end{array}" in converted:
        result.errors.append(
            "MATH_UNSUPPORTED_ARRAY: only a parenthesized rectangular l/c/r array is supported"
        )
    return converted


def _replace_braced_bars(text: str, result: MathResult) -> str:
    """Convert only explicitly braced LaTeX bars, preserving nested math."""
    output: list[str] = []
    cursor = 0
    marker = re.compile(r"\\bar\s*\{")
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
            result.errors.append("MATH_UNCLOSED_BAR: \\bar{...} is not closed")
            output.append(text[match.start():])
            return "".join(output)
        inner_source = text[match.end():pos - 1]
        if not inner_source.strip():
            result.errors.append("MATH_EMPTY_BAR: \\bar{...} must contain math")
            output.append(text[match.start():pos])
        else:
            inner = convert_math(inner_source)
            for rule, count in inner.rules.items():
                result.applied(rule, count)
            result.errors.extend(inner.errors)
            output.append(r"\dempa-bar{" + inner.source + "}")
            result.applied("MATH_BAR")
        cursor = pos
    output.append(text[cursor:])
    return "".join(output)


def _replace_sized_absolute_values(text: str, result: MathResult) -> str:
    """Convert explicit LaTeX left/right absolute-value delimiters recursively."""
    pattern = re.compile(r"\\left\s*\|(.*?)\\right\s*\|", flags=re.DOTALL)

    def replace(found: re.Match[str]) -> str:
        inner = convert_math(found.group(1))
        for rule, count in inner.rules.items():
            result.applied(rule, count)
        result.errors.extend(inner.errors)
        result.applied("MATH_ABSOLUTE_VALUE")
        return r"\abs{" + inner.source + "}"

    return pattern.sub(replace, text)


def convert_math(source: str) -> MathResult:
    result = MathResult(source=source)
    text = source.strip()

    aligned = re.fullmatch(
        r"\\begin\{align\*?\}\s*(.*?)\s*\\end\{align\*?\}", text, flags=re.DOTALL
    )
    if aligned:
        rows: list[str] = []
        for row_source in re.split(r"\\\\", aligned.group(1)):
            if not row_source.strip():
                continue
            cells: list[str] = []
            for cell_source in row_source.split("&"):
                cell = convert_math(cell_source)
                for rule, count in cell.rules.items():
                    result.applied(rule, count)
                result.errors.extend(cell.errors)
                cells.append("${" + cell.source + "}")
            rows.append("[" + "; ".join(cells) + "]")
        if not rows:
            result.errors.append("MATH_EMPTY_ALIGNMENT: align environment has no rows")
        result.source = r"\align([" + "; ".join(rows) + "]);"
        result.applied("MATH_ALIGN")
        return result

    text = _replace_parenthesized_arrays(text, result)
    text = _replace_braced_bars(text, result)
    text = _replace_sized_absolute_values(text, result)

    replacements = (
        (r"\\\s*\|\s*\\\s*", r" \\mid ", "MATH_MID"),
        (r"\\not\s*\\in\b", r"\\nin", "MATH_NOT_IN"),
        (r"\\notin\b", r"\\nin", "MATH_NOT_IN"),
        (r"\\ge\b", r"\\geq", "MATH_GE"),
        (r"\\le\b", r"\\leq", "MATH_LE"),
        (r"\\varepsilon\b", r"\\epsilon", "MATH_VAREPSILON"),
        (r"\\dfrac\b", r"\\frac", "MATH_DFRAC"),
        (r"\\iff\b", r"\\Longleftrightarrow", "MATH_IFF"),
        (r"\\colon\b", r"\\colon-rel", "MATH_COLON"),
        (r"\\ell\b", r"\\dempa-ell", "MATH_ELL"),
        (r"\\exp\b", r"\\mathrm{exp}", "MATH_EXP"),
        (r"\\sp\s*\{([^{}]+)\}", r"^{\1}", "MATH_SP_SUPERSCRIPT"),
        (r"\\left\b|\\right\b", "", "MATH_DELIMITER_SIZE"),
        (r"\\[,!;:]", " ", "MATH_SPACING"),
        (r"\\\s", " ", "MATH_SPACING"),
    )
    for pattern, replacement, rule in replacements:
        text, count = re.subn(pattern, replacement, text)
        if count:
            result.applied(rule, count)

    text, count = re.subn(
        r"\\\|(.+?)\\\|",
        lambda match: r"\norm{" + match.group(1).strip() + "}",
        text,
    )
    if count:
        result.applied("MATH_NORM", count)
    if r"\|" in text:
        result.errors.append(
            "MATH_UNBALANCED_LATEX_NORM: LaTeX norm delimiters must be paired"
        )

    text, count = re.subn(
        r"\|\|([^|]+)\|\|",
        lambda match: r"\norm{" + match.group(1).strip() + "}",
        text,
    )
    if count:
        result.applied("MATH_NORM", count)
    if "||" in text:
        result.errors.append("MATH_UNBALANCED_NORM: double vertical bars must be paired")

    absolute_pattern = re.compile(
        r"\|([^|]+)\|(?=$|[=+\-*/)<>,_^.}]|\\(?:leq|geq|neq)\b)"
    )
    text, count = absolute_pattern.subn(
        lambda match: r"\abs{" + match.group(1).strip() + "}",
        text,
    )
    if count:
        result.applied("MATH_ABSOLUTE_VALUE", count)
    if "|" in text:
        result.errors.append(
            "MATH_UNSUPPORTED_VERTICAL_BAR: use an unambiguous absolute value or set separator"
        )

    text, count = re.subn(
        r"\\\{(.*?)\\\}",
        lambda match: r"\brace{" + match.group(1).strip() + "}",
        text,
        flags=re.DOTALL,
    )
    if count:
        result.applied("MATH_BRACE", count)

    text = _replace_text_commands(text, result)
    text, count = re.subn(
        r"\\sum\s*_(?:\{([^{}]*)\}|([A-Za-z0-9]))\s*\^(?:\{([^{}]*)\}|([A-Za-z0-9]))",
        lambda match: (
            r"\dempa-sum{" + (match.group(1) or match.group(2)).strip() + "}{"
            + (match.group(3) or match.group(4)).strip() + "}"
        ),
        text,
    )
    if count:
        result.applied("MATH_BIG_OPERATOR_SCRIPTS", count)
    text, count = re.subn(
        r"\\bigcup\s*_(?:\{([^{}]*)\}|([A-Za-z0-9]))\s*\^(?:\{([^{}]*)\}|([A-Za-z0-9]))",
        lambda match: (
            r"\dempa-bigcup{" + (match.group(1) or match.group(2)).strip() + "}{"
            + (match.group(3) or match.group(4)).strip() + "}"
        ),
        text,
    )
    if count:
        result.applied("MATH_BIG_OPERATOR_SCRIPTS", count)
    text, count = re.subn(
        r"\\bigcup\s*_(?:\{([^{}]*)\}|([A-Za-z0-9]))",
        lambda match: r"\dempa-bigcup-sub{" + (match.group(1) or match.group(2)).strip() + "}",
        text,
    )
    if count:
        result.applied("MATH_BIG_OPERATOR_SUBSCRIPT", count)
    text, count = re.subn(
        r"\\pi\s*_(?:\{([^{}]*)\}|([A-Za-z0-9]))",
        lambda match: r"\dempa-pi-sub{" + (match.group(1) or match.group(2)).strip() + "}",
        text,
    )
    if count:
        result.applied("MATH_COMMAND_SUBSCRIPT", count)
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
