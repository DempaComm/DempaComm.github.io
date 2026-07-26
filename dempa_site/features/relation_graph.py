"""Generate a dependency-free SVG graph from paper tags and explicit relations."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page
from dempa_site.files import write_json


GENERIC_TAGS = frozenset({"数学", "すべて", "雑談", "僕のお気に入り", "論文メモ"})


GRAPH_SCRIPT = r"""(() => {
  "use strict";
  const svg = document.querySelector("#paper-graph");
  const tagSelect = document.querySelector("#graph-tag");
  const yearSelect = document.querySelector("#graph-year");
  const count = document.querySelector("#graph-count");
  const list = document.querySelector("#graph-paper-list");
  const reset = document.querySelector("#graph-reset");
  const zoomIn = document.querySelector("#graph-zoom-in");
  const zoomOut = document.querySelector("#graph-zoom-out");
  const viewReset = document.querySelector("#graph-view-reset");
  const ns = "http://www.w3.org/2000/svg";
  const initialView = {x: 0, y: 0, width: 1200, height: 820};
  let view = {...initialView};
  let pan = null;
  const make = (name, attrs = {}) => {
    const element = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  };
  const shorten = (value, length = 14) => value.length > length ? `${value.slice(0, length)}…` : value;
  const applyView = () => svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
  const resetView = () => {
    view = {...initialView};
    applyView();
  };
  const changeZoom = (factor, clientX = null, clientY = null) => {
    const rect = svg.getBoundingClientRect();
    const ratioX = clientX === null ? 0.5 : (clientX - rect.left) / rect.width;
    const ratioY = clientY === null ? 0.5 : (clientY - rect.top) / rect.height;
    const nextWidth = Math.max(300, Math.min(2400, view.width * factor));
    const nextHeight = nextWidth * initialView.height / initialView.width;
    const anchorX = view.x + view.width * ratioX;
    const anchorY = view.y + view.height * ratioY;
    view = {
      x: anchorX - nextWidth * ratioX,
      y: anchorY - nextHeight * ratioY,
      width: nextWidth,
      height: nextHeight
    };
    applyView();
  };

  fetch("paper-graph.json")
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      data.tags.forEach(tag => {
        const option = document.createElement("option");
        option.value = tag.name;
        option.textContent = `${tag.name} (${tag.count})`;
        tagSelect.append(option);
      });
      data.years.forEach(year => {
        const option = document.createElement("option");
        option.value = String(year);
        option.textContent = `${year}年`;
        yearSelect.append(option);
      });
      if (data.default_tag) tagSelect.value = data.default_tag;

      const draw = () => {
        const selectedTag = tagSelect.value;
        const selectedYear = yearSelect.value;
        let nodes = data.nodes.filter(node =>
          (!selectedTag || node.tags.includes(selectedTag)) &&
          (!selectedYear || String(node.year) === selectedYear)
        );
        const total = nodes.length;
        nodes = nodes.sort((a, b) => b.order - a.order).slice(0, 60);
        const selected = new Set(nodes.map(node => node.slug));
        const edges = data.edges.filter(edge => selected.has(edge.source) && selected.has(edge.target));
        svg.replaceChildren();
        list.replaceChildren();
        count.textContent = total > 60 ? `${total}件中、新しい60件を表示` : `${total}件を表示`;

        if (!nodes.length) {
          const message = make("text", {x: 500, y: 360, "text-anchor": "middle", class: "graph-empty"});
          message.textContent = "条件に一致する原稿がありません";
          svg.append(message);
          return;
        }

        const positions = new Map();
        const centerX = 600;
        const centerY = 400;
        const radius = Math.min(350, 110 + nodes.length * 6);
        nodes.forEach((node, index) => {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index / nodes.length);
          const ring = nodes.length > 24 && index % 2 ? radius * 0.68 : radius;
          positions.set(node.slug, {
            x: centerX + Math.cos(angle) * ring,
            y: centerY + Math.sin(angle) * ring
          });
        });

        edges.forEach(edge => {
          const a = positions.get(edge.source);
          const b = positions.get(edge.target);
          const line = make("line", {
            x1: a.x, y1: a.y, x2: b.x, y2: b.y,
            class: edge.explicit.length ? "graph-edge graph-edge-explicit" : "graph-edge",
            "stroke-width": Math.min(5, 1 + edge.weight * 0.75)
          });
          const title = make("title");
          title.textContent = edge.explicit.length
            ? `明示関係: ${edge.explicit.join("、")} / 共通タグ: ${edge.tags.join("、")}`
            : `共通タグ: ${edge.tags.join("、")}`;
          line.append(title);
          svg.append(line);
        });

        nodes.forEach(node => {
          const position = positions.get(node.slug);
          const link = make("a", {href: `../papers/${node.slug}/`});
          const group = make("g", {class: "graph-node", transform: `translate(${position.x} ${position.y})`});
          const circle = make("circle", {r: 9});
          const label = make("text", {x: 13, y: 4});
          label.textContent = shorten(node.title);
          const title = make("title");
          title.textContent = `${node.title} (${node.year})`;
          group.append(circle, label, title);
          link.append(group);
          svg.append(link);

          const item = document.createElement("li");
          const itemLink = document.createElement("a");
          itemLink.href = `../papers/${node.slug}/`;
          itemLink.textContent = node.title;
          const meta = document.createElement("span");
          meta.textContent = `${node.year} / ${node.tags.join("・")}`;
          item.append(itemLink, meta);
          list.append(item);
        });
        resetView();
      };

      tagSelect.addEventListener("change", draw);
      yearSelect.addEventListener("change", draw);
      reset.addEventListener("click", () => {
        tagSelect.value = data.default_tag || "";
        yearSelect.value = "";
        draw();
      });
      zoomIn.addEventListener("click", () => changeZoom(0.8));
      zoomOut.addEventListener("click", () => changeZoom(1.25));
      viewReset.addEventListener("click", resetView);
      svg.addEventListener("wheel", event => {
        event.preventDefault();
        changeZoom(event.deltaY < 0 ? 0.86 : 1.16, event.clientX, event.clientY);
      }, {passive: false});
      svg.addEventListener("pointerdown", event => {
        if (event.target.closest(".graph-node")) return;
        pan = {pointerId: event.pointerId, x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y};
        svg.setPointerCapture(event.pointerId);
        svg.classList.add("is-panning");
      });
      svg.addEventListener("pointermove", event => {
        if (!pan || pan.pointerId !== event.pointerId) return;
        const rect = svg.getBoundingClientRect();
        view.x = pan.viewX - (event.clientX - pan.x) * view.width / rect.width;
        view.y = pan.viewY - (event.clientY - pan.y) * view.height / rect.height;
        applyView();
      });
      const endPan = event => {
        if (!pan || pan.pointerId !== event.pointerId) return;
        pan = null;
        svg.classList.remove("is-panning");
      };
      svg.addEventListener("pointerup", endPan);
      svg.addEventListener("pointercancel", endPan);
      draw();
    })
    .catch(error => {
      count.textContent = `関係図を読み込めませんでした: ${error.message}`;
    });
})();
"""


def _graph_data(catalog: SiteCatalog) -> dict:
    papers = [paper for _, paper in catalog.selected]
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

    edges = []
    for first, second in combinations(papers, 2):
        shared = sorted(meaningful[first.slug] & meaningful[second.slug])
        key = tuple(sorted((first.slug, second.slug)))
        explicit_kinds = sorted(explicit.get(key, ()))
        keep_tag_edge = len(shared) >= 2 or any(tag_counts[tag] <= 8 for tag in shared)
        if not keep_tag_edge and not explicit_kinds:
            continue
        edges.append(
            {
                "source": first.slug,
                "target": second.slug,
                "weight": max(1, len(shared)),
                "tags": shared,
                "explicit": explicit_kinds,
            }
        )
    default_tag = "次元論" if "次元論" in tag_counts else next(
        (tag for tag, _ in tag_counts.most_common() if tag not in GENERIC_TAGS), ""
    )
    return {
        "schema_version": 1,
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
    (target / "graph.js").write_text(GRAPH_SCRIPT, encoding="utf-8")
    body = """    <section aria-labelledby="graph-title">
      <div class="section-heading">
        <h2 id="graph-title">タグから見る近さ</h2>
        <p>線にマウスを重ねると共通タグが分かります。明示的な関係は主色の線で表示します。</p>
      </div>
      <div class="graph-controls">
        <label>タグ<select id="graph-tag"><option value="">すべてのタグ</option></select></label>
        <label>公開年<select id="graph-year"><option value="">すべての年</option></select></label>
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
      <details class="graph-accessible-list">
        <summary>表示中の原稿を一覧で見る</summary>
        <ul id="graph-paper-list"></ul>
      </details>
      <p class="lineage-note">「数学」「雑談」など広すぎるタグは線の生成から除外しています。一つのタグだけを共有する場合、そのタグが8件以下のときだけ線を引きます。</p>
    </section>
    <script src="graph.js" defer></script>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="原稿関係図",
            eyebrow="PAPER RELATION GRAPH",
            description="電波通信のタグと明示的な関係を使って、話題の近い原稿を図にします。",
            canonical_path="/graph/",
            body=body,
            body_class="graph-page",
        ),
        encoding="utf-8",
    )
