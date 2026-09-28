import {neighborhood} from "./graph-model.js";

export function paintLabels(state) {
  const {svg, options, selected, hovered, graph, layout, view, fitted, nodeElements, degrees, scale} = state;
  if (!view) return;
  const zoom = fitted.width / view.width;
  const unit = 1 / scale();
  const occupied = [];
  const nearby = neighborhood(hovered || selected, graph.edges);
  const sorted = [...graph.nodes].sort((a, b) =>
    (Number(b.slug === hovered || b.slug === selected) - Number(a.slug === hovered || a.slug === selected)) ||
    (Number(nearby.has(b.slug)) - Number(nearby.has(a.slug))) ||
    (degrees.get(b.slug) - degrees.get(a.slug)) || a.slug.localeCompare(b.slug));
  let shown = 0;
  for (const node of sorted) {
    const elements = nodeElements.get(node.slug), point = layout.byId.get(node.slug);
    const densityScale = Math.min(1, Math.max(0.62, svg.clientWidth / 760));
    const radius = (3.4 + Math.sqrt(degrees.get(node.slug) || 0) * 1.1) * densityScale;
    elements.dot.setAttribute("r", radius * unit);
    elements.hit.setAttribute("r", Math.max(13, radius + 5) * unit);
    elements.ring.setAttribute("r", (radius + 5) * unit);
    const labelWidth = (Array.from(elements.text.textContent).length * 10.5 + 6) * unit;
    const leftLabel = point.x + (radius + 7) * unit + labelWidth > view.x + view.width - 12 * unit;
    elements.text.setAttribute("text-anchor", leftLabel ? "end" : "start");
    elements.text.setAttribute("x", (leftLabel ? -1 : 1) * (radius + 7) * unit);
    elements.text.setAttribute("y", 4 * unit);
    elements.text.setAttribute("font-size", 11.5 * unit);
    const important = node.slug === hovered || node.slug === selected;
    const neighbor = Boolean(hovered || selected) && nearby.has(node.slug);
    const limit = Math.ceil(Math.max(3, Math.floor(svg.clientWidth / 115)) * Math.min(10, zoom ** 1.8));
    let show = important || options.labels === "all" || (options.labels === "auto" && (neighbor || shown < limit));
    if (point.x < view.x || point.x > view.x + view.width || point.y < view.y || point.y > view.y + view.height) show = false;
    const box = {x: leftLabel ? point.x - (radius + 7) * unit - labelWidth : point.x + (radius + 5) * unit,
      y: point.y - 10 * unit, width: labelWidth, height: 21 * unit};
    if (show && options.labels !== "all" && !important && occupied.some(other =>
      box.x < other.x + other.width && box.x + box.width > other.x &&
      box.y < other.y + other.height && box.y + box.height > other.y)) show = false;
    elements.text.classList.toggle("is-visible", show);
    if (show) { occupied.push(box); shown += 1; }
  }
}

export function highlight(state) {
  const {list, selected, hovered, graph, nodeElements, edgeElements} = state;
  const active = hovered || selected;
  const neighbors = active ? neighborhood(active, graph.edges) : null;
  nodeElements.forEach((elements, slug) => {
    elements.group.classList.toggle("is-dimmed", Boolean(neighbors && !neighbors.has(slug)));
    elements.group.classList.toggle("is-selected", slug === selected);
    elements.group.classList.toggle("is-highlighted", slug === active);
    elements.group.setAttribute("aria-pressed", String(slug === selected));
  });
  edgeElements.forEach(({element, edge}) => {
    const connected = edge.source === active || edge.target === active;
    element.classList.toggle("is-highlighted", Boolean(active && connected));
    element.classList.toggle("is-dimmed", Boolean(active && !connected));
  });
  list.querySelectorAll("button").forEach(element => element.setAttribute("aria-pressed", String(element.dataset.graphSlug === selected)));
  paintLabels(state);
}

export function draw(state) {
  const {layout, nodeElements, edgeElements} = state;
  layout.points.forEach(point => nodeElements.get(point.slug)?.group.setAttribute("transform", `translate(${point.x},${point.y})`));
  edgeElements.forEach(({element, edge}) => {
    const a = layout.byId.get(edge.source), b = layout.byId.get(edge.target);
    element.setAttribute("x1", a.x); element.setAttribute("y1", a.y);
    element.setAttribute("x2", b.x); element.setAttribute("y2", b.y);
  });
  paintLabels(state);
}
