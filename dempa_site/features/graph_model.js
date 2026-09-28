// Pure graph operations shared by the browser and the regression tests.
export function activeEdges(edges, options) {
  return edges.filter(edge =>
    (options.tags && edge.tags.length) ||
    (options.paths && edge.reading_paths.length) ||
    (options.explicit && edge.explicit.length));
}

export function neighborhood(slug, edges, depth = 1) {
  const found = new Set([slug]);
  let frontier = new Set([slug]);
  for (let level = 0; level < depth; level += 1) {
    const next = new Set();
    for (const edge of edges) {
      if (frontier.has(edge.source) && !found.has(edge.target)) next.add(edge.target);
      if (frontier.has(edge.target) && !found.has(edge.source)) next.add(edge.source);
    }
    next.forEach(id => found.add(id));
    frontier = next;
  }
  return found;
}

const normalize = value => String(value).normalize("NFKC").toLocaleLowerCase("ja");

export function visibleGraph(data, options) {
  const terms = normalize(options.q || "").trim().split(/\s+/).filter(Boolean);
  let nodes = data.nodes.filter(node =>
    (!options.tag || node.tags.includes(options.tag)) &&
    (!options.year || String(node.year) === String(options.year)) &&
    (!options.group || node.group === options.group) &&
    (!options.content || (options.content === "html" && node.html_path) ||
      (options.content === "statements" && node.statement_count > 0) ||
      (options.content === "corrections" && node.correction_count > 0)) &&
    terms.every(term => normalize(`${node.title} ${node.tags.join(" ")}`).includes(term)));
  const ids = new Set(nodes.map(node => node.slug));
  let edges = activeEdges(data.edges, options).filter(edge => ids.has(edge.source) && ids.has(edge.target));
  if (options.paper) {
    const local = neighborhood(options.paper, edges, options.depth || 1);
    nodes = nodes.filter(node => local.has(node.slug));
  }
  if (!options.orphans) {
    const linked = new Set(edges.flatMap(edge => [edge.source, edge.target]));
    nodes = nodes.filter(node => linked.has(node.slug));
  }
  const displayed = new Set(nodes.map(node => node.slug));
  edges = edges.filter(edge => displayed.has(edge.source) && displayed.has(edge.target));
  return {nodes, edges};
}

function randomFor(seed) {
  let hash = 2166136261;
  for (const character of seed) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
  return () => {
    hash += 0x6d2b79f5;
    let value = Math.imul(hash ^ hash >>> 15, 1 | hash);
    value ^= value + Math.imul(value ^ value >>> 7, 61 | value);
    return ((value ^ value >>> 14) >>> 0) / 4294967296;
  };
}

const anchors = {
  topology: [-200, -80], analysis: [220, -40],
  algebra: [70, 220], other: [-270, 210],
};

export function createLayout(nodes, edges, previous = new Map()) {
  const points = nodes.map(node => {
    const anchor = anchors[node.group] || anchors.other;
    const random = randomFor(node.slug);
    const angle = random() * Math.PI * 2;
    const radius = Math.sqrt(random()) * 250;
    const saved = previous.get(node.slug);
    return {slug: node.slug, group: node.group,
      x: Number.isFinite(saved?.x) ? saved.x : anchor[0] + Math.cos(angle) * radius,
      y: Number.isFinite(saved?.y) ? saved.y : anchor[1] + Math.sin(angle) * radius,
      vx: 0, vy: 0, pinned: false};
  });
  const byId = new Map(points.map(point => [point.slug, point]));
  return {points, byId, links: edges.map(edge => ({
    source: byId.get(edge.source), target: byId.get(edge.target), weight: edge.weight,
  })).filter(edge => edge.source && edge.target), iteration: 0};
}

export function stepLayout(layout, spacing = 1) {
  const {points, links} = layout;
  const alpha = Math.max(0.12, 1 - layout.iteration / 280);
  for (let i = 0; i < points.length; i += 1) {
    for (let j = i + 1; j < points.length; j += 1) {
      const a = points[i], b = points[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      // Coincident restored/dragged points still need a deterministic separation.
      if (Math.abs(dx) + Math.abs(dy) < 0.001) { dx = 0.1; dy = 0.1; }
      const distance = Math.hypot(dx, dy);
      const force = Math.min(6, 1450 * spacing * spacing / (distance * distance + 40)) +
        Math.max(0, 24 - distance) * 0.16;
      const fx = dx / distance * force, fy = dy / distance * force;
      a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
    }
  }
  for (const edge of links) {
    const dx = edge.target.x - edge.source.x, dy = edge.target.y - edge.source.y;
    const distance = Math.hypot(dx, dy) || 1;
    const force = (distance - 65 * spacing) * 0.017 * Math.min(1.8, Math.sqrt(edge.weight || 1));
    const fx = dx / distance * force, fy = dy / distance * force;
    edge.source.vx += fx; edge.source.vy += fy;
    edge.target.vx -= fx; edge.target.vy -= fy;
  }
  let movement = 0;
  for (const point of points) {
    const anchor = anchors[point.group] || anchors.other;
    point.vx = (point.vx + (anchor[0] * spacing - point.x) * 0.004) * 0.7;
    point.vy = (point.vy + (anchor[1] * spacing - point.y) * 0.004) * 0.7;
    if (point.pinned) { point.vx = 0; point.vy = 0; continue; }
    const dx = Math.max(-10, Math.min(10, point.vx)) * alpha;
    const dy = Math.max(-10, Math.min(10, point.vy)) * alpha;
    point.x += dx; point.y += dy;
    movement += Math.abs(dx) + Math.abs(dy);
  }
  layout.iteration += 1;
  return movement / Math.max(points.length, 1);
}

export function fitView(points, aspect = 1.5) {
  if (!points.length) return {x: -600, y: -400, width: 1200, height: 800};
  const minX = Math.min(...points.map(point => point.x)), maxX = Math.max(...points.map(point => point.x));
  const minY = Math.min(...points.map(point => point.y)), maxY = Math.max(...points.map(point => point.y));
  const width = Math.max(280, maxX - minX + 160, (maxY - minY + 160) * aspect);
  const height = width / aspect;
  return {x: (minX + maxX - width) / 2, y: (minY + maxY - height) / 2, width, height};
}
