import {activeEdges} from "./graph-model.js";
import {html, makeSvg, button, link} from "./graph-dom.js";

const relationText = (edge, options) => {
  const parts = [];
  if (options.explicit && edge.explicit.length) parts.push("明示された関係");
  if (options.paths && edge.reading_paths.length) parts.push("読書経路");
  if (options.tags && edge.tags.length) parts.push(`共通タグ: ${edge.tags.join("・")}`);
  return parts.join(" / ");
};

export function renderInspector(state, on, focus = false) {
  const {inspector, svg, data, byId, groups, options, selected, nodeElements} = state;
  inspector.replaceChildren();
  const node = byId.get(selected);
  if (!node) {
    const welcome = html("div", "graph-welcome");
    const motif = makeSvg("svg", {viewBox: "0 0 200 130", "aria-hidden": "true"});
    [[35,75,95,48],[95,48,158,25],[95,48,153,94],[35,75,63,117],[95,48,63,117]].forEach(([x1,y1,x2,y2]) => motif.append(makeSvg("line", {x1,y1,x2,y2})));
    [[35,75,4],[95,48,6],[158,25,3],[153,94,4],[63,117,3]].forEach(([cx,cy,r]) => motif.append(makeSvg("circle", {cx,cy,r})));
    welcome.append(motif, html("p", "graph-kicker", "つながりから、読みはじめる"),
      html("h2", "", "点の向こうに、\n次の原稿。"),
      html("p", "", "気になる点を選ぶと、原稿の概要と関連する原稿がここに現れます。"));
    const counts = html("div", "graph-welcome-counts");
    const nodeCount = html("span"); nodeCount.append(html("strong", "", String(data.nodes.length)), "原稿");
    const edgeCount = html("span"); edgeCount.append(html("strong", "", String(data.edges.length)), "つながり");
    counts.append(nodeCount, edgeCount); welcome.append(counts);
    const hint = html("p", "graph-small", "色は数学の分野、点の大きさは表示中のつながりの数を表します。");
    inspector.append(welcome, hint);
    return;
  }
  const top = html("div", "graph-inspector-top");
  const meta = html("span", "graph-kicker", `${node.math_section} · ${node.year}`);
  meta.style.color = groups.get(node.group).color;
  const close = button("×", on.clearSelection);
  close.setAttribute("aria-label", "原稿の選択を解除");
  top.append(meta, close);
  const heading = html("h2", "", node.title); heading.id = "graph-detail-heading"; heading.tabIndex = -1;
  const actions = html("nav", "graph-paper-actions"); actions.setAttribute("aria-label", "原稿を読む");
  if (node.html_path) actions.append(link("HTMLで読む ↗", `../papers/${node.slug}/${node.html_path}`, "graph-primary-link"));
  actions.append(link("原稿ページ ↗", `../papers/${node.slug}/`));
  if (node.statement_count) actions.append(link(`定理等 ${node.statement_count}件`, `../statements/years/${node.year}/?paper=${node.slug}`));
  const tags = html("div", "graph-paper-tags");
  node.tags.filter(tag => !data.excluded_generic_tags.includes(tag)).forEach(tag => tags.append(button(tag, () => on.filterTag(tag))));
  inspector.append(top, heading);
  if (node.summary) inspector.append(html("p", "graph-paper-summary", node.summary));
  inspector.append(actions, tags);
  if (node.correction_count) inspector.append(html("p", "graph-small", `訂正・追記 ${node.correction_count}件。内容は原稿ページで確認できます。`));
  const local = html("div", "graph-local-actions");
  local.append(button("この原稿の周辺を見る", () => on.openNeighborhood(node.slug), "graph-local-button"));
  if (options.paper) {
    const depth = html("div", "graph-depth");
    depth.append(html("span", "", "範囲"));
    [1, 2].forEach(value => {
      const control = button(`${value}段階`, () => on.setDepth(value));
      control.setAttribute("aria-pressed", String(options.depth === value)); depth.append(control);
    });
    local.append(depth);
  }
  inspector.append(local);
  if (node.reading_paths.length) {
    const paths = html("div", "graph-reading-paths");
    paths.append(html("h3", "", "この原稿を含む読書経路"));
    node.reading_paths.forEach(path => paths.append(link(`${path.title} ↗`, `../reading-paths/${encodeURIComponent(path.slug)}/`)));
    inspector.append(paths);
  }
  const related = activeEdges(data.edges, options).filter(edge => edge.source === node.slug || edge.target === node.slug)
    .sort((a, b) => b.weight - a.weight || a.source.localeCompare(b.source));
  const section = html("div", "graph-related");
  section.append(html("h3", "", `つながる原稿 · ${related.length}`));
  if (!related.length) section.append(html("p", "graph-small", "現在の線の設定では、つながる原稿はありません。タグや分野から探せます。"));
  related.forEach(edge => {
    const target = byId.get(edge.source === node.slug ? edge.target : edge.source);
    const item = button("", () => {
      if (!nodeElements.has(target.slug)) {
        on.openNeighborhood(target.slug, true);
      } else on.select(target.slug);
    });
    item.append(html("span", "", target.title), html("small", "", relationText(edge, options)));
    section.append(item);
  });
  inspector.append(section, button("関係図に戻る ↑", () => {
    const target = nodeElements.get(node.slug)?.group || svg;
    target.focus(); target.scrollIntoView({block: "nearest"});
  }, "graph-return"));
  if (focus) heading.focus({preventScroll: true});
}
