from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .math import convert_math


THEOREM_CLASSES = {
    "df": "定義", "definition": "定義", "prop": "命題", "proposition": "命題",
    "thm": "定理", "theorem": "定理", "lem": "補題", "lemma": "補題",
    "cor": "系", "corollary": "系", "exam": "例", "example": "例",
    "fact": "事実", "claim": "主張", "cau": "注意", "rmk": "注意", "remark": "注意",
}

RULE_DESCRIPTIONS = {
    "AST_PARAGRAPH": "Pandoc ParaをSATySFi段落へ変換した",
    "AST_STRONG": "Pandoc Strongを太字コマンドへ変換した",
    "AST_EMPH": "Pandoc Emphを強調コマンドへ変換した",
    "AST_MATH_INLINE": "インライン数式をSATySFi数式へ変換した",
    "AST_MATH_BREAK_OPPORTUNITY": "インライン数式の直前に安全な改行候補を追加した",
    "AST_MATH_DISPLAY": "別行立て数式をSATySFi数式へ変換した",
    "AST_REFERENCE": "Pandocが解決した参照をSATySFi相互参照へ変換した",
    "AST_CITATION": "Pandocが解決した引用を文献一覧と一致する番号へ変換した",
    "AST_BIBLIOGRAPHY": "Pandoc citeprocの文献一覧をSATySFi番号付き一覧へ変換した",
    "AST_EXTERNAL_LINK": "HTTP(S)リンクをSATySFi注釈リンクへ変換した",
    "AST_QUOTED": "Pandocの引用符付きインラインを引用符とともに保持した",
    "AST_FIGURE": "単一のローカル画像とキャプションをSATySFi図版へ変換した",
    "AST_TABLE": "結合のない単純な表とキャプションをSATySFi表へ変換した",
    "AST_TRANSPARENT_SPAN": "装飾属性のないPandoc Spanの内容を保持した",
    "BIBLIOGRAPHY_CITEPROC": "Pandoc citeprocでBibTeX文献一覧を中間表現へ展開した",
    "AST_THEOREM": "Pandocの定理Divを番号付き定理段落へ変換した",
    "AST_PROOF": "Pandocのproof Divを証明段落へ変換した",
    "AST_PROOF_CUSTOM_HEADING": "LaTeX proof環境のオプション題名を証明見出しとして保持した",
    "AST_SECTION": "Pandocのレベル1見出しを番号付きSATySFi見出しへ変換した",
    "AST_SECTION_UNNUMBERED": "Pandocのレベル1見出しを番号なしSATySFi見出しへ変換した",
    "AST_FOOTNOTE": "Pandoc NoteをSATySFi脚注へ変換した",
    "AST_BULLET_LIST": "箇条書きをSATySFi listingへ変換した",
    "AST_ORDERED_LIST": "番号付き箇条書きをSATySFi enumerateへ変換した",
    "MATH_NOT_IN": "LaTeXの否定包含記号をSATySFi命令へ変換した",
    "MATH_GE": "LaTeXの\\geをSATySFiの\\geqへ変換した",
    "MATH_LE": "LaTeXの\\leをSATySFiの\\leqへ変換した",
    "MATH_VAREPSILON": "LaTeXの\\varepsilonをSATySFiの\\epsilonへ変換した",
    "MATH_DFRAC": "LaTeXの\\dfracをSATySFiの\\fracへ変換した",
    "MATH_DELIMITER_SIZE": "SATySFiに不要な区切り記号のサイズ指定を除いた",
    "MATH_SPACING": "LaTeX固有の数式空白命令を正規化した",
    "MATH_SP_SUPERSCRIPT": "TeXのsp上付き命令を通常の上付きへ変換した",
    "MATH_BRACE": "集合の波括弧をSATySFi命令へ変換した",
    "MATH_TEXT": "数式内テキストをSATySFi命令へ変換した",
    "MATH_TEXT_NESTED_MATH_FLATTENED": "数式内テキストに入れ子になった単純数式を文字へ変換した",
    "MATH_FACTORIAL": "階乗記号を同梱SATySFi命令へ変換した",
    "MATH_BRACE_SCRIPT": "添字と上付き文字の引数を明示した",
    "MATH_ALIGN": "LaTeXのalign環境をSATySFiの整列数式へ変換した",
    "MATH_IFF": "LaTeXの\\iffをSATySFiの\\Longleftrightarrowへ変換した",
    "MATH_MID": "LaTeXの集合内区切りをSATySFiの\\midへ変換した",
    "MATH_NORM": "対になった二重縦線をSATySFiの\\normへ変換した",
    "MATH_ABSOLUTE_VALUE": "演算子境界にある対の縦線をSATySFiの\\absへ変換した",
    "MATH_BIG_OPERATOR_SCRIPTS": "大演算子の上下限を同梱SATySFi命令へ変換した",
    "MATH_BIG_OPERATOR_SUBSCRIPT": "大演算子の下限を同梱SATySFi命令へ変換した",
    "MATH_COMMAND_SUBSCRIPT": "引数なし数式命令の下付きを同梱SATySFi命令へ変換した",
    "MATH_COLON": "LaTeXの関係記号colonをSATySFiのcolon-relへ変換した",
    "MATH_ELL": "LaTeXのellを同梱SATySFi命令へ変換した",
    "MATH_EXP": "LaTeXのexpをSATySFiのローマン体へ変換した",
    "MATH_BAR": "波括弧で閉じたLaTeXのbarを同梱SATySFi上線命令へ変換した",
    "MATH_MATRIX_ARRAY": "丸括弧で囲まれた単純なLaTeX arrayをSATySFi行列へ変換した",
}


@dataclass
class ConversionResult:
    satysfi: str | None = None
    rules: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.satysfi is not None and not self.errors

    def applied(self, rule: str, count: int = 1) -> None:
        self.rules[rule] = self.rules.get(rule, 0) + count

    def rule_report(self) -> list[dict[str, Any]]:
        return [
            {
                "id": rule,
                "description": RULE_DESCRIPTIONS.get(rule, rule.replace("_", " ").lower()),
                "count": self.rules[rule],
            }
            for rule in sorted(self.rules)
        ]


def _escape_text(text: str) -> str:
    replacements = {"%": "％", "#": "＃", "{": "｛", "}": "｝", "<": "＜", ">": "＞", "\\": "＼"}
    return "".join(replacements.get(character, character) for character in text)


def _plain_inlines(nodes: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for node in nodes:
        kind = node.get("t")
        if kind == "Str":
            parts.append(str(node.get("c", "")))
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            parts.append(" ")
        elif kind in {"Strong", "Emph", "Span", "Quoted"}:
            content = node.get("c", [])
            if kind == "Span" and isinstance(content, list) and len(content) == 2:
                content = content[1]
            if kind == "Quoted" and isinstance(content, list) and len(content) == 2:
                content = content[1]
            parts.append(_plain_inlines(content))
        elif kind == "Math":
            parts.append(str(node.get("c", [{}, ""])[1]))
    return "".join(parts).strip()


class Renderer:
    def __init__(self, result: ConversionResult, citation_numbers: dict[str, str]) -> None:
        self.result = result
        self.citation_numbers = citation_numbers
        self.generated_label_count = 0
        self.section_count = 0
        self.figure_count = 0
        self.table_count = 0

    def inlines(
        self, nodes: list[dict[str, Any]], *, linkify_bare_urls: bool = True
    ) -> str:
        rendered: list[str] = []
        for node in nodes:
            kind = node.get("t")
            content = node.get("c")
            if kind == "Str":
                text = str(content)
                if linkify_bare_urls and re.fullmatch(r"https?://[^\s`]+", text):
                    rendered.append(r"\dempa-href(`" + text + "`){" + _escape_text(text) + "}")
                    self.result.applied("AST_EXTERNAL_LINK")
                else:
                    rendered.append(_escape_text(text))
            elif kind in {"Space", "SoftBreak", "LineBreak"}:
                rendered.append(" ")
            elif kind == "Strong":
                rendered.append(
                    r"\dempa-strong{"
                    + self.inlines(content, linkify_bare_urls=linkify_bare_urls) + "}"
                )
                self.result.applied("AST_STRONG")
            elif kind == "Emph":
                rendered.append(
                    r"\emph{"
                    + self.inlines(content, linkify_bare_urls=linkify_bare_urls) + "}"
                )
                self.result.applied("AST_EMPH")
            elif kind == "Quoted":
                quote_type, quote_content = content
                quote_name = quote_type.get("t")
                delimiters = {
                    "DoubleQuote": ("“", "”"),
                    "SingleQuote": ("‘", "’"),
                }.get(quote_name)
                if delimiters is None:
                    self.result.errors.append(f"AST_UNSUPPORTED_QUOTE_TYPE: {quote_name}")
                    continue
                opening, closing = delimiters
                rendered.append(
                    opening
                    + self.inlines(quote_content, linkify_bare_urls=linkify_bare_urls)
                    + closing
                )
                self.result.applied("AST_QUOTED")
            elif kind == "Span":
                attributes, span_content = content
                if attributes[0] or attributes[1] or attributes[2]:
                    self.result.errors.append(
                        "AST_UNSUPPORTED_SPAN_ATTRIBUTES: only attribute-free spans are supported"
                    )
                    continue
                rendered.append(
                    self.inlines(span_content, linkify_bare_urls=linkify_bare_urls)
                )
                self.result.applied("AST_TRANSPARENT_SPAN")
            elif kind == "Cite":
                citations, _display = content
                numbers: list[str] = []
                for citation in citations:
                    mode = citation.get("citationMode", {}).get("t")
                    if mode != "NormalCitation" or citation.get("citationPrefix") or citation.get("citationSuffix"):
                        self.result.errors.append(
                            "AST_UNSUPPORTED_CITATION_FORM: only plain citations are supported"
                        )
                        continue
                    citation_id = str(citation.get("citationId", ""))
                    number = self.citation_numbers.get(citation_id)
                    if not number:
                        self.result.errors.append(f"AST_UNRESOLVED_CITATION: {citation_id}")
                        continue
                    self.result.citations.append(citation_id)
                    numbers.append(number)
                if numbers:
                    rendered.append("[" + ", ".join(numbers) + "]")
                    self.result.applied("AST_CITATION")
            elif kind == "Math":
                math_type, source = content
                converted = convert_math(source)
                for rule, count in converted.rules.items():
                    self.result.applied(rule, count)
                self.result.errors.extend(converted.errors)
                if math_type.get("t") == "DisplayMath":
                    if converted.source.startswith(r"\align("):
                        rendered.append(converted.source)
                    else:
                        rendered.append(r"\eqn(${" + converted.source + "});")
                    self.result.applied("AST_MATH_DISPLAY")
                else:
                    break_opportunity = r"\fil;" if len(source.strip()) >= 12 else ""
                    rendered.append(break_opportunity + "${" + converted.source + "}")
                    self.result.applied("AST_MATH_INLINE")
                    if break_opportunity:
                        self.result.applied("AST_MATH_BREAK_OPPORTUNITY")
            elif kind == "Link":
                attributes, label, target = content
                key_values = dict(attributes[2])
                uri = str(target[0])
                if key_values.get("reference-type") == "ref" and uri.startswith("#"):
                    reference = key_values.get("reference") or uri[1:]
                    self.result.references.append(reference)
                    rendered.append(r"\ref(`" + reference + "`);")
                    self.result.applied("AST_REFERENCE")
                elif (
                    uri.startswith(("http://", "https://"))
                    and not attributes[0] and not attributes[1] and not attributes[2]
                    and "`" not in uri and "\n" not in uri
                ):
                    rendered.append(
                        r"\dempa-href(`" + uri + "`){"
                        + self.inlines(label, linkify_bare_urls=False) + "}"
                    )
                    self.result.applied("AST_EXTERNAL_LINK")
                else:
                    self.result.errors.append(
                        "AST_UNSUPPORTED_LINK: only internal references and plain HTTP(S) links are supported"
                    )
            elif kind == "Code":
                rendered.append(r"\code{" + _escape_text(str(content[1])) + "}")
            elif kind == "Note":
                if len(content) != 1 or content[0].get("t") not in {"Para", "Plain"}:
                    self.result.errors.append(
                        "AST_UNSUPPORTED_NOTE: only one-paragraph notes are supported"
                    )
                    continue
                rendered.append(r"\dempa-footnote{" + self.inlines(content[0].get("c", [])) + "}")
                self.result.applied("AST_FOOTNOTE")
            else:
                self.result.errors.append(f"AST_UNSUPPORTED_INLINE: {kind}")
        return "".join(rendered)

    @staticmethod
    def _strip_prefix(nodes: list[dict[str, Any]], expected: str) -> tuple[str, list[dict[str, Any]]]:
        if len(nodes) < 4 or nodes[0].get("t") != "Strong":
            return "", nodes
        heading = _plain_inlines(nodes[0].get("c", []))
        if not heading.startswith(expected):
            return "", nodes
        number = heading.removeprefix(expected).strip()
        cursor = 1
        if cursor < len(nodes) and nodes[cursor].get("t") == "Str" and nodes[cursor].get("c") == ".":
            cursor += 1
        while cursor < len(nodes) and nodes[cursor].get("t") in {"Space", "SoftBreak"}:
            cursor += 1
        body = nodes[cursor:]
        if body and body[-1].get("t") == "Emph":
            body = body[:-1] + body[-1].get("c", [])
        return number, body

    @staticmethod
    def _proof_heading_and_body(
        nodes: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        body = list(nodes)
        heading = [{"t": "Str", "c": "証明."}]
        custom_heading = False
        if body and body[0].get("t") == "Emph":
            pandoc_heading = list(body.pop(0).get("c", []))
            if _plain_inlines(pandoc_heading) not in {"Proof", "Proof."}:
                heading = pandoc_heading
                custom_heading = True
            while body and body[0].get("t") in {"Space", "SoftBreak"}:
                body.pop(0)
        return heading, body, custom_heading

    @staticmethod
    def _strip_qed(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        body = list(nodes)
        if body and body[-1].get("t") == "Str":
            trailing = str(body[-1].get("c", "")).replace("\u00a0", "").strip()
            if trailing in {"□", "◻", "◽"}:
                body.pop()
        return body

    def theorem(self, attributes: list[Any], blocks: list[dict[str, Any]], theorem_class: str) -> str:
        label = attributes[0]
        name = THEOREM_CLASSES[theorem_class]
        if not blocks or blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append(
                f"AST_THEOREM_SHAPE: {theorem_class} must start with a paragraph"
            )
            return ""
        if any(block.get("t") not in {"Para", "Plain", "OrderedList"} for block in blocks[1:]):
            self.result.errors.append(
                f"AST_THEOREM_SHAPE: {theorem_class} may contain paragraphs and ordered lists only"
            )
            return ""
        number, body = self._strip_prefix(blocks[0].get("c", []), name)
        if not number:
            self.result.errors.append(f"AST_THEOREM_NUMBER: number not found for {theorem_class}")
            return ""
        if label:
            if label in self.result.labels:
                self.result.errors.append(f"AST_DUPLICATE_LABEL: {label}")
            self.result.labels[label] = number
        else:
            self.generated_label_count += 1
            label = f"generated-statement-{self.generated_label_count}"
        heading = f"{name} {number}."
        self.result.applied("AST_THEOREM")
        rendered = [
            r"+p{\dempa-statement-label(`" + label + "`)(`" + number + "`){"
            + _escape_text(heading) + "} " + self.inlines(body) + "}"
        ]
        for block in blocks[1:]:
            kind = block.get("t")
            if kind in {"Para", "Plain"}:
                paragraph = self._unwrap_theorem_emphasis(block.get("c", []))
                rendered.append("+p{" + self.inlines(paragraph) + "}")
            else:
                rendered.append(self._list(block, unwrap_theorem_emphasis=True))
        return "\n".join(rendered)

    @staticmethod
    def _unwrap_theorem_emphasis(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(nodes) == 1 and nodes[0].get("t") == "Emph":
            return list(nodes[0].get("c", []))
        return list(nodes)

    def _list(self, node: dict[str, Any], *, unwrap_theorem_emphasis: bool = False) -> str:
        kind = node.get("t")
        content = node.get("c")
        items = content if kind == "BulletList" else content[1]
        rendered_items: list[str] = []
        for item in items:
            if len(item) != 1 or item[0].get("t") not in {"Para", "Plain"}:
                self.result.errors.append(
                    "AST_UNSUPPORTED_LIST_ITEM: only one-paragraph items are supported"
                )
                continue
            inlines = item[0].get("c", [])
            if unwrap_theorem_emphasis:
                inlines = self._unwrap_theorem_emphasis(inlines)
            rendered_items.append("* " + self.inlines(inlines))
        command = "listing" if kind == "BulletList" else "enumerate"
        self.result.applied("AST_BULLET_LIST" if kind == "BulletList" else "AST_ORDERED_LIST")
        return "+" + command + "{\n  " + "\n  ".join(rendered_items) + "\n}"

    def section(self, content: list[Any]) -> str:
        level, attributes, title = content
        label, classes, key_values = attributes
        if level != 1:
            self.result.errors.append(f"AST_UNSUPPORTED_HEADER_LEVEL: {level}")
            return ""
        unknown_classes = [name for name in classes if name != "unnumbered"]
        if unknown_classes or key_values:
            self.result.errors.append("AST_UNSUPPORTED_HEADER_ATTRIBUTES")
            return ""
        if not label:
            self.generated_label_count += 1
            label = f"generated-section-{self.generated_label_count}"
        rendered_title = self.inlines(title)
        if "unnumbered" in classes:
            self.result.applied("AST_SECTION_UNNUMBERED")
            return r"+dempa-section-unnumbered(`" + label + "`){" + rendered_title + "}"
        self.section_count += 1
        number = str(self.section_count)
        if label in self.result.labels:
            self.result.errors.append(f"AST_DUPLICATE_LABEL: {label}")
        self.result.labels[label] = number
        self.result.applied("AST_SECTION")
        return (
            r"+dempa-section(`" + label + "`)(`" + number + "`){" + rendered_title + "}"
        )

    def proof(self, blocks: list[dict[str, Any]]) -> str:
        if not blocks or any(block.get("t") not in {"Para", "Plain"} for block in blocks):
            self.result.errors.append("AST_PROOF_SHAPE: proof must contain paragraphs only")
            return ""
        paragraphs = [list(block.get("c", [])) for block in blocks]
        heading, paragraphs[0], custom_heading = self._proof_heading_and_body(paragraphs[0])
        paragraphs[-1] = self._strip_qed(paragraphs[-1])
        self.result.applied("AST_PROOF")
        if custom_heading:
            self.result.applied("AST_PROOF_CUSTOM_HEADING")
        rendered: list[str] = []
        for index, paragraph in enumerate(paragraphs):
            prefix = (
                r"\dempa-proof-heading{" + self.inlines(heading) + r"} \fil;"
                if index == 0 else ""
            )
            suffix = r" \dempa-qed;" if index == len(paragraphs) - 1 else ""
            rendered.append("+p{" + prefix + self.inlines(paragraph) + suffix + "}")
        return "\n".join(rendered)

    def bibliography(self, attributes: list[Any], blocks: list[dict[str, Any]]) -> str:
        label, classes, key_values = attributes
        allowed_classes = {"references", "csl-bib-body", "hanging-indent"}
        if not label or set(classes) - allowed_classes or key_values:
            self.result.errors.append("AST_UNSUPPORTED_BIBLIOGRAPHY_ATTRIBUTES")
            return ""
        rendered_items: list[str] = []
        seen: set[str] = set()
        for index, block in enumerate(blocks, start=1):
            if block.get("t") != "Div":
                self.result.errors.append("AST_UNSUPPORTED_BIBLIOGRAPHY_ENTRY")
                continue
            entry_attributes, entry_blocks = block.get("c", [[], []])
            entry_label, entry_classes, entry_key_values = entry_attributes
            if (
                not entry_label.startswith("ref-")
                or entry_classes != ["csl-entry"]
                or entry_key_values
                or len(entry_blocks) != 1
                or entry_blocks[0].get("t") not in {"Para", "Plain"}
            ):
                self.result.errors.append("AST_UNSUPPORTED_BIBLIOGRAPHY_ENTRY")
                continue
            citation_id = entry_label.removeprefix("ref-")
            if citation_id in seen or self.citation_numbers.get(citation_id) != str(index):
                self.result.errors.append(f"AST_BIBLIOGRAPHY_NUMBER_MISMATCH: {citation_id}")
                continue
            seen.add(citation_id)
            rendered_items.append("* " + self.inlines(entry_blocks[0].get("c", [])))
        if not rendered_items:
            self.result.errors.append("AST_EMPTY_BIBLIOGRAPHY")
            return ""
        self.result.applied("AST_BIBLIOGRAPHY")
        return (
            r"+dempa-section-unnumbered(`" + label + "`){参考文献}\n"
            "+enumerate{\n  " + "\n  ".join(rendered_items) + "\n}"
        )

    def figure(self, content: list[Any]) -> str:
        if not isinstance(content, list) or len(content) != 3:
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_SHAPE")
            return ""
        attributes, caption, body = content
        label, classes, key_values = attributes
        if label or classes or any(key != "latex-placement" for key, _ in key_values):
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_ATTRIBUTES")
            return ""
        placement = dict(key_values).get("latex-placement")
        if placement:
            self.result.warnings.append(
                f"FIGURE_PLACEMENT_NOT_PRESERVED: {placement}"
            )
        if not isinstance(caption, list) or len(caption) != 2 or caption[0] is not None:
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_CAPTION")
            return ""
        caption_blocks = caption[1]
        if len(caption_blocks) != 1 or caption_blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_CAPTION")
            return ""
        figure_blocks = body
        if len(figure_blocks) == 1 and figure_blocks[0].get("t") == "Div":
            wrapper_attributes, figure_blocks = figure_blocks[0].get("c", [[], []])
            if wrapper_attributes != ["", ["center"], []]:
                self.result.errors.append("AST_UNSUPPORTED_FIGURE_WRAPPER")
                return ""
        if len(figure_blocks) != 1 or figure_blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_BODY")
            return ""
        image_nodes = figure_blocks[0].get("c", [])
        if len(image_nodes) != 1 or image_nodes[0].get("t") != "Image":
            self.result.errors.append("AST_UNSUPPORTED_FIGURE_BODY")
            return ""
        image_attributes, alt, target = image_nodes[0].get("c", [[], [], []])
        source, title = target
        if image_attributes != ["", [], []] or alt or title:
            self.result.errors.append("AST_UNSUPPORTED_IMAGE_ATTRIBUTES")
            return ""
        if (
            not re.fullmatch(r"[A-Za-z0-9._-]+\.(?:jpe?g|png|pdf)", source, flags=re.IGNORECASE)
            or "`" in source
        ):
            self.result.errors.append(f"AST_UNSAFE_IMAGE_PATH: {source}")
            return ""
        self.result.images.append(source)
        self.result.warnings.append(
            f"IMAGE_SIZE_NORMALIZED: {source} is rendered at the converter default width"
        )
        self.result.applied("AST_FIGURE")
        self.figure_count += 1
        rendered_caption = self.inlines(caption_blocks[0].get("c", []))
        return (
            r"+p{\fil;\dempa-image(`" + source + r"`);\fil;}" + "\n"
            r"+p{\fil;図 " + str(self.figure_count) + "　" + rendered_caption + r"\fil;}"
        )

    def table(self, content: list[Any]) -> str:
        if not isinstance(content, list) or len(content) != 6:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_SHAPE")
            return ""
        attributes, caption, column_specs, head, bodies, foot = content
        if attributes != ["", [], []]:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_ATTRIBUTES")
            return ""
        if not isinstance(caption, list) or len(caption) != 2 or caption[0] is not None:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_CAPTION")
            return ""
        caption_blocks = caption[1]
        if len(caption_blocks) != 1 or caption_blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_CAPTION")
            return ""
        if not column_specs or any(
            not isinstance(spec, list)
            or len(spec) != 2
            or spec[0].get("t") not in {"AlignLeft", "AlignCenter", "AlignRight", "AlignDefault"}
            or spec[1].get("t") != "ColWidthDefault"
            for spec in column_specs
        ):
            self.result.errors.append("AST_UNSUPPORTED_TABLE_COLUMNS")
            return ""
        if head != [["", [], []], []] or foot != [["", [], []], []] or len(bodies) != 1:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_SECTIONS")
            return ""
        body_attributes, row_head_columns, intermediate_head, rows = bodies[0]
        if body_attributes != ["", [], []] or row_head_columns != 0 or intermediate_head:
            self.result.errors.append("AST_UNSUPPORTED_TABLE_SECTIONS")
            return ""
        rendered_rows: list[str] = []
        for row in rows:
            row_attributes, cells = row
            if row_attributes != ["", [], []] or len(cells) != len(column_specs):
                self.result.errors.append("AST_UNSUPPORTED_TABLE_ROW")
                continue
            rendered_cells: list[str] = []
            for cell in cells:
                cell_attributes, alignment, row_span, column_span, blocks = cell
                if (
                    cell_attributes != ["", [], []]
                    or alignment.get("t") != "AlignDefault"
                    or row_span != 1
                    or column_span != 1
                    or len(blocks) != 1
                    or blocks[0].get("t") not in {"Para", "Plain"}
                ):
                    self.result.errors.append("AST_UNSUPPORTED_TABLE_CELL")
                    continue
                rendered_cells.append("{" + self.inlines(blocks[0].get("c", [])) + "}")
            if len(rendered_cells) == len(column_specs):
                rendered_rows.append("[" + "; ".join(rendered_cells) + "]")
        if not rendered_rows:
            self.result.errors.append("AST_EMPTY_TABLE")
            return ""
        self.table_count += 1
        self.result.applied("AST_TABLE")
        self.result.warnings.append("TABLE_ALIGNMENT_NORMALIZED: column alignment is centered")
        rendered_caption = self.inlines(caption_blocks[0].get("c", []))
        return (
            r"+p{\fil;\dempa-table([" + "; ".join(rendered_rows) + r"]);\fil;}" + "\n"
            r"+p{\fil;表 " + str(self.table_count) + "　" + rendered_caption + r"\fil;}"
        )

    def block(self, node: dict[str, Any]) -> str:
        kind = node.get("t")
        content = node.get("c")
        if kind in {"Para", "Plain"}:
            self.result.applied("AST_PARAGRAPH")
            return "+p{" + self.inlines(content) + "}"
        if kind == "Div":
            attributes, blocks = content
            classes = attributes[1]
            if "references" in classes:
                return self.bibliography(attributes, blocks)
            theorem_class = next((name for name in classes if name in THEOREM_CLASSES), None)
            if theorem_class:
                return self.theorem(attributes, blocks, theorem_class)
            if "proof" in classes:
                return self.proof(blocks)
            self.result.errors.append(f"AST_UNSUPPORTED_DIV: {','.join(classes) or '(no class)'}")
            return ""
        if kind == "Header":
            return self.section(content)
        if kind == "Figure":
            return self.figure(content)
        if kind == "Table":
            return self.table(content)
        if kind in {"BulletList", "OrderedList"}:
            return self._list(node)
        self.result.errors.append(f"AST_UNSUPPORTED_BLOCK: {kind}")
        return ""


def _meta_inlines(meta_value: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not meta_value:
        return []
    if meta_value.get("t") == "MetaInlines":
        return meta_value.get("c", [])
    if meta_value.get("t") == "MetaList" and meta_value.get("c"):
        first = meta_value["c"][0]
        if first.get("t") == "MetaInlines":
            return first.get("c", [])
    return []


def _citation_numbers(blocks: list[dict[str, Any]]) -> dict[str, str]:
    numbers: dict[str, str] = {}
    for block in blocks:
        if block.get("t") != "Div":
            continue
        attributes, entries = block.get("c", [[], []])
        if "references" not in attributes[1]:
            continue
        for index, entry in enumerate(entries, start=1):
            if entry.get("t") != "Div":
                continue
            entry_label = entry.get("c", [["", [], []], []])[0][0]
            if entry_label.startswith("ref-"):
                numbers[entry_label.removeprefix("ref-")] = str(index)
    return numbers


def convert_document(document: dict[str, Any]) -> ConversionResult:
    result = ConversionResult()
    renderer = Renderer(result, _citation_numbers(document.get("blocks", [])))
    metadata = document.get("meta", {})
    title = renderer.inlines(_meta_inlines(metadata.get("title"))) or "SATySFi変換文書"
    author = renderer.inlines(_meta_inlines(metadata.get("author")))
    blocks = [renderer.block(block) for block in document.get("blocks", [])]
    for reference in sorted(set(result.references) - set(result.labels)):
        result.errors.append(f"AST_UNRESOLVED_REFERENCE: {reference}")
    if result.errors:
        return result
    indented = "\n".join("  " + line if line else "" for block in blocks for line in block.splitlines())
    result.satysfi = (
        "@require: stdja\n@require: itemize\n@import: dempa\n\n"
        "StdJa.document (|\n"
        f"  title = {{{title}}};\n  author = {{{author}}};\n"
        "  show-title = true;\n  show-toc = false;\n|) '<\n"
        f"{indented}\n>\n"
    )
    return result
