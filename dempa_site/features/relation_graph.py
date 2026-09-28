"""Generate a dependency-free SVG graph from paper tags and explicit relations."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import log
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page
from dempa_site.features.paper_capabilities import paper_capabilities
from dempa_site.features.reading_paths import load_reading_paths
from dempa_site.features.statements import KIND_LABELS
from dempa_site.files import write_json


GENERIC_TAGS = frozenset({"数学", "すべて", "雑談", "僕のお気に入り", "論文メモ"})


GRAPH_ASSETS = {
    "graph.js": "relation_graph.js",
    "graph-model.js": "graph_model.js",
    "graph-dom.js": "graph_dom.js",
    "graph-state.js": "graph_state.js",
    "graph-view.js": "graph_view.js",
    "graph-inspector.js": "graph_inspector.js",
    "graph.css": "relation_graph.css",
}
GRAPH_SCRIPT_PATH = Path(__file__).with_name("relation_graph.js")
GROUPS = (
    ("topology", "位相・距離・幾何", "#b5a2ed"),
    ("analysis", "解析・測度・確率", "#e3b675"),
    ("algebra", "代数・組合せ", "#79ccbb"),
    ("other", "その他", "#9aa9c7"),
)


def _tag_connections(papers, tag_counts: Counter) -> dict:
    """Keep a sparse, deterministic set of shared-tag suggestions.

    Rare tags carry more weight. A suggestion is not a citation or a claimed
    prerequisite; cap its degree at four without dropping authored relations.
    """
    tags = {paper.slug: set(paper.tags) - GENERIC_TAGS for paper in papers}
    weights = {tag: 1 + log((len(papers) + 1) / (count + 1))
               for tag, count in tag_counts.items()}
    candidates = []
    for first, second in combinations(papers, 2):
        left, right = tags[first.slug], tags[second.slug]
        shared = left & right
        if not shared:
            continue
        score = round(sum(weights[tag] for tag in sorted(shared)) /
                      sum(weights[tag] for tag in sorted(left | right)), 9)
        key = tuple(sorted((first.slug, second.slug)))
        candidates.append((score, key, sorted(shared, key=lambda tag: (tag_counts[tag], tag))))
    degree = Counter()
    selected = {}
    for score, key, shared in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if all(degree[slug] < 4 for slug in key):
            selected[key] = (shared, round(score, 4))
            degree.update(key)
    return selected


def _graph_data(catalog: SiteCatalog) -> dict:
    papers = [paper for _, paper in catalog.selected]
    capabilities = paper_capabilities(catalog)
    reading_paths = load_reading_paths(catalog)
    tag_counts = Counter(tag for paper in papers for tag in paper.tags)
    suggestions = _tag_connections(papers, tag_counts)
    explicit: dict[tuple[str, str], set[str]] = {}
    for paper in papers:
        for relation in paper.relations:
            key = tuple(sorted((paper.slug, relation.target_slug)))
            explicit.setdefault(key, set()).add(relation.kind)

    path_edges: dict[tuple[str, str], set[str]] = {}
    path_memberships: dict[str, list[dict[str, str]]] = {}
    for reading_path in reading_paths:
        for step in reading_path.papers:
            path_memberships.setdefault(step.slug, []).append(
                {"slug": reading_path.slug, "title": reading_path.title}
            )
        for first, second in zip(reading_path.papers, reading_path.papers[1:]):
            key = tuple(sorted((first.slug, second.slug)))
            path_edges.setdefault(key, set()).add(reading_path.slug)

    edges = []
    for first, second in combinations(papers, 2):
        key = tuple(sorted((first.slug, second.slug)))
        explicit_kinds = sorted(explicit.get(key, ()))
        paths = sorted(path_edges.get(key, ()))
        suggested_tags, affinity = suggestions.get(key, ([], 0))
        if not suggested_tags and not explicit_kinds and not paths:
            continue
        edges.append(
            {
                "source": first.slug,
                "target": second.slug,
                "weight": 1 + affinity * 2 + len(explicit_kinds) * 3 + len(paths) * 2,
                "tags": suggested_tags,
                "explicit": explicit_kinds,
                "reading_paths": paths,
            }
        )
    return {
        "schema_version": 2,
        "statement_labels": KIND_LABELS,
        "groups": [{"id": key, "label": label, "color": color,
                    "count": sum((paper.math_section or "その他") == label for paper in papers)}
                   for key, label, color in GROUPS],
        "excluded_generic_tags": sorted(GENERIC_TAGS),
        "years": sorted({paper.year for paper in papers}, reverse=True),
        "tags": [
            {"name": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
            if tag not in GENERIC_TAGS
        ],
        "nodes": [
            {
                "slug": paper.slug,
                "title": paper.title,
                "summary": paper.summary,
                "year": paper.year,
                "order": paper.order,
                "math_section": paper.math_section or "その他",
                "group": next((key for key, label, _ in GROUPS if label == paper.math_section), "other"),
                "tags": list(paper.tags),
                "html_path": capabilities[paper.slug].html_path,
                "statement_counts": dict(capabilities[paper.slug].statement_counts),
                "statement_count": capabilities[paper.slug].statement_count,
                "correction_count": capabilities[paper.slug].correction_count,
                "reading_paths": path_memberships.get(paper.slug, []),
            }
            for paper in papers
        ],
        "edges": edges,
    }


def generate_relation_graph(catalog: SiteCatalog, output: Path) -> None:
    target = output / "graph"
    target.mkdir(parents=True)
    data = _graph_data(catalog)
    write_json(target / "paper-graph.json", data)
    for name, source in GRAPH_ASSETS.items():
        (target / name).write_bytes(Path(__file__).with_name(source).read_bytes())
    body = """    <section class="graph-explorer" aria-label="原稿のつながりを探索">
      <div class="graph-toolbar">
        <label class="graph-search"><span aria-hidden="true">⌕</span><span class="graph-sr">原稿名・タグ</span><input id="graph-query" type="search" placeholder="原稿名・タグを探す" autocomplete="off"></label>
        <p id="graph-count" role="status">関係図を読み込み中…</p>
        <button id="graph-expand" class="graph-icon-button" type="button" aria-label="関係図を広く表示" aria-expanded="false" title="広く表示">⛶</button>
      </div>
      <div class="graph-shell">
        <div class="graph-map">
          <div class="graph-map-heading"><span class="graph-map-label">KNOWLEDGE GRAPH</span><button id="graph-all" type="button" hidden>全体へ戻る ↗</button><p id="graph-context" hidden></p></div>
          <svg id="paper-graph" viewBox="0 0 1400 900" role="group" tabindex="0" aria-label="原稿関係図。矢印キーで移動、プラス・マイナスキーで拡大縮小" aria-describedby="graph-help"></svg>
          <div id="graph-empty" class="graph-empty-state" hidden><strong>一致する原稿がありません</strong><p>検索語や絞り込みを変えてみてください。</p><button id="graph-empty-reset" type="button">すべての原稿を表示</button></div>
          <div class="graph-map-bottom"><div id="graph-legend" aria-label="分野で絞り込む"></div>
            <div class="graph-map-tools" aria-label="関係図の表示操作">
              <button id="graph-motion" type="button" aria-label="配置の動きを止める" title="配置の動きを止める">Ⅱ</button>
              <button id="graph-zoom-out" type="button" aria-label="関係図を縮小" title="縮小">−</button><output id="graph-zoom-level" aria-label="表示倍率">100%</output><button id="graph-zoom-in" type="button" aria-label="関係図を拡大" title="拡大">＋</button>
              <button id="graph-view-reset" type="button" aria-label="全体が見える位置に戻す" title="全体が見える位置に戻す">⊙</button>
            </div>
          </div>
        </div>
        <aside class="graph-sidebar" aria-label="表示条件と原稿の詳細">
          <details class="graph-settings"><summary>表示を調整<span aria-hidden="true">☷</span></summary>
            <div class="graph-settings-body">
              <label>タグ<select id="graph-tag"><option value="">すべてのタグ</option></select></label>
              <div class="graph-select-pair"><label>公開年<select id="graph-year"><option value="">すべての年</option></select></label><label>公開内容<select id="graph-content"><option value="">指定なし</option><option value="html">HTML版あり</option><option value="statements">定理等あり</option><option value="corrections">訂正・追記あり</option></select></label></div>
              <fieldset><legend>表示する線</legend><label class="graph-check"><input id="graph-tags" type="checkbox" checked><span class="graph-line-key tags"></span>共通タグ</label><label class="graph-check"><input id="graph-paths" type="checkbox" checked><span class="graph-line-key paths"></span>読書経路</label><label class="graph-check"><input id="graph-explicit" type="checkbox" checked><span class="graph-line-key explicit"></span>明示された関係</label></fieldset>
              <label class="graph-check"><input id="graph-orphans" type="checkbox" checked>線のない原稿も表示</label>
              <label>原稿名<select id="graph-labels"><option value="auto">拡大に合わせて表示</option><option value="all">すべて表示</option><option value="none">選択した原稿だけ</option></select></label>
              <label>配置の広がり<input id="graph-spacing" type="range" min="70" max="160" value="100"></label>
              <div class="graph-pan-controls" role="group" aria-label="関係図の表示位置"><button type="button" data-pan-x="-1" data-pan-y="0" aria-label="関係図の左側を見る">←</button><button type="button" data-pan-x="0" data-pan-y="-1" aria-label="関係図の上側を見る">↑</button><button type="button" data-pan-x="0" data-pan-y="1" aria-label="関係図の下側を見る">↓</button><button type="button" data-pan-x="1" data-pan-y="0" aria-label="関係図の右側を見る">→</button></div>
              <button id="graph-reset" class="graph-text-button" type="button">表示条件をリセット</button>
            </div>
          </details>
          <section id="graph-detail" class="graph-inspector" aria-label="選んだ原稿"></section>
          <details class="graph-accessible-list"><summary>原稿の一覧 <span id="graph-list-count"></span></summary><ul id="graph-paper-list"></ul></details>
        </aside>
      </div>
      <div class="graph-caption"><p id="graph-help">点を選んで原稿を見る。ドラッグで移動、ホイールで拡大。Tab・Enterと表示ボタンでも操作できます。</p><details><summary>線の意味</summary><p>線は原稿間に登録された関係、読書経路で前後に並ぶ関係、共通タグを示します。共通タグの線は、珍しいタグの一致を重く見て各原稿につき最大4本を選びます。引用・前提関係を推定したものではありません。</p></details></div>
      <noscript><p>関係図の操作にはJavaScriptが必要です。<a href="../archive/">全原稿の一覧</a>からも原稿を探せます。</p></noscript>
    </section>
    <script src="graph.js" type="module"></script>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="原稿関係図",
            eyebrow="PAPER RELATION GRAPH",
            description="ひとつの原稿から、次の発見へ。数学のつながりをたどる。",
            canonical_path="/graph/",
            body=body,
            body_class="graph-page",
            extra_head='<link rel="stylesheet" href="graph.css">\n',
        ),
        encoding="utf-8",
    )
