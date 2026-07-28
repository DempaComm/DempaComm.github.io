"""PDF and TikZ graphics preparation for LaTeXML conversion."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dempa_site.conversion.latexml_normalization import _without_tex_comments
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper
from dempa_site.paths import safe_relative_path

@dataclass(frozen=True)
class PreparedGraphic:
    source: str
    page: int
    output: str
    width: str


INCLUDE_GRAPHICS_PATTERN = re.compile(
    r"\\includegraphics\s*(?:\[(?P<options>[^]]*)\])?\s*\{(?P<source>[^{}]+)\}"
)
TIKZCD_PATTERN = re.compile(
    r"\\begin\{tikzcd\}(?:\[[^]]*\])?.*?\\end\{tikzcd\}", re.DOTALL
)
MISSING_IMAGE_PATTERN = re.compile(
    r'<img\b(?=[^>]*\bclass="[^"]*\bltx_missing_image\b)[^>]*>',
    re.IGNORECASE,
)
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


def _replace_tikzcd_environments(
    source: str, output_names: Iterable[str]
) -> tuple[str, int]:
    """Replace tikz-cd environments with already rendered image references."""
    names = iter(output_names)
    replacements = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal replacements
        try:
            name = next(names)
        except StopIteration as error:
            raise PaperToolError("tikz-cd図版の出力数が不足しています") from error
        replacements += 1
        return rf"\includegraphics{{{name}}}"

    converted = TIKZCD_PATTERN.sub(replace, source)
    try:
        next(names)
    except StopIteration:
        pass
    else:
        raise PaperToolError("tikz-cd図版の出力数が原稿より多くなっています")
    if replacements:
        converted = re.sub(
            r"\\usepackage(?:\[[^]]*\])?\{tikz-cd\}",
            r"\\usepackage{graphicx}",
            converted,
            count=1,
        )
    return converted, replacements


def _prepare_tikzcd_graphics(
    source_path: Path, source: str, target_dir: Path, timeout: int
) -> tuple[str, tuple[PreparedGraphic, ...]]:
    r"""Render every tikz-cd environment with TeX before LaTeXML runs.

    The full manuscript is compiled first so labels referenced inside diagrams
    retain their numbers. A standalone copy then emits one tightly cropped PDF
    page per diagram, which is rasterized for reliable browser display. The
    protected source is never rewritten.
    """
    diagrams = TIKZCD_PATTERN.findall(_without_tex_comments(source))
    if not diagrams:
        return source, ()
    required = {
        "platex": shutil.which("platex"),
        "pdflatex": shutil.which("pdflatex"),
        "pdftoppm": shutil.which("pdftoppm"),
    }
    missing = [name for name, executable in required.items() if executable is None]
    if missing:
        raise PaperToolError(
            "tikz-cd図版の描画に必要なコマンドがありません: "
            + ", ".join(missing)
        )

    with tempfile.TemporaryDirectory(prefix=".tikzcd-render-", dir=target_dir) as raw:
        workspace = Path(raw)
        full_source = workspace / "source.tex"
        full_source.write_text(source, encoding="utf-8")
        full_command = [
            required["platex"],
            "-halt-on-error",
            "-interaction=nonstopmode",
            f"-output-directory={workspace}",
            str(full_source),
        ]
        for _ in range(2):
            completed = subprocess.run(
                full_command,
                cwd=source_path.parent,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout)[-4000:]
                raise PaperToolError("tikz-cd原稿をコンパイルできません: " + detail)

        preamble = source.split(r"\begin{document}", 1)[0]
        preamble, class_count = re.subn(
            r"\\documentclass(?:\[[^]]*\])?\{[^{}]+\}",
            r"\\documentclass[border=4pt,multi=tikzcd]{standalone}",
            preamble,
            count=1,
        )
        if class_count != 1:
            raise PaperToolError("tikz-cd図版用のdocumentclassを準備できません")
        wrapper = workspace / "diagrams.tex"
        wrapper.write_text(
            preamble
            + r"\begin{document}"
            + "\n".join(diagrams)
            + r"\end{document}",
            encoding="utf-8",
        )
        full_aux = workspace / "source.aux"
        if full_aux.is_file():
            shutil.copy2(full_aux, workspace / "diagrams.aux")
        render_command = [
            required["pdflatex"],
            "-halt-on-error",
            "-interaction=nonstopmode",
            f"-output-directory={workspace}",
            str(wrapper),
        ]
        completed = subprocess.run(
            render_command,
            cwd=source_path.parent,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rendered_pdf = workspace / "diagrams.pdf"
        if completed.returncode != 0 or not rendered_pdf.is_file():
            detail = (completed.stderr or completed.stdout)[-4000:]
            raise PaperToolError("tikz-cd図版を分離描画できません: " + detail)
        completed = subprocess.run(
            [
                required["pdftoppm"],
                "-png",
                "-r",
                "192",
                str(rendered_pdf),
                str(workspace / "tikzcd"),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rendered = sorted(
            workspace.glob("tikzcd-*.png"),
            key=lambda path: int(re.search(r"-(\d+)\.png$", path.name).group(1)),
        )
        if completed.returncode != 0 or len(rendered) != len(diagrams):
            detail = (completed.stderr or completed.stdout)[-4000:]
            raise PaperToolError(
                f"tikz-cd図版数が一致しません: expected={len(diagrams)} "
                f"actual={len(rendered)} {detail}"
            )
        width = max(2, len(str(len(rendered))))
        output_names = []
        graphics = []
        for index, rendered_path in enumerate(rendered, start=1):
            output_name = f"tikzcd-{index:0{width}d}.png"
            shutil.copy2(rendered_path, target_dir / output_name)
            output_names.append(output_name)
            graphics.append(
                PreparedGraphic(
                    source=f"tikzcd environment {index}",
                    page=index,
                    output=output_name,
                    width="",
                )
            )
    converted, count = _replace_tikzcd_environments(source, output_names)
    if count != len(graphics):
        raise PaperToolError("tikz-cd図版の置換数が一致しません")
    return converted, tuple(graphics)


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


def _deduplicate_tikzcd_graphics(
    html_text: str, graphics: tuple[PreparedGraphic, ...], target_dir: Path
) -> str:
    """Point HTML at stable TikZ filenames and remove LaTeXML copies."""
    tikz_graphics = [
        graphic
        for graphic in graphics
        if graphic.source.startswith("tikzcd environment ")
    ]
    if not tikz_graphics:
        return html_text
    originals = {graphic.output for graphic in tikz_graphics}
    candidates: dict[str, list[Path]] = {}
    for path in target_dir.glob("*.png"):
        if path.name not in originals:
            candidates.setdefault(sha256_file(path), []).append(path)
    for graphic in tikz_graphics:
        original = target_dir / graphic.output
        if not original.is_file():
            continue
        copies = candidates.get(sha256_file(original), [])
        for copy in copies:
            html_text = html_text.replace(
                f'src="{html.escape(copy.name, quote=True)}"',
                f'src="{html.escape(graphic.output, quote=True)}"',
            )
            copy.unlink(missing_ok=True)
    return html_text


def _link_public_pdf_assets(
    html_text: str, paper: Paper, target_dir: Path
) -> str:
    """Link copied PDF resources to their manifest-protected paper files."""
    for entry in paper.files:
        if not entry.public or Path(entry.path).suffix.casefold() != ".pdf":
            continue
        relative = safe_relative_path(entry.path, PaperToolError)
        if relative.parent != Path("."):
            continue
        encoded = html.escape(relative.name, quote=True)
        html_text = html_text.replace(f'href="{encoded}"', f'href="../{encoded}"')
        copied = target_dir / relative.name
        copied.unlink(missing_ok=True)
    return html_text



