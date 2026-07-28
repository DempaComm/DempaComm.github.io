"""Extract and publish an index of selected mathematical statements."""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page
from dempa_site.files import write_json
from dempa_site.manifests.model import Paper


KIND_LABELS = {
    "theorem": "定理",
    "definition": "定義",
    "proposition": "命題",
    "counterexample": "反例",
}
KIND_ORDER = tuple(KIND_LABELS)
_CLASS_KINDS = {
    "thm": "theorem",
    "theorem": "theorem",
    "df": "definition",
    "definition": "definition",
    "defnition": "definition",
    "prop": "proposition",
    "proposition": "proposition",
    "counterexample": "counterexample",
}


@dataclass(frozen=True)
class IndexedStatement:
    identifier: str
    kind: str
    title: str
    paper_slug: str
    paper_title: str
    href: str
    source: str


def _kind_from_title(title: str, fallback: str = "") -> str:
    compact = title.lstrip()
    for kind, label in KIND_LABELS.items():
        if compact.startswith(label):
            return kind
    return fallback


class _StatementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.statements: list[tuple[str, str, str]] = []
        self._candidate: tuple[str, str] | None = None
        self._capturing_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "div" and "ltx_theorem" in classes:
            fallback = ""
            for class_name in classes:
                if class_name.startswith("ltx_theorem_"):
                    fallback = _CLASS_KINDS.get(
                        class_name.removeprefix("ltx_theorem_"), fallback
                    )
            self._candidate = (attributes.get("id", ""), fallback)
        elif (
            tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
            and self._candidate is not None
            and "ltx_title_theorem" in classes
        ):
            self._capturing_title = True
            self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            return
        if not self._capturing_title or self._candidate is None:
            return
        identifier, fallback = self._candidate
        title = " ".join("".join(self._title_parts).split())
        kind = _kind_from_title(title, fallback)
        if identifier and title and kind in KIND_LABELS:
            self.statements.append((identifier, kind, title))
        self._candidate = None
        self._capturing_title = False
        self._title_parts = []


def _automatic_statements(manifest_path: Path, paper: Paper) -> list[IndexedStatement]:
    version = paper.html_version
    if version is None:
        return []
    source = manifest_path.parent / version.path
    parser = _StatementParser()
    parser.feed(source.read_text(encoding="utf-8"))
    base = f"../papers/{paper.slug}/{version.path}"
    return [
        IndexedStatement(
            identifier=identifier,
            kind=kind,
            title=title,
            paper_slug=paper.slug,
            paper_title=paper.title,
            href=f"{base}#{identifier}",
            source="automatic",
        )
        for identifier, kind, title in parser.statements
    ]


@lru_cache(maxsize=8)
def indexed_statements(catalog: SiteCatalog) -> tuple[IndexedStatement, ...]:
    """Combine LaTeXML extraction with explicit manifest overrides."""
    result: list[IndexedStatement] = []
    for manifest_path, paper in catalog.selected:
        by_id = {
            item.identifier: item
            for item in _automatic_statements(manifest_path, paper)
        }
        version = paper.html_version
        base = f"../papers/{paper.slug}/"
        if version is not None:
            base += version.path
        for statement in paper.statements:
            if statement.kind not in KIND_LABELS:
                continue
            anchor = statement.anchor
            href = anchor if anchor.startswith(("/", "http://", "https://")) else base + anchor
            by_id[statement.identifier] = IndexedStatement(
                identifier=statement.identifier,
                kind=statement.kind,
                title=statement.title,
                paper_slug=paper.slug,
                paper_title=paper.title,
                href=href,
                source="manual",
            )
        if "反例" in paper.tags and not any(
            item.kind == "counterexample" for item in by_id.values()
        ):
            by_id["tag-counterexample"] = IndexedStatement(
                identifier="tag-counterexample",
                kind="counterexample",
                title=f"反例を扱う原稿：{paper.title}",
                paper_slug=paper.slug,
                paper_title=paper.title,
                href=base,
                source="tag",
            )
        result.extend(by_id.values())
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return tuple(
        sorted(
            result,
            key=lambda item: (
                order[item.kind], item.paper_slug, item.identifier
            ),
        )
    )


def _render_statement(item: IndexedStatement, prefix: str) -> str:
    source_labels = {
        "manual": "手動登録",
        "automatic": "HTMLから抽出",
        "tag": "反例タグから補完",
    }
    source = source_labels[item.source]
    href = item.href
    if href.startswith("../"):
        href = prefix + href.removeprefix("../")
    return f"""        <li id="statement-{html.escape(item.paper_slug, quote=True)}-{html.escape(item.identifier, quote=True)}" data-kind="{item.kind}" data-year="{item.paper_slug[:4]}" data-paper="{html.escape(item.paper_slug, quote=True)}">
          <a href="{html.escape(href, quote=True)}">{html.escape(item.title)}</a>
          <span><a href="{prefix}papers/{html.escape(item.paper_slug, quote=True)}/">{html.escape(item.paper_title)}</a> · {source}</span>
        </li>"""


def _statement_sections(
    statements: tuple[IndexedStatement, ...], prefix: str
) -> str:
    sections = []
    for kind, label in KIND_LABELS.items():
        matching = tuple(item for item in statements if item.kind == kind)
        if not matching:
            continue
        items = "\n".join(
            _render_statement(item, prefix) for item in matching
        )
        sections.append(
            f"""    <section class="statement-section" id="{kind}" aria-labelledby="{kind}-title">
      <div class="section-heading"><h2 id="{kind}-title">{label}</h2><p>{len(matching)}件</p></div>
      <ol class="statement-list">
{items}
      </ol>
    </section>"""
        )
    return "\n".join(sections)


def _filter_panel(
    statements: tuple[IndexedStatement, ...], *, fixed_kind: bool, fixed_year: bool
) -> str:
    years = sorted({item.paper_slug[:4] for item in statements}, reverse=True)
    year_options = "".join(
        f'<option value="{year}">{year}年</option>' for year in years
    )
    papers = sorted({(item.paper_slug, item.paper_title) for item in statements})
    paper_options = "".join(
        f'<option value="{html.escape(slug, quote=True)}">'
        f'{html.escape(title)}（{html.escape(slug)}）</option>'
        for slug, title in papers
    )
    kind_control = "" if fixed_kind else '<label>種類<select id="statement-kind"><option value="">すべて</option><option value="theorem">定理</option><option value="definition">定義</option><option value="proposition">命題</option><option value="counterexample">反例</option></select></label>'
    year_control = "" if fixed_year else f'<label>公開年<select id="statement-year"><option value="">すべて</option>{year_options}</select></label>'
    return f"""    <section class="statement-filter-panel" aria-labelledby="statement-filter-title">
      <div class="section-heading">
        <h2 id="statement-filter-title">索引を絞り込む</h2>
        <p>このページに含まれる項目を絞り込みます。</p>
      </div>
      <form id="statement-filter" class="statement-filter" role="search">
        <label>検索語<input id="statement-query" type="search" placeholder="定理名・原稿名"></label>
        {kind_control}
        {year_control}
        <label>原稿<select id="statement-paper"><option value="">すべて</option>{paper_options}</select></label>
        <button id="statement-reset" type="button">条件を消す</button>
      </form>
      <p id="statement-filter-status" class="statement-filter-status" role="status" aria-live="polite">{len(statements)}件を表示しています。</p>
    </section>"""


def _directory_card(href: str, number: str, title: str, count: int) -> str:
    return f'<a class="explore-card" href="{href}"><span class="section-number">{number}</span><strong>{title}</strong><span>{count}件</span></a>'


def generate_statements(catalog: SiteCatalog, output: Path) -> None:
    statements = indexed_statements(catalog)
    counts = {kind: sum(item.kind == kind for item in statements) for kind in KIND_ORDER}
    years = sorted({item.paper_slug[:4] for item in statements}, reverse=True)
    kind_cards = "\n".join(
        _directory_card(f"kinds/{kind}/", kind.upper(), label, counts[kind])
        for kind, label in KIND_LABELS.items()
    )
    year_cards = "\n".join(
        _directory_card(
            f"years/{year}/", year, f"{year}年",
            sum(item.paper_slug[:4] == year for item in statements),
        )
        for year in years
    )
    body = f"""    <section data-statement-directory aria-labelledby="statement-kind-title">
      <div class="section-heading"><h2 id="statement-kind-title">種類から選ぶ</h2><p>定理・定義・命題・反例ごとの索引です。</p></div>
      <div class="explore-grid statement-shortcuts">{kind_cards}</div>
    </section>
    <section aria-labelledby="statement-year-title">
      <div class="section-heading"><h2 id="statement-year-title">公開年から選ぶ</h2><p>原稿の初出年ごとの索引です。</p></div>
      <div class="explore-grid statement-year-directory">{year_cards}</div>
    </section>
    <section><p>LaTeXMLの主HTML版から自動抽出し、必要な項目は原稿メタデータで補正しています。</p></section>
    <script src="../statements.js" defer></script>"""
    target = output / "statements"
    target.mkdir(parents=True)
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="定理・定義・命題・反例索引",
            eyebrow="MATHEMATICAL STATEMENTS",
            description=f"{len(statements)}件の数学的記述を、種類と原稿からたどります。",
            canonical_path="/statements/",
            body=body,
            body_class="statements-page",
            current_navigation="statements",
        ),
        encoding="utf-8",
    )
    kinds_dir = target / "kinds"
    years_dir = target / "years"
    kinds_dir.mkdir()
    years_dir.mkdir()
    for kind, label in KIND_LABELS.items():
        subset = tuple(item for item in statements if item.kind == kind)
        page_body = (
            f'    <p class="breadcrumb"><a href="../../">定理等索引</a> / {label}</p>\n'
            + _filter_panel(subset, fixed_kind=True, fixed_year=False)
            + "\n"
            + _statement_sections(subset, "../../../")
            + '\n    <script src="../../../statements.js" defer></script>'
        )
        kind_dir = kinds_dir / kind
        kind_dir.mkdir()
        (kind_dir / "index.html").write_text(
            rendered_exploration_page(
                title=f"{label}索引", eyebrow="STATEMENT BY KIND",
                description=f"{label}として登録された{len(subset)}件を掲載します。",
                canonical_path=f"/statements/kinds/{kind}/", body=page_body,
                prefix="../../../", body_class="statements-page",
                current_navigation="statements",
            ), encoding="utf-8"
        )
    for year in years:
        subset = tuple(item for item in statements if item.paper_slug[:4] == year)
        page_body = (
            f'    <p class="breadcrumb"><a href="../../">定理等索引</a> / {year}年</p>\n'
            + _filter_panel(subset, fixed_kind=False, fixed_year=True)
            + "\n"
            + _statement_sections(subset, "../../../")
            + '\n    <script src="../../../statements.js" defer></script>'
        )
        year_dir = years_dir / year
        year_dir.mkdir()
        (year_dir / "index.html").write_text(
            rendered_exploration_page(
                title=f"{year}年の定理等索引", eyebrow="STATEMENT BY YEAR",
                description=f"{year}年公開の原稿から抽出した{len(subset)}件を掲載します。",
                canonical_path=f"/statements/years/{year}/", body=page_body,
                prefix="../../../", body_class="statements-page",
                current_navigation="statements",
            ), encoding="utf-8"
        )
    write_json(
        target / "statements.json",
        {
            "schema_version": 1,
            "counts": counts,
            "statements": [asdict(item) for item in statements],
        },
    )
