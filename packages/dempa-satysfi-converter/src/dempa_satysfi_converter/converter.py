from __future__ import annotations

from dataclasses import dataclass, field
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
    "AST_THEOREM": "Pandocの定理Divを番号付き定理段落へ変換した",
    "AST_PROOF": "Pandocのproof Divを証明段落へ変換した",
    "AST_BULLET_LIST": "箇条書きをSATySFi listingへ変換した",
    "AST_ORDERED_LIST": "番号付き箇条書きをSATySFi enumerateへ変換した",
    "MATH_NOT_IN": "LaTeXの否定包含記号をSATySFi命令へ変換した",
    "MATH_GE": "LaTeXの\\geをSATySFiの\\geqへ変換した",
    "MATH_DFRAC": "LaTeXの\\dfracをSATySFiの\\fracへ変換した",
    "MATH_DELIMITER_SIZE": "SATySFiに不要な区切り記号のサイズ指定を除いた",
    "MATH_SPACING": "LaTeX固有の数式空白命令を正規化した",
    "MATH_BRACE": "集合の波括弧をSATySFi命令へ変換した",
    "MATH_TEXT": "数式内テキストをSATySFi命令へ変換した",
    "MATH_TEXT_NESTED_MATH_FLATTENED": "数式内テキストに入れ子になった単純数式を文字へ変換した",
    "MATH_FACTORIAL": "階乗記号を同梱SATySFi命令へ変換した",
    "MATH_BRACE_SCRIPT": "添字と上付き文字の引数を明示した",
}


@dataclass
class ConversionResult:
    satysfi: str | None = None
    rules: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    references: list[str] = field(default_factory=list)

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
        elif kind in {"Strong", "Emph", "Span"}:
            content = node.get("c", [])
            if kind == "Span" and isinstance(content, list) and len(content) == 2:
                content = content[1]
            parts.append(_plain_inlines(content))
        elif kind == "Math":
            parts.append(str(node.get("c", [{}, ""])[1]))
    return "".join(parts).strip()


class Renderer:
    def __init__(self, result: ConversionResult) -> None:
        self.result = result
        self.generated_label_count = 0

    def inlines(self, nodes: list[dict[str, Any]]) -> str:
        rendered: list[str] = []
        for node in nodes:
            kind = node.get("t")
            content = node.get("c")
            if kind == "Str":
                rendered.append(_escape_text(str(content)))
            elif kind in {"Space", "SoftBreak", "LineBreak"}:
                rendered.append(" ")
            elif kind == "Strong":
                rendered.append(r"\dempa-strong{" + self.inlines(content) + "}")
                self.result.applied("AST_STRONG")
            elif kind == "Emph":
                rendered.append(r"\emph{" + self.inlines(content) + "}")
                self.result.applied("AST_EMPH")
            elif kind == "Math":
                math_type, source = content
                converted = convert_math(source)
                for rule, count in converted.rules.items():
                    self.result.applied(rule, count)
                self.result.errors.extend(converted.errors)
                if math_type.get("t") == "DisplayMath":
                    rendered.append(r"\math{" + converted.source + "}")
                    self.result.applied("AST_MATH_DISPLAY")
                else:
                    break_opportunity = r"\fil;" if len(source.strip()) >= 12 else ""
                    rendered.append(break_opportunity + "${" + converted.source + "}")
                    self.result.applied("AST_MATH_INLINE")
                    if break_opportunity:
                        self.result.applied("AST_MATH_BREAK_OPPORTUNITY")
            elif kind == "Link":
                attributes, _label, target = content
                key_values = dict(attributes[2])
                if key_values.get("reference-type") != "ref" or not target[0].startswith("#"):
                    self.result.errors.append("AST_UNSUPPORTED_LINK: only internal references are supported")
                    continue
                reference = key_values.get("reference") or target[0][1:]
                self.result.references.append(reference)
                rendered.append(r"\ref(`" + reference + "`);")
                self.result.applied("AST_REFERENCE")
            elif kind == "Code":
                rendered.append(r"\code{" + _escape_text(str(content[1])) + "}")
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
        if len(body) == 1 and body[0].get("t") == "Emph":
            body = body[0].get("c", [])
        return number, body

    @staticmethod
    def _strip_proof(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        body = list(nodes)
        if body and body[0].get("t") == "Emph" and _plain_inlines(body[0].get("c", [])).startswith("Proof"):
            body.pop(0)
            while body and body[0].get("t") in {"Space", "SoftBreak"}:
                body.pop(0)
        if body and body[-1].get("t") == "Str":
            trailing = str(body[-1].get("c", "")).replace("\u00a0", "").strip()
            if trailing in {"□", "◻", "◽"}:
                body.pop()
        return body

    def theorem(self, attributes: list[Any], blocks: list[dict[str, Any]], theorem_class: str) -> str:
        label = attributes[0]
        name = THEOREM_CLASSES[theorem_class]
        if len(blocks) != 1 or blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append(f"AST_THEOREM_SHAPE: {theorem_class} must contain one paragraph")
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
        return (
            r"+p{\dempa-statement-label(`" + label + "`)(`" + number + "`){"
            + _escape_text(heading) + "} " + self.inlines(body) + "}"
        )

    def proof(self, blocks: list[dict[str, Any]]) -> str:
        if len(blocks) != 1 or blocks[0].get("t") not in {"Para", "Plain"}:
            self.result.errors.append("AST_PROOF_SHAPE: proof must contain one paragraph")
            return ""
        body = self._strip_proof(blocks[0].get("c", []))
        self.result.applied("AST_PROOF")
        return r"+p{\dempa-proof-heading{証明.} " + self.inlines(body) + r" \dempa-qed;}"

    def block(self, node: dict[str, Any]) -> str:
        kind = node.get("t")
        content = node.get("c")
        if kind in {"Para", "Plain"}:
            self.result.applied("AST_PARAGRAPH")
            return "+p{" + self.inlines(content) + "}"
        if kind == "Div":
            attributes, blocks = content
            classes = attributes[1]
            theorem_class = next((name for name in classes if name in THEOREM_CLASSES), None)
            if theorem_class:
                return self.theorem(attributes, blocks, theorem_class)
            if "proof" in classes:
                return self.proof(blocks)
            self.result.errors.append(f"AST_UNSUPPORTED_DIV: {','.join(classes) or '(no class)'}")
            return ""
        if kind in {"BulletList", "OrderedList"}:
            items = content if kind == "BulletList" else content[1]
            rendered_items: list[str] = []
            for item in items:
                if len(item) != 1 or item[0].get("t") not in {"Para", "Plain"}:
                    self.result.errors.append("AST_UNSUPPORTED_LIST_ITEM: only one-paragraph items are supported")
                    continue
                rendered_items.append("* " + self.inlines(item[0].get("c", [])))
            command = "listing" if kind == "BulletList" else "enumerate"
            self.result.applied("AST_BULLET_LIST" if kind == "BulletList" else "AST_ORDERED_LIST")
            return "+" + command + "{\n  " + "\n  ".join(rendered_items) + "\n}"
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


def convert_document(document: dict[str, Any]) -> ConversionResult:
    result = ConversionResult()
    renderer = Renderer(result)
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
