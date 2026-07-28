"""Generate a dependency-free SVG graph from paper tags and explicit relations."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page
from dempa_site.features.paper_capabilities import paper_capabilities
from dempa_site.features.reading_paths import load_reading_paths
from dempa_site.files import write_json


GENERIC_TAGS = frozenset({"数学", "すべて", "雑談", "僕のお気に入り", "論文メモ"})


GRAPH_SCRIPT_PATH = Path(__file__).with_name("relation_graph.js")


def _graph_data(catalog: SiteCatalog) -> dict:
    papers = [paper for _, paper in catalog.selected]
    capabilities = paper_capabilities(catalog)
    reading_paths = load_reading_paths(catalog)
    tag_counts = Counter(tag for paper in papers for tag in paper.tags)
    meaningful = {
        paper.slug: set(paper.tags) - GENERIC_TAGS
        for paper in papers
    }
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
        shared = sorted(meaningful[first.slug] & meaningful[second.slug])
        key = tuple(sorted((first.slug, second.slug)))
        explicit_kinds = sorted(explicit.get(key, ()))
        paths = sorted(path_edges.get(key, ()))
        rare_tags = [tag for tag in shared if tag_counts[tag] <= 6]
        if not rare_tags and not explicit_kinds and not paths:
            continue
        edges.append(
            {
                "source": first.slug,
                "target": second.slug,
                "weight": max(1, len(rare_tags) + len(explicit_kinds) + len(paths)),
                "tags": rare_tags,
                "explicit": explicit_kinds,
                "reading_paths": paths,
            }
        )
    default_tag = "次元論" if "次元論" in tag_counts else next(
        (tag for tag, _ in tag_counts.most_common() if tag not in GENERIC_TAGS), ""
    )
    return {
        "schema_version": 1,
        "statement_labels": {
            "theorem": "定理",
            "definition": "定義",
            "proposition": "命題",
            "counterexample": "反例",
        },
        "excluded_generic_tags": sorted(GENERIC_TAGS),
        "default_tag": default_tag,
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
                "year": paper.year,
                "order": paper.order,
                "math_section": paper.math_section or "その他",
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
    (target / "graph.js").write_text(
        GRAPH_SCRIPT_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    body = """    <section aria-labelledby="graph-title">
      <aside class="graph-work-in-progress" aria-label="原稿関係図についてのお知らせ">
        <strong>原稿関係図は現在調整中です。</strong>
        <p>原稿同士の関係の選び方と、図の見せ方は今後変更することがあります。</p>
      </aside>
      <div class="section-heading">
        <h2 id="graph-title">意味のある関係をたどる</h2>
        <p>明示関係、読書経路での前後、希少タグだけを線にして、過密な図を避けます。</p>
      </div>
      <div class="graph-controls">
        <label>タグ<select id="graph-tag"><option value="">すべてのタグ</option></select></label>
        <label>公開年<select id="graph-year"><option value="">すべての年</option></select></label>
        <label>公開内容<select id="graph-content"><option value="">指定なし</option><option value="html">HTML版あり</option><option value="statements">定理等あり</option><option value="corrections">訂正・追記あり</option></select></label>
        <button id="graph-reset" type="button">条件を戻す</button>
      </div>
      <p id="graph-count" class="paper-count" aria-live="polite">関係図を読み込み中です</p>
      <div class="graph-view-controls" aria-label="関係図の表示操作">
        <button id="graph-zoom-in" type="button" aria-label="関係図を拡大">＋ 拡大</button>
        <button id="graph-zoom-out" type="button" aria-label="関係図を縮小">− 縮小</button>
        <button id="graph-view-reset" type="button">全体を表示</button>
        <span>余白をドラッグして移動、ホイールまたはボタンで拡大縮小できます。</span>
      </div>
      <div class="graph-canvas"><svg id="paper-graph" viewBox="0 0 1200 820" role="img" aria-label="タグを使った原稿関係図"></svg></div>
      <aside id="graph-detail" class="graph-detail" aria-live="polite"><p>図または一覧から原稿を選ぶと、HTML版や定理等への入口を表示します。</p></aside>
      <details class="graph-accessible-list">
        <summary>表示中の原稿を一覧で見る</summary>
        <ul id="graph-paper-list"></ul>
      </details>
      <p class="lineage-note">「数学」「雑談」など広すぎるタグは線の生成から除外しています。タグによる線は、そのタグを持つ原稿が6件以下の場合だけ生成します。</p>
    </section>
    <script src="graph.js" defer></script>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="原稿関係図",
            eyebrow="PAPER RELATION GRAPH",
            description="明示関係、読書経路、希少タグを使い、HTML本文や定理等へ進める図です。",
            canonical_path="/graph/",
            body=body,
            body_class="graph-page",
        ),
        encoding="utf-8",
    )
