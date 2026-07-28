"""Temporary source normalizations used only for LaTeXML conversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

def _without_tex_comments(source: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in source.splitlines())


def _normalize_math_inside_text(source: str) -> tuple[str, int]:
    r"""Lift inline math out of a text command while retaining text segments.

    TeX accepts ``\text{words $...$}`` inside display math, but LaTeXML's math
    parser can leave that construct unparsed. The temporary copy becomes
    ``\text{words }...``. The protected manuscript is never rewritten.
    """
    output = []
    cursor = 0
    replacements = 0
    marker = r"\text{"
    while True:
        start = source.find(marker, cursor)
        if start < 0:
            output.append(source[cursor:])
            break
        output.append(source[cursor:start])
        depth = 1
        end = start + len(marker)
        while end < len(source) and depth:
            character = source[end]
            escaped = end > 0 and source[end - 1] == "\\"
            if not escaped and character == "{":
                depth += 1
            elif not escaped and character == "}":
                depth -= 1
            end += 1
        if depth:
            output.append(source[start:])
            break
        content = source[start + len(marker) : end - 1]
        matches = list(re.finditer(r"(?<!\\)\$([^$]+)(?<!\\)\$", content))
        if matches:
            inner_cursor = 0
            for match in matches:
                text_part = content[inner_cursor : match.start()]
                if _without_tex_comments(text_part).strip():
                    output.append(marker + text_part + "}")
                output.append(match.group(1))
                replacements += 1
                inner_cursor = match.end()
            text_part = content[inner_cursor:]
            if _without_tex_comments(text_part).strip():
                output.append(marker + text_part + "}")
        else:
            output.append(marker + content + "}")
        cursor = end
    return "".join(output), replacements


def _normalize_cross_row_braces(source: str) -> tuple[str, int]:
    """Render braces as text when an align row contains only one side."""
    replacements = 0
    environment_pattern = re.compile(
        r"(\\begin\{align\*?\})(.*?)(\\end\{align\*?\})", re.DOTALL
    )

    def replace_environment(match: re.Match[str]) -> str:
        nonlocal replacements
        parts = re.split(r"(?<!\\)(\\\\(?:\s*\[[^]]*\])?)", match.group(2))
        for index in range(0, len(parts), 2):
            row = parts[index]
            opening = row.count(r"\{")
            closing = row.count(r"\}")
            if opening == closing:
                continue
            parts[index] = row.replace(r"\{", r"\text{\{}").replace(
                r"\}", r"\text{\}}"
            )
            replacements += opening + closing
        return match.group(1) + "".join(parts) + match.group(3)

    return environment_pattern.sub(replace_environment, source), replacements


def _normalize_quotient_relation(source: str) -> tuple[str, int]:
    r"""Give LaTeXML an explicit atom type for quotient notation ``/\sim``."""
    source, count = re.subn(r"/\s*\\sim\b", r"/\\mathord{\\sim}", source)
    source, bowtie_count = re.subn(
        r"/\\!\\bowtie\b", r"\\mathbin{/\\!\\bowtie}", source
    )
    return source, count + bowtie_count


def _normalize_legacy_math_punctuation(source: str) -> tuple[str, int]:
    r"""Disambiguate old but visibly clear punctuation in a temporary copy."""
    replacements = 0
    source, count = re.subn(
        r"\\newcommand\{\\card\}\{\\text\{\{\\rm card\}\}\}",
        r"\\DeclareMathOperator{\\card}{card}",
        source,
    )
    replacements += count
    source, count = re.subn(r"(?<=[A-Za-z]),\s*(?=:[A-Za-z\\])", "", source)
    replacements += count
    source, count = re.subn(
        r"(?<=\))\.(?=[A-Za-z\\])", r"\\mathbin{.}", source
    )
    replacements += count
    source, count = re.subn(
        r"GL\(([^()\n]*?)\.\s*(\\mathbb\{[^{}]+\})\)",
        r"GL(\1,\2)",
        source,
    )
    replacements += count
    return source, replacements


def _normalize_bigtriangleup_symbol(source: str) -> tuple[str, int]:
    r"""Prevent LaTeXML from treating ``\bigtriangleup`` as addition."""
    return re.subn(
        r"(?<!\\mathord\{)\\bigtriangleup(?![A-Za-z@])",
        r"\\mathord{\\bigtriangleup}",
        source,
    )


def _normalize_left_exponent_function_space(source: str) -> tuple[str, int]:
    r"""Rewrite function-space notation ``{}^{A}B`` as equivalent ``B^{A}``."""
    marker = "{}^{"
    output = []
    cursor = 0
    replacements = 0
    while True:
        start = source.find(marker, cursor)
        if start < 0:
            output.append(source[cursor:])
            break
        output.append(source[cursor:start])
        exponent_start = start + len(marker)
        depth = 1
        exponent_end = exponent_start
        while exponent_end < len(source) and depth:
            character = source[exponent_end]
            escaped = exponent_end > 0 and source[exponent_end - 1] == "\\"
            if not escaped and character == "{":
                depth += 1
            elif not escaped and character == "}":
                depth -= 1
            exponent_end += 1
        if depth:
            output.append(source[start:])
            break
        base_start = exponent_end
        while base_start < len(source) and source[base_start].isspace():
            base_start += 1
        if base_start >= len(source):
            output.append(source[start:exponent_end])
            cursor = exponent_end
            continue
        if source[base_start] == "\\":
            match = re.match(r"\\(?:[A-Za-z@]+|.)", source[base_start:])
            base_end = base_start + len(match.group(0)) if match else base_start
        elif source[base_start] == "{":
            base_depth = 1
            base_end = base_start + 1
            while base_end < len(source) and base_depth:
                character = source[base_end]
                escaped = base_end > 0 and source[base_end - 1] == "\\"
                if not escaped and character == "{":
                    base_depth += 1
                elif not escaped and character == "}":
                    base_depth -= 1
                base_end += 1
            if base_depth:
                output.append(source[start:exponent_end])
                cursor = exponent_end
                continue
        else:
            base_end = base_start + 1
        if base_end < len(source) and source[base_end] == "_":
            subscript_end = base_end + 1
            if subscript_end < len(source) and source[subscript_end] == "{":
                subscript_depth = 1
                subscript_end += 1
                while subscript_end < len(source) and subscript_depth:
                    character = source[subscript_end]
                    escaped = subscript_end > 0 and source[subscript_end - 1] == "\\"
                    if not escaped and character == "{":
                        subscript_depth += 1
                    elif not escaped and character == "}":
                        subscript_depth -= 1
                    subscript_end += 1
                if not subscript_depth:
                    base_end = subscript_end
            elif subscript_end < len(source):
                base_end = subscript_end + 1
        exponent = source[exponent_start : exponent_end - 1]
        base = source[base_start:base_end]
        output.append(f"{base}^{{{exponent}}}")
        replacements += 1
        cursor = base_end
    return "".join(output), replacements


def _normalize_norm_delimiters(source: str) -> tuple[str, int]:
    r"""Give paired norm delimiters explicit left and right semantics."""
    replacements = 0
    lines = []
    for line in source.splitlines(keepends=True):
        delimiters = list(re.finditer(r"\\[lr]Vert", line))
        if (
            delimiters
            and len(delimiters) % 2 == 0
            and delimiters[0].group(0) == r"\rVert"
        ):
            delimiter_index = 0

            def alternate_delimiter(_match: re.Match[str]) -> str:
                nonlocal delimiter_index
                value = r"\lVert" if delimiter_index % 2 == 0 else r"\rVert"
                delimiter_index += 1
                return value

            line = re.sub(r"\\[lr]Vert", alternate_delimiter, line)
            replacements += len(delimiters) // 2
        lines.append(line)
    source = "".join(lines)
    patterns = (
        re.compile(r"\\lVert((?:(?!\\[lr]Vert)[^$\n])*?)\\lVert"),
        re.compile(r"(?<!\|)\|\|([^|$\n]*?)\|\|(?!\|)"),
    )
    for pattern in patterns:
        source, count = pattern.subn(r"\\lVert \1\\rVert", source)
        replacements += count
    return source, replacements


def _normalize_absolute_value_placeholders(source: str) -> tuple[str, int]:
    r"""Give the common ``|\cdot|`` placeholder explicit delimiters."""
    return re.subn(
        r"(?<![A-Za-z0-9}\)])\|\s*\\cdot\s*\|",
        r"\\lvert\\cdot\\rvert ",
        source,
    )


def _normalize_empty_domain_maps(source: str) -> tuple[str, int]:
    r"""Keep visible ``f:\to Y`` notation while avoiding a missing operand.

    Several historical manuscripts visibly omit the domain.  It would be
    unsafe to invent one, so the temporary conversion copy groups only the
    function name, colon, and arrow into a single math atom.
    """
    return re.subn(
        r"(?<![A-Za-z@\\])([A-Za-z])\s*:\s*\\to\b",
        r"\\mathord{\1{:}\\to}",
        source,
    )


def _normalize_continuation_relations(source: str) -> tuple[str, int]:
    r"""Join an alignment row that continues the preceding equivalence."""
    return re.subn(
        r"(?m)\\\\\s*\n\s*(\\(?:iff|implies|Longleftright)\b)",
        r" \1",
        source,
    )


def _normalize_inverse_image_half_open_intervals(source: str) -> tuple[str, int]:
    r"""Mark mixed interval delimiters inside inverse images explicitly."""
    replacements = 0

    def open_closed(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return (
            r"f^{-1}(\mathopen{(}"
            + match.group("body")
            + r"\mathclose{]})"
        )

    def closed_open(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return (
            r"f^{-1}(\mathopen{[}"
            + match.group("body")
            + r"\mathclose{)})"
        )

    source = re.sub(
        r"f\^\{-1\}\(\((?P<body>[^$\n]*?)\]\)", open_closed, source
    )
    source = re.sub(
        r"f\^\{-1\}\(\[(?P<body>[^$\n]*?)\)\)", closed_open, source
    )
    return source, replacements


def _inject_latexml_compat_package(
    source: str, bibliographies: Iterable[Path]
) -> tuple[str, int]:
    r"""Load repository bindings in recursive bibliography conversion."""
    if not tuple(bibliographies) or r"\usepackage{dempa-compat}" in source:
        return source, 0
    pattern = re.compile(r"(\\documentclass(?:\[[^]]*\])?\{[^{}]+\})")
    return pattern.subn(r"\1\n\\usepackage{dempa-compat}", source, count=1)


def _normalize_sized_parentheses(source: str) -> tuple[str, int]:
    r"""Correct unambiguous left/right command typos around parentheses."""
    return re.subn(r"\\Bigr\(", r"\\Bigl(", source)


def _normalize_group_action_dots(source: str) -> tuple[str, int]:
    r"""Mark explicitly declared action dots as binary operators for LaTeXML.

    Some manuscripts deliberately write a group action as ``g.x`` (and an
    induced action as ``g..x``). TeX renders the periods, but LaTeXML assigns
    punctuation semantics to them and rejects the surrounding formula. Apply
    this only when the manuscript declares the notation, and only inside math.
    The protected manuscript is never rewritten.
    """
    if not re.search(r"\$g\.x\$\s*と書", source):
        return source, 0

    replacements = 0

    def normalize_region(match: re.Match[str]) -> str:
        nonlocal replacements
        region = match.group(0)
        region, double_count = re.subn(r"\.\.", r"\\mathbin{..}", region)
        region, single_count = re.subn(
            r"(?<=[A-Za-z}\)])\.(?=[A-Za-z(\\])",
            r"\\mathbin{.}",
            region,
        )
        replacements += double_count + single_count
        return region

    math_environment = re.compile(
        r"\\begin\{(?P<environment>align\*?|alignat\*?|equation\*?|"
        r"gather\*?|multline\*?|eqnarray\*?|flalign\*?)\}.*?"
        r"\\end\{(?P=environment)\}",
        re.DOTALL,
    )
    source = math_environment.sub(normalize_region, source)
    for pattern in (
        re.compile(r"\\\[.*?\\\]", re.DOTALL),
        re.compile(r"\\\(.*?\\\)", re.DOTALL),
        re.compile(r"(?<!\\)\$\$.*?(?<!\\)\$\$", re.DOTALL),
        re.compile(r"(?<!\\)\$(?!\$).*?(?<!\\)\$", re.DOTALL),
    ):
        source = pattern.sub(normalize_region, source)
    return source, replacements


def _normalize_group_map_display(source: str) -> tuple[str, int]:
    r"""Separate two juxtaposed group-operation maps into parseable rows."""
    original = (
        r"binary:G\times G\rightarrow G\ (x,y)\mapsto xy\ \ "
        r"inverse:G\rightarrow G\ x\mapsto x^{-1}"
    )
    replacement = (
        r"\begin{gathered}"
        r"\mathrm{binary}:G\times G\rightarrow G,\quad (x,y)\mapsto xy\\"
        r"\mathrm{inverse}:G\rightarrow G,\quad x\mapsto x^{-1}"
        r"\end{gathered}"
    )
    return source.replace(original, replacement), source.count(original)


def _normalize_empty_membership_before_condition(source: str) -> tuple[str, int]:
    r"""Remove a membership sign with no right operand before ``\mid``."""
    return re.subn(r"\\in\s*\\mid", r"\\mid", source)


def _normalize_nocite_all(
    source: str, bibliographies: Iterable[Path]
) -> tuple[str, int]:
    r"""Expand ``\nocite{*}`` because LaTeXML can omit uncited BibTeX rows."""
    keys = []
    key_pattern = re.compile(
        r"^\s*@(?:article|book|booklet|conference|inbook|incollection|"
        r"inproceedings|manual|mastersthesis|misc|phdthesis|proceedings|"
        r"techreport|unpublished)\s*[({]\s*([^,\s]+)\s*,",
        re.IGNORECASE | re.MULTILINE,
    )
    for bibliography in bibliographies:
        text = bibliography.read_text(encoding="utf-8", errors="replace")
        keys.extend(key_pattern.findall(text))
    keys = list(dict.fromkeys(keys))
    if not keys:
        return source, 0
    return re.subn(
        r"\\nocite\s*\{\s*\*\s*\}",
        r"\\nocite{" + ",".join(keys) + "}",
        source,
    )



