import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";

const source = await readFile(new URL("../dempa_site/features/graph_model.js", import.meta.url), "utf8");
const {activeEdges, neighborhood, visibleGraph, createLayout, stepLayout, fitView} =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const node = (slug, values = {}) => ({slug, title: slug, tags: [], group: "topology", year: 2026,
  html_path: "", statement_count: 0, correction_count: 0, ...values});
const edge = (source, target, values = {}) => ({source, target, tags: [], reading_paths: [], explicit: [], weight: 1, ...values});
const options = {tags: true, paths: true, explicit: true, orphans: true};
const data = {nodes: [node("a", {title: "ＡＢＣ 距離", tags: ["位相"], html_path: "html/index.html"}),
  node("b", {tags: ["位相"], statement_count: 2}), node("c", {group: "analysis", year: 2025}), node("d"), node("orphan")],
  edges: [edge("a", "b", {tags: ["位相"]}), edge("b", "c", {reading_paths: ["path"]}), edge("c", "d", {explicit: ["related"]})]};
assert.deepEqual([...neighborhood("a", data.edges, 1)].sort(), ["a", "b"]);
assert.deepEqual([...neighborhood("a", data.edges, 2)].sort(), ["a", "b", "c"]);
assert.equal(activeEdges(data.edges, {...options, tags: false}).length, 2);
assert.equal(visibleGraph(data, {...options, tags: false, paths: false, explicit: false, orphans: false}).nodes.length, 0);
assert.deepEqual(visibleGraph(data, {...options, q: "abc 距離"}).nodes.map(n => n.slug), ["a"]);
assert.deepEqual(visibleGraph(data, {...options, content: "statements"}).nodes.map(n => n.slug), ["b"]);
assert.equal(visibleGraph(data, {...options, content: "corrections"}).nodes.length, 0);
assert.equal(visibleGraph(data, {...options, tag: "位相"}).edges.length, 1);
assert.equal(visibleGraph(data, {...options, paper: "a", depth: 2}).nodes.length, 3);
assert.equal(visibleGraph(data, {...options, paper: "a", depth: 2, paths: false}).nodes.length, 2);
assert.equal(visibleGraph(data, {...options, paper: "a", year: "2025"}).nodes.length, 0);
for (const filters of [{group: "analysis"}, {content: "html"}, {paper: "a"}, {tag: "位相", orphans: false}]) {
  const result = visibleGraph(data, {...options, ...filters});
  assert(result.edges.every(e => result.nodes.some(n => n.slug === e.source) && result.nodes.some(n => n.slug === e.target)));
}

const nodes = Array.from({length: 40}, (_, i) => node(String(i)));
const edges = nodes.slice(1).map((n, i) => edge(nodes[i].slug, n.slug));
const original = JSON.stringify(nodes);
const first = createLayout(nodes, edges), second = createLayout(nodes, edges);
for (let step = 0; step < 300; step += 1) { stepLayout(first); stepLayout(second); }
assert.deepEqual(first.points, second.points, "layout is repeatable");
assert.equal(JSON.stringify(nodes), original, "layout must not mutate catalog data");
assert(first.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y)));
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const connected = first.links.reduce((sum, e) => sum + distance(e.source, e.target), 0) / first.links.length;
const allPairs = first.points.flatMap((a, i) => first.points.slice(i + 1).map(b => distance(a, b)));
assert(connected < allPairs.reduce((sum, value) => sum + value, 0) / allPairs.length, "connected papers should cluster");
assert(Math.min(...allPairs) > 15, "nodes should not collapse onto one point");
for (const aspect of [0.5, 1, 2.5]) {
  const view = fitView(first.points, aspect);
  assert(Math.abs(view.width / view.height - aspect) < 1e-9);
  assert(first.points.every(p => p.x > view.x && p.x < view.x + view.width && p.y > view.y && p.y < view.y + view.height));
}
const coincident = createLayout(nodes.slice(0, 2), [], new Map([["0", {x: 0, y: 0}], ["1", {x: 0, y: 0}]]));
stepLayout(coincident);
assert(distance(...coincident.points) > 0, "coincident nodes must separate");
const pinned = createLayout([node("p")], []);
pinned.points[0].pinned = true;
const before = {x: pinned.points[0].x, y: pinned.points[0].y};
stepLayout(pinned);
assert.equal(pinned.points[0].x, before.x); assert.equal(pinned.points[0].y, before.y);
assert.equal(stepLayout(createLayout([], [])), 0);
assert(Object.values(fitView([])).every(Number.isFinite));
console.log("Graph filtering, edge provenance, deterministic layout, fit and drag contracts passed.");
