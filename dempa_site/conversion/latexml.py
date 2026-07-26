"""Run isolated LaTeXML trials without changing protected paper sources."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from dempa_site.dates import local_now_seconds
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path
from dempa_site.protection.privacy import privacy_findings


@dataclass(frozen=True)
class LaTeXMLTarget:
    paper_dir: Path
    paper: Paper
    source: Path
    category: str


@dataclass(frozen=True)
class PreparedGraphic:
    source: str
    page: int
    output: str
    width: str


INCLUDE_GRAPHICS_PATTERN = re.compile(
    r"\\includegraphics\s*(?:\[(?P<options>[^]]*)\])?\s*\{(?P<source>[^{}]+)\}"
)
MISSING_IMAGE_PATTERN = re.compile(
    r'<img\b(?=[^>]*\bclass="[^"]*\bltx_missing_image\b)[^>]*>',
    re.IGNORECASE,
)
SVG_PATTERN = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
DOCUMENT_TITLE_PATTERN = re.compile(
    r'<h1\b(?=[^>]*\bclass="[^"]*\bltx_title_document\b)[^>]*>(.*?)</h1>',
    re.IGNORECASE | re.DOTALL,
)
UNSAFE_SVG_PATTERNS = (
    ("script element", re.compile(r"<script\b", re.IGNORECASE)),
    ("event handler", re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)),
    (
        "external resource",
        re.compile(
            r"(?:href|xlink:href)\s*=\s*['\"]\s*(?:https?:|//|data:|javascript:)",
            re.IGNORECASE,
        ),
    ),
)


def _binding_files(root: Path) -> tuple[Path, ...]:
    binding_dir = root / "experiments" / "latexml-bindings"
    if not binding_dir.is_dir():
        return ()
    return tuple(sorted(binding_dir.glob("*.ltxml")))


def _blocking_reasons(
    *,
    status: str,
    warning_count: int,
    error_count: int,
    has_error_markup: bool,
    title_present: bool,
    conversion_date_visible: bool,
    missing_graphics: int,
    unsafe_svg_findings: list[str],
    findings: list[str],
) -> list[str]:
    reasons = []
    if status == "failed":
        reasons.append("HTMLを生成できませんでした")
    if warning_count:
        reasons.append(f"LaTeXML警告が{warning_count}件あります")
    if error_count:
        reasons.append(f"LaTeXMLエラーが{error_count}件あります")
    if has_error_markup:
        reasons.append("生成HTMLにltx_ERRORがあります")
    if not title_present:
        reasons.append("生成HTMLに原稿題名がありません")
    if not conversion_date_visible:
        reasons.append("生成HTMLにHTML変換日を表示できませんでした")
    if missing_graphics:
        reasons.append(f"生成HTMLに未変換の図版が{missing_graphics}件あります")
    if unsafe_svg_findings:
        reasons.append("生成SVGに公開を許可しない要素があります")
    if findings:
        reasons.append("生成HTMLの簡易個人情報検査に確認事項があります")
    return reasons


def svg_findings(html_text: str) -> tuple[int, list[str]]:
    """Count inline SVGs and report executable or externally loaded content."""
    fragments = SVG_PATTERN.findall(html_text)
    findings = []
    for index, fragment in enumerate(fragments, start=1):
        for label, pattern in UNSAFE_SVG_PATTERNS:
            if pattern.search(fragment):
                findings.append(f"inline SVG {index}: {label}")
    return len(fragments), findings


def has_document_title(html_text: str) -> bool:
    """Return whether LaTeXML emitted a non-empty document-title heading."""
    for fragment in DOCUMENT_TITLE_PATTERN.findall(html_text):
        plain_text = re.sub(r"<[^>]+>", "", fragment)
        if re.sub(r"\s+", " ", html.unescape(plain_text)).strip():
            return True
    return False


def _set_conversion_date(html_text: str, label: str) -> tuple[str, bool]:
    replacement = f'<div class="ltx_dates">HTML変換日：{label}</div>'
    date_pattern = re.compile(r'<div class="ltx_dates">.*?</div>', re.DOTALL)
    if date_pattern.search(html_text):
        return date_pattern.sub(replacement, html_text, count=1), True
    body_pattern = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
    if body_pattern.search(html_text):
        return body_pattern.sub(rf"\1\n{replacement}", html_text, count=1), True
    return html_text, False


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
    return re.subn(r"/\s*\\sim\b", r"/\\mathord{\\sim}", source)


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


def _effective_warning_lines(
    log_text: str, html_text: str, has_bibliographies: bool
) -> tuple[list[str], list[str]]:
    """Separate actionable warnings from a safe mixed-bibliography warning."""
    warnings = [
        line for line in log_text.splitlines() if line.startswith("Warning:")
    ]
    ignored = []
    if has_bibliographies and "ltx_missing_citation" not in html_text:
        for line in tuple(warnings):
            if line.startswith("Warning:expected:bibkeys "):
                warnings.remove(line)
                ignored.append(line)
    return warnings, ignored


def _prepare_pdf_graphics(
    source: Path, target_dir: Path, timeout: int
) -> tuple[PreparedGraphic, ...]:
    references = []
    other_graphics = []
    for match in INCLUDE_GRAPHICS_PATTERN.finditer(
        _without_tex_comments(source.read_text(encoding="utf-8", errors="replace"))
    ):
        relative = safe_relative_path(match.group("source"), PaperToolError)
        if relative.suffix.casefold() != ".pdf":
            other_graphics.append(str(relative))
            continue
        options = match.group("options") or ""
        page_match = re.search(r"(?:^|,)\s*page\s*=\s*(\d+)\s*(?:,|$)", options)
        page = int(page_match.group(1)) if page_match else 1
        width_match = re.search(
            r"(?:^|,)\s*width\s*=\s*([0-9.]+(?:cm|mm|in|pt|px|em|rem|%))\s*(?:,|$)",
            options,
        )
        width = width_match.group(1) if width_match else ""
        references.append((relative, page, width))
    if not references:
        return ()
    if other_graphics:
        raise PaperToolError(
            "PDFと他形式の図版が混在しているため自動画像化できません: "
            + ", ".join(other_graphics)
        )

    converter = shutil.which("pdftoppm")
    if converter is None:
        raise PaperToolError(
            "PDF図版のHTML変換にはpdftoppmが必要です。macOSでは `brew install poppler` で導入してください"
        )
    prepared_by_key: dict[tuple[Path, int], PreparedGraphic] = {}
    prepared = []
    for relative, page, width in references:
        key = (relative, page)
        graphic = prepared_by_key.get(key)
        if graphic is None:
            pdf_path = source.parent / relative
            if not pdf_path.is_file():
                raise PaperToolError(f"PDF図版がありません: {relative}")
            output_name = f"figure-{len(prepared_by_key) + 1:02d}-page-{page}.png"
            output_prefix = target_dir / output_name.removesuffix(".png")
            completed = subprocess.run(
                [
                    converter,
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-png",
                    "-r",
                    "144",
                    str(pdf_path),
                    str(output_prefix),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output_path = target_dir / output_name
            if completed.returncode != 0 or not output_path.is_file():
                detail = (completed.stderr or completed.stdout).strip()
                raise PaperToolError(
                    f"PDF図版をPNGへ変換できません: {relative} page={page} {detail}"
                )
            graphic = PreparedGraphic(str(relative), page, output_name, "")
            prepared_by_key[key] = graphic
        prepared.append(
            PreparedGraphic(graphic.source, graphic.page, graphic.output, width)
        )
    return tuple(prepared)


def _insert_prepared_graphics(
    html_text: str, graphics: tuple[PreparedGraphic, ...]
) -> tuple[str, int]:
    index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        if index >= len(graphics):
            return match.group(0)
        graphic = graphics[index]
        index += 1
        tag = match.group(0)
        tag = re.sub(
            r'src="[^"]*"',
            f'src="{html.escape(graphic.output, quote=True)}"',
            tag,
            count=1,
        )
        class_match = re.search(r'class="([^"]*)"', tag)
        if class_match:
            classes = [
                value
                for value in class_match.group(1).split()
                if value not in {"ltx_missing", "ltx_missing_image"}
            ]
            tag = (
                tag[: class_match.start(1)]
                + " ".join(classes)
                + tag[class_match.end(1) :]
            )
        width = html.escape(graphic.width, quote=True)
        sizing = f"width:{width};" if width else ""
        tag = tag[:-1] + f' style="{sizing}max-width:100%;height:auto">'
        return tag

    converted = MISSING_IMAGE_PATTERN.sub(replace, html_text)
    missing = len(MISSING_IMAGE_PATTERN.findall(converted))
    if index != len(graphics):
        missing += len(graphics) - index
    return converted, missing


def _tex_source(paper_dir: Path, paper: Paper) -> Path:
    if paper.build.root:
        root = safe_relative_path(paper.build.root, PaperToolError)
        if root.suffix.casefold() == ".tex":
            return paper_dir / root
    candidates = [
        paper_dir / safe_relative_path(entry.path, PaperToolError)
        for entry in paper.files
        if entry.role == "manuscript" and Path(entry.path).suffix.casefold() == ".tex"
    ]
    if not candidates:
        raise PaperToolError(f"LaTeXMLで変換できるTeX原稿がありません: {paper.slug}")
    return candidates[0]


def _bibliography_files(target: LaTeXMLTarget) -> tuple[Path, ...]:
    files = []
    for entry in target.paper.files:
        if (
            entry.public
            and entry.role == "bibliography"
            and Path(entry.path).suffix.casefold() == ".bib"
        ):
            candidate = target.paper_dir / safe_relative_path(
                entry.path, PaperToolError
            )
            if candidate.is_file():
                files.append(candidate)
    return tuple(files)


def configured_targets(
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    requested_slugs: Iterable[str] = (),
) -> tuple[LaTeXMLTarget, ...]:
    by_slug = {paper.slug: (path.parent, paper) for path, paper in papers}
    requested = tuple(requested_slugs)
    if requested:
        entries = [{"slug": slug, "category": "手動指定"} for slug in requested]
    else:
        config_path = root / "experiments" / "latexml-trial.json"
        if not config_path.is_file():
            raise PaperToolError(f"LaTeXML試験設定がありません: {config_path}")
        config = read_json(config_path)
        if config.get("schema_version") != 1 or not isinstance(config.get("papers"), list):
            raise PaperToolError(f"LaTeXML試験設定の形式が不正です: {config_path}")
        entries = config["papers"]
    slugs = [entry.get("slug", "") for entry in entries]
    if len(slugs) != len(set(slugs)):
        raise PaperToolError("LaTeXML試験対象の原稿番号が重複しています")
    missing = sorted(set(slugs) - set(by_slug))
    if missing:
        raise PaperToolError("LaTeXML試験対象が未登録です: " + ", ".join(missing))
    targets = []
    for entry in entries:
        slug = entry.get("slug")
        category = entry.get("category")
        if not isinstance(slug, str) or not isinstance(category, str) or not category.strip():
            raise PaperToolError("LaTeXML試験対象にはslugとcategoryが必要です")
        paper_dir, paper = by_slug[slug]
        targets.append(LaTeXMLTarget(paper_dir, paper, _tex_source(paper_dir, paper), category))
    return tuple(targets)


def unconverted_tex_slugs(
    papers: Iterable[tuple[Path, Paper]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return batch candidates, papers without TeX, and already converted papers."""
    candidates = []
    without_tex = []
    already_converted = []
    for manifest_path, paper in papers:
        if paper.html_version is not None:
            already_converted.append(paper.slug)
            continue
        try:
            source = _tex_source(manifest_path.parent, paper)
        except PaperToolError:
            without_tex.append(paper.slug)
            continue
        if not source.is_file():
            without_tex.append(paper.slug)
            continue
        candidates.append(paper.slug)
    return tuple(candidates), tuple(without_tex), tuple(already_converted)


def _tool_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--VERSION"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return (result.stdout or result.stderr).strip().splitlines()[0]


def run_latexml_trial(
    *,
    root: Path,
    papers: Iterable[tuple[Path, Paper]],
    output: Path,
    requested_slugs: Iterable[str] = (),
    timeout: int = 180,
    progress: Callable[[int, int, dict], None] | None = None,
) -> dict:
    executable = shutil.which("latexmlc")
    if executable is None:
        raise PaperToolError(
            "latexmlcが見つかりません。macOSでは `brew install latexml` で導入してから再実行してください"
        )
    if timeout < 10:
        raise PaperToolError("LaTeXMLのtimeoutは10秒以上にしてください")
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise PaperToolError(
            f"LaTeXML出力先が空ではありません: {output}（別の--outputを指定してください）"
        )
    output.mkdir(parents=True, exist_ok=True)
    conversion_time = local_now_seconds()
    conversion_date = conversion_time.date().isoformat()
    conversion_date_label = (
        f"{conversion_time.year}年{conversion_time.month}月{conversion_time.day}日"
    )
    targets = configured_targets(root, papers, requested_slugs)
    binding_files = _binding_files(root)
    binding_dir = binding_files[0].parent if binding_files else None
    results = []
    for position, target in enumerate(targets, start=1):
        target_dir = output / target.paper.slug
        target_dir.mkdir()
        destination = target_dir / "index.html"
        log = target_dir / "latexml.log"
        command = [
            executable,
            f"--destination={destination}",
            "--format=html5",
            "--presentationmathml",
            "--svg",
            "--nocomments",
            f"--timeout={timeout}",
            "--expire=-1",
            f"--log={log}",
        ]
        if binding_dir is not None:
            command.append(f"--path={binding_dir.resolve()}")
        bibliography_files = _bibliography_files(target)
        for bibliography in bibliography_files:
            command.append(f"--bibliography={bibliography.resolve()}")
        graphics: tuple[PreparedGraphic, ...] = ()
        missing_graphics = 0
        source_normalizations = []
        try:
            graphics = _prepare_pdf_graphics(target.source, target_dir, timeout)
            if graphics:
                command.append("--nographicimages")
            source_text = target.source.read_text(encoding="utf-8", errors="replace")
            normalized_source, normalization_count = _normalize_math_inside_text(
                source_text
            )
            normalized_source, brace_normalization_count = (
                _normalize_cross_row_braces(normalized_source)
            )
            normalized_source, quotient_normalization_count = (
                _normalize_quotient_relation(normalized_source)
            )
            normalized_source, triangle_normalization_count = (
                _normalize_bigtriangleup_symbol(normalized_source)
            )
            normalized_source, function_space_normalization_count = (
                _normalize_left_exponent_function_space(normalized_source)
            )
            normalized_source, norm_delimiter_normalization_count = (
                _normalize_norm_delimiters(normalized_source)
            )
            normalized_source, sized_parenthesis_normalization_count = (
                _normalize_sized_parentheses(normalized_source)
            )
            normalized_source, group_action_dot_normalization_count = (
                _normalize_group_action_dots(normalized_source)
            )
            normalized_source, group_map_display_normalization_count = (
                _normalize_group_map_display(normalized_source)
            )
            normalized_source, empty_membership_normalization_count = (
                _normalize_empty_membership_before_condition(normalized_source)
            )
            normalized_source, nocite_normalization_count = _normalize_nocite_all(
                normalized_source, bibliography_files
            )
            conversion_source = target.source
            temporary_source = None
            if (
                normalization_count
                or brace_normalization_count
                or quotient_normalization_count
                or triangle_normalization_count
                or function_space_normalization_count
                or norm_delimiter_normalization_count
                or sized_parenthesis_normalization_count
                or group_action_dot_normalization_count
                or group_map_display_normalization_count
                or empty_membership_normalization_count
                or nocite_normalization_count
            ):
                temporary_source = target_dir / ".latexml-normalized.tex"
                temporary_source.write_text(normalized_source, encoding="utf-8")
                conversion_source = temporary_source
            if normalization_count:
                source_normalizations.append(
                    {
                        "kind": "math-inside-text",
                        "count": normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if brace_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "cross-row-braces",
                        "count": brace_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if quotient_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "quotient-relation",
                        "count": quotient_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if triangle_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "bigtriangleup-symbol",
                        "count": triangle_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if function_space_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "left-exponent-function-space",
                        "count": function_space_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if norm_delimiter_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "norm-delimiters",
                        "count": norm_delimiter_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if sized_parenthesis_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "sized-parentheses",
                        "count": sized_parenthesis_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if group_action_dot_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "group-action-dots",
                        "count": group_action_dot_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if group_map_display_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "group-map-display",
                        "count": group_map_display_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if empty_membership_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "empty-membership-before-condition",
                        "count": empty_membership_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            if nocite_normalization_count:
                source_normalizations.append(
                    {
                        "kind": "nocite-all",
                        "count": nocite_normalization_count,
                        "scope": "temporary-conversion-copy",
                    }
                )
            command.append(str(conversion_source))
            try:
                completed = subprocess.run(
                    command,
                    cwd=target.paper_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 30,
                    check=False,
                )
            finally:
                if temporary_source is not None:
                    temporary_source.unlink(missing_ok=True)
            log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            error_count = sum(line.startswith("Error:") for line in log_text.splitlines())
            html_text = (
                destination.read_text(encoding="utf-8", errors="replace")
                if destination.is_file()
                else ""
            )
            html_text, missing_graphics = _insert_prepared_graphics(
                html_text, graphics
            )
            html_text, conversion_date_visible = _set_conversion_date(
                html_text, conversion_date_label
            )
            if destination.is_file():
                destination.write_text(html_text, encoding="utf-8")
            warning_lines, ignored_warnings = _effective_warning_lines(
                log_text, html_text, bool(bibliography_files)
            )
            warning_count = len(warning_lines)
            inline_svg_count, unsafe_svg_findings = svg_findings(html_text)
            has_error_markup = "ltx_ERROR" in html_text
            title_present = has_document_title(html_text)
            findings = privacy_findings(html_text, "html")
            if not destination.is_file() or completed.returncode != 0:
                status = "failed"
            elif error_count or has_error_markup:
                status = "partial"
            elif warning_count:
                status = "generated-with-warnings"
            else:
                status = "generated"
            error = "" if status != "failed" else (completed.stderr or completed.stdout)[-4000:]
        except (PaperToolError, subprocess.TimeoutExpired) as exception:
            status = "failed"
            error = (
                str(exception)
                if isinstance(exception, PaperToolError)
                else f"Python側の制限時間を超過しました: {exception}"
            )
            warning_count = 0
            error_count = 0
            has_error_markup = False
            title_present = False
            conversion_date_visible = False
            missing_graphics = len(graphics)
            inline_svg_count = 0
            unsafe_svg_findings = []
            findings = []
            ignored_warnings = []
        blocking_reasons = _blocking_reasons(
            status=status,
            warning_count=warning_count,
            error_count=error_count,
            has_error_markup=has_error_markup,
            title_present=title_present,
            conversion_date_visible=conversion_date_visible,
            missing_graphics=missing_graphics,
            unsafe_svg_findings=unsafe_svg_findings,
            findings=findings,
        )
        results.append(
            {
                "slug": target.paper.slug,
                "title": target.paper.title,
                "category": target.category,
                "source": str(target.source.relative_to(target.paper_dir)),
                "source_sha256": sha256_file(target.source),
                "status": status,
                "html": f"{target.paper.slug}/index.html" if destination.is_file() else "",
                "log": f"{target.paper.slug}/latexml.log" if log.is_file() else "",
                "warning_count": warning_count,
                "error_count": error_count,
                "error_markup": has_error_markup,
                "title_present": title_present,
                "html_conversion_date": conversion_date,
                "html_conversion_date_visible": conversion_date_visible,
                "graphics": [
                    {
                        "source": graphic.source,
                        "page": graphic.page,
                        "output": f"{target.paper.slug}/{graphic.output}",
                        "converter": "pdftoppm",
                        "width": graphic.width,
                    }
                    for graphic in graphics
                ],
                "missing_graphics": missing_graphics,
                "inline_svg_count": inline_svg_count,
                "unsafe_svg_findings": unsafe_svg_findings,
                "source_normalizations": source_normalizations,
                "bibliographies": [
                    {
                        "source": str(path.relative_to(target.paper_dir)),
                        "sha256": sha256_file(path),
                    }
                    for path in bibliography_files
                ],
                "ignored_warnings": ignored_warnings,
                "privacy_findings": findings,
                "comments_removed": True,
                "automatic_checks_passed": not blocking_reasons,
                "blocking_reasons": blocking_reasons,
                "error": error,
            }
        )
        if progress is not None:
            progress(position, len(targets), results[-1])
    report = {
        "schema_version": 2,
        "generated_at": conversion_time.isoformat(timespec="seconds"),
        "tool": "LaTeXML",
        "version": _tool_version(executable),
        "publishable": False,
        "manual_review_required": True,
        "binding_files": [
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
            }
            for path in binding_files
        ],
        "manual_review_checklist": [
            "題名、著者名などに公開したくない情報がないか",
            "HTML変換日が実際の変換日と一致しているか",
            "日本語が欠落または文字化けしていないか",
            "数式、定理環境、番号、相互参照が元PDFと一致するか",
            "図版、引用、参考文献が欠落していないか",
            "元PDFと意味が変わっていないか",
        ],
        "results": results,
    }
    write_json(output / "report.json", report)
    return report
