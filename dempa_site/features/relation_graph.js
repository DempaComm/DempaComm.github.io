import {activeEdges, neighborhood, visibleGraph, createLayout, stepLayout, fitView} from "./graph-model.js";

const $ = id => document.getElementById(id);
const svg = $("paper-graph");
const workspace = document.querySelector(".graph-explorer");
const inspector = $("graph-detail");
const list = $("graph-paper-list");
const settings = document.querySelector(".graph-settings");
const accessibleList = document.querySelector(".graph-accessible-list");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const ns = "http://www.w3.org/2000/svg";
const html = (name, className = "", text = "") => {
  const element = document.createElement(name);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
};
const makeSvg = (name, attributes = {}) => {
  const element = document.createElementNS(ns, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
};
const button = (text, action, className = "") => {
  const element = html("button", className, text);
  element.type = "button";
  element.addEventListener("click", action);
  return element;
};
const link = (text, href, className = "") => {
  const element = html("a", className, text);
  element.href = href;
  return element;
};
const shortTitle = (title, limit = 15) => Array.from(title).length > limit
  ? Array.from(title).slice(0, limit).join("") + "…" : title;
const defaults = {q: "", tag: "", year: "", group: "", content: "", paper: "", depth: 1,
  tags: true, paths: true, explicit: true, orphans: true, labels: "auto", spacing: 100};

async function start() {
  const response = await fetch("paper-graph.json");
  if (!response.ok) throw new Error(`Graph data: HTTP ${response.status}`);
  const data = await response.json();
  const byId = new Map(data.nodes.map(node => [node.slug, node]));
  const groups = new Map(data.groups.map(group => [group.id, group]));
  const locationKey = () => location.pathname + location.search;
  const readOptions = () => {
    const params = new URLSearchParams(location.search);
    const value = {...defaults};
    for (const key of ["q", "tag", "year", "group", "content", "paper"]) value[key] = params.get(key) || "";
    if (!byId.has(value.paper)) value.paper = "";
    if (!groups.has(value.group)) value.group = "";
    if (!data.tags.some(tag => tag.name === value.tag)) value.tag = "";
    if (!data.years.some(year => String(year) === value.year)) value.year = "";
    if (!["html", "statements", "corrections"].includes(value.content)) value.content = "";
    for (const key of ["tags", "paths", "explicit", "orphans"]) value[key] = params.get(key) !== "0";
    value.depth = params.get("depth") === "2" ? 2 : 1;
    value.labels = ["all", "none"].includes(params.get("labels")) ? params.get("labels") : "auto";
    value.spacing = Math.max(70, Math.min(160, Number(params.get("spacing")) || 100));
    return value;
  };
  let options = readOptions();
  const saved = history.state?.paperGraph;
  const initial = saved?.location === locationKey() ? saved : null;
  let selected = byId.has(initial?.selected) ? initial.selected : options.paper;
  let hovered = "";
  let keyboardSlug = selected;
  let positions = new Map(initial?.positions || []);
  let graph = {nodes: [], edges: []};
  let layout;
  let view;
  let fitted;
  let nodeElements = new Map();
  let edgeElements = [];
  let degrees = new Map();
  let frame = 0;
  let saveTimer = 0;
  let searchTimer = 0;
  let paused = initial?.paused ?? reducedMotion.matches;
  let drag = null;
  let suppressClick = false;
  let expanded = false;
  let expandedScroll = 0;
  let restoring = false;

  const rememberPositions = () => {
    layout?.points.forEach(point => positions.set(point.slug, {x: point.x, y: point.y}));
  };
  const save = () => {
    if (restoring || !view) return;
    rememberPositions();
    const active = document.activeElement;
    history.replaceState({...history.state, paperGraph: {
      location: locationKey(), selected, view: {...view}, fitted: {...fitted},
      positions: [...positions], paused, listOpen: accessibleList.open, settingsOpen: settings.open,
      sidebarScroll: document.querySelector(".graph-sidebar").scrollTop,
      scrollX, scrollY: expanded ? expandedScroll : scrollY,
      focus: {id: active?.id || "", slug: active?.closest("[data-graph-slug]")?.dataset.graphSlug || "",
        list: active?.classList.contains("graph-list-select") || false,
        href: inspector.contains(active) ? active.getAttribute("href") : ""},
    }}, "");
  };
  const saveSoon = () => { clearTimeout(saveTimer); saveTimer = setTimeout(save, 180); };
  const updateUrl = () => {
    const url = new URL(location.href);
    for (const [key, value] of Object.entries(options)) {
      url.searchParams.delete(key);
      if (value !== defaults[key]) url.searchParams.set(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
    }
    history.replaceState(history.state, "", url);
  };
  const synchronizeControls = () => {
    for (const key of ["q", "tag", "year", "content", "labels", "spacing"]) {
      $(key === "q" ? "graph-query" : `graph-${key}`).value = options[key];
    }
    for (const key of ["tags", "paths", "explicit", "orphans"]) $(`graph-${key}`).checked = options[key];
    document.querySelectorAll("[data-graph-group]").forEach(element => {
      element.setAttribute("aria-pressed", String(options.group === element.dataset.graphGroup));
    });
    $("graph-all").hidden = !options.paper;
    $("graph-context").hidden = !options.paper;
    $("graph-context").textContent = options.paper ? `${shortTitle(byId.get(options.paper).title, 24)} · ${options.depth}段階のつながり` : "";
  };
  const aspect = () => Math.max(0.45, svg.clientWidth / Math.max(1, svg.clientHeight));
  const world = (x, y) => new DOMPoint(x, y).matrixTransform(svg.getScreenCTM().inverse());
  const scale = () => Math.max(0.1, svg.getScreenCTM()?.a || 1);

  function paintLabels() {
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
  const applyView = () => {
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
    $("graph-zoom-level").value = `${Math.round(fitted.width / view.width * 100)}%`;
    paintLabels();
  };
  const fit = () => {
    fitted = fitView(layout.points, aspect());
    view = {...fitted};
    applyView();
    saveSoon();
  };
  const zoom = (factor, x, y) => {
    if (!layout) return;
    const anchor = x === undefined ? {x: view.x + view.width / 2, y: view.y + view.height / 2} : world(x, y);
    const nextWidth = Math.max(fitted.width / 6, Math.min(fitted.width * 2, view.width * factor));
    const ratio = nextWidth / view.width;
    view = {x: anchor.x - (anchor.x - view.x) * ratio, y: anchor.y - (anchor.y - view.y) * ratio,
      width: nextWidth, height: view.height * ratio};
    applyView(); saveSoon();
  };
  const pan = (x, y) => {
    view.x += x * view.width * 0.15; view.y += y * view.height * 0.15;
    applyView(); saveSoon();
  };
  function highlight() {
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
    paintLabels();
  }
  function draw() {
    layout.points.forEach(point => nodeElements.get(point.slug)?.group.setAttribute("transform", `translate(${point.x},${point.y})`));
    edgeElements.forEach(({element, edge}) => {
      const a = layout.byId.get(edge.source), b = layout.byId.get(edge.target);
      element.setAttribute("x1", a.x); element.setAttribute("y1", a.y);
      element.setAttribute("x2", b.x); element.setAttribute("y2", b.y);
    });
    paintLabels();
  }
  function animate() {
    cancelAnimationFrame(frame);
    if (paused) return;
    const tick = () => {
      if (document.hidden || paused) { frame = 0; return; }
      let movement = 0;
      for (let step = 0; step < 3; step += 1) movement = stepLayout(layout, options.spacing / 100);
      draw();
      if (layout.iteration < 300 && movement > 0.012) frame = requestAnimationFrame(tick);
      else { frame = 0; saveSoon(); }
    };
    frame = requestAnimationFrame(tick);
  }
  const relationText = edge => {
    const parts = [];
    if (options.explicit && edge.explicit.length) parts.push("明示された関係");
    if (options.paths && edge.reading_paths.length) parts.push("読書経路");
    if (options.tags && edge.tags.length) parts.push(`共通タグ: ${edge.tags.join("・")}`);
    return parts.join(" / ");
  };
  function showInspector(focus = false) {
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
    const close = button("×", () => { selected = ""; showInspector(); highlight(); svg.focus({preventScroll: true}); saveSoon(); });
    close.setAttribute("aria-label", "原稿の選択を解除");
    top.append(meta, close);
    const heading = html("h2", "", node.title); heading.id = "graph-detail-heading"; heading.tabIndex = -1;
    const actions = html("nav", "graph-paper-actions"); actions.setAttribute("aria-label", "原稿を読む");
    if (node.html_path) actions.append(link("HTMLで読む ↗", `../papers/${node.slug}/${node.html_path}`, "graph-primary-link"));
    actions.append(link("原稿ページ ↗", `../papers/${node.slug}/`));
    if (node.statement_count) actions.append(link(`定理等 ${node.statement_count}件`, `../statements/years/${node.year}/?paper=${node.slug}`));
    const tags = html("div", "graph-paper-tags");
    node.tags.filter(tag => !data.excluded_generic_tags.includes(tag)).forEach(tag => tags.append(button(tag, () => {
      options.tag = tag; options.paper = ""; change();
    })));
    inspector.append(top, heading);
    if (node.summary) inspector.append(html("p", "graph-paper-summary", node.summary));
    inspector.append(actions, tags);
    if (node.correction_count) inspector.append(html("p", "graph-small", `訂正・追記 ${node.correction_count}件。内容は原稿ページで確認できます。`));
    const local = html("div", "graph-local-actions");
    local.append(button("この原稿の周辺を見る", () => {
      options = {...options, q: "", tag: "", year: "", content: "", group: "", paper: node.slug, depth: 1}; change();
    }, "graph-local-button"));
    if (options.paper) {
      const depth = html("div", "graph-depth");
      depth.append(html("span", "", "範囲"));
      [1, 2].forEach(value => {
        const control = button(`${value}段階`, () => { options.depth = value; change(); });
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
          options = {...options, q: "", tag: "", year: "", content: "", group: "", paper: target.slug, depth: 1}; selected = target.slug; change();
        } else select(target.slug);
      });
      item.append(html("span", "", target.title), html("small", "", relationText(edge)));
      section.append(item);
    });
    inspector.append(section, button("関係図に戻る ↑", () => {
      const target = nodeElements.get(node.slug)?.group || svg;
      target.focus(); target.scrollIntoView({block: "nearest"});
    }, "graph-return"));
    if (focus) heading.focus({preventScroll: true});
  }
  function select(slug, focus = false) {
    selected = slug; keyboardSlug = slug;
    nodeElements.forEach(({group}, id) => group.setAttribute("tabindex", id === slug ? "0" : "-1"));
    showInspector(focus); highlight(); saveSoon();
    if (matchMedia("(max-width: 760px)").matches) inspector.scrollIntoView({block: "start"});
    else {
      const sidebar = document.querySelector(".graph-sidebar");
      const heading = $("graph-detail-heading").getBoundingClientRect();
      const bounds = sidebar.getBoundingClientRect();
      if (heading.top < bounds.top || heading.bottom > bounds.bottom) sidebar.scrollTop = settings.offsetHeight;
    }
  }
  function render(restored = null) {
    cancelAnimationFrame(frame);
    if (!restored) rememberPositions();
    graph = visibleGraph(data, options);
    if (!graph.nodes.some(node => node.slug === selected)) selected = "";
    hovered = "";
    layout = createLayout(graph.nodes, graph.edges, positions);
    // Start with an already legible arrangement, then gently settle the remaining forces.
    if (!restored) for (let step = 0; step < (reducedMotion.matches || paused ? 300 : 110); step += 1) stepLayout(layout, options.spacing / 100);
    degrees = new Map(graph.nodes.map(node => [node.slug, 0]));
    graph.edges.forEach(edge => { degrees.set(edge.source, degrees.get(edge.source) + 1); degrees.set(edge.target, degrees.get(edge.target) + 1); });
    svg.replaceChildren(); nodeElements = new Map(); edgeElements = [];
    const lines = makeSvg("g", {class: "graph-links", "aria-hidden": "true"});
    const dots = makeSvg("g", {class: "graph-nodes"});
    graph.edges.forEach(edge => {
      const kind = options.explicit && edge.explicit.length ? "explicit" : options.paths && edge.reading_paths.length ? "paths" : "tags";
      const element = makeSvg("line", {class: `graph-connection ${kind}`, "vector-effect": "non-scaling-stroke"});
      lines.append(element); edgeElements.push({element, edge});
    });
    if (!graph.nodes.some(node => node.slug === keyboardSlug)) keyboardSlug = selected || graph.nodes[0]?.slug;
    graph.nodes.forEach(node => {
      const group = makeSvg("g", {class: "graph-point", role: "button", tabindex: node.slug === keyboardSlug ? "0" : "-1",
        "aria-label": `${node.title}、${node.year}年、つながり${degrees.get(node.slug)}件`, "data-graph-slug": node.slug});
      group.style.setProperty("--node-color", groups.get(node.group).color);
      const title = makeSvg("title"); title.textContent = node.title;
      const hit = makeSvg("circle", {class: "graph-point-hit"});
      const ring = makeSvg("circle", {class: "graph-point-ring", "vector-effect": "non-scaling-stroke"});
      const dot = makeSvg("circle", {class: "graph-point-dot"});
      const text = makeSvg("text", {class: "graph-point-label", "aria-hidden": "true"}); text.textContent = shortTitle(node.title);
      group.append(title, hit, ring, dot, text); dots.append(group);
      nodeElements.set(node.slug, {group, dot, hit, ring, text});
      group.addEventListener("pointerenter", event => { if (event.pointerType !== "touch" && !drag) { hovered = node.slug; highlight(); } });
      group.addEventListener("pointerleave", () => { hovered = ""; highlight(); });
      group.addEventListener("focus", () => { hovered = node.slug; highlight(); });
      group.addEventListener("blur", () => { hovered = ""; highlight(); });
      group.addEventListener("click", event => { event.stopPropagation(); if (!suppressClick) select(node.slug, event.detail === 0); });
    });
    svg.append(lines, dots);
    list.replaceChildren();
    [...graph.nodes].sort((a, b) => b.order - a.order).forEach(node => {
      const item = html("li");
      const control = button(node.title, () => select(node.slug, true), "graph-list-select");
      control.dataset.graphSlug = node.slug; item.append(control); list.append(item);
    });
    $("graph-count").textContent = `${graph.nodes.length} / ${data.nodes.length} 原稿 · ${graph.edges.length} つながり`;
    $("graph-list-count").textContent = `${graph.nodes.length}件`;
    $("graph-empty").hidden = Boolean(graph.nodes.length);
    synchronizeControls();
    fitted = fitView(layout.points, aspect());
    view = restored?.view && Object.values(restored.view).every(Number.isFinite) && restored.view.width > 0 && restored.view.height > 0
      ? {...restored.view} : {...fitted};
    if (restored?.fitted) fitted = {...restored.fitted};
    draw(); applyView(); showInspector(); highlight();
    if (!restored) animate();
    saveSoon();
  }
  function change() { updateUrl(); render(); }
  const reset = () => {
    clearTimeout(searchTimer); options = {...defaults}; selected = ""; change();
  };

  data.tags.forEach(tag => $("graph-tag").append(new Option(`${tag.name} (${tag.count})`, tag.name)));
  data.years.forEach(year => $("graph-year").append(new Option(`${year}年`, String(year))));
  data.groups.forEach(group => {
    const control = button("", () => { options.group = options.group === group.id ? "" : group.id; change(); }, "graph-group");
    control.dataset.graphGroup = group.id; control.style.setProperty("--group-color", group.color);
    control.append(html("span", "graph-group-dot"), html("span", "", group.label), html("small", "", String(group.count)));
    $("graph-legend").append(control);
  });
  $("graph-query").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { options.q = $("graph-query").value; change(); }, 160);
  });
  for (const key of ["tag", "year", "content"]) $(`graph-${key}`).addEventListener("change", event => { options[key] = event.target.value; change(); });
  for (const key of ["tags", "paths", "explicit", "orphans"]) $(`graph-${key}`).addEventListener("change", event => { options[key] = event.target.checked; change(); });
  $("graph-labels").addEventListener("change", event => { options.labels = event.target.value; updateUrl(); paintLabels(); saveSoon(); });
  $("graph-spacing").addEventListener("change", event => { options.spacing = Number(event.target.value); change(); });
  $("graph-reset").addEventListener("click", reset);
  $("graph-empty-reset").addEventListener("click", reset);
  $("graph-all").addEventListener("click", () => { options.paper = ""; change(); });
  $("graph-zoom-in").addEventListener("click", () => zoom(0.8));
  $("graph-zoom-out").addEventListener("click", () => zoom(1.25));
  $("graph-view-reset").addEventListener("click", fit);
  document.querySelectorAll("[data-pan-x]").forEach(control => control.addEventListener("click", () => pan(Number(control.dataset.panX), Number(control.dataset.panY))));
  const updateMotion = () => {
    const label = paused ? "配置の動きを再開する" : "配置の動きを止める";
    $("graph-motion").textContent = paused ? "▷" : "Ⅱ";
    $("graph-motion").setAttribute("aria-label", label); $("graph-motion").title = label;
    $("graph-motion").setAttribute("aria-pressed", String(paused));
  };
  $("graph-motion").addEventListener("click", () => {
    paused = !paused; updateMotion();
    if (paused) cancelAnimationFrame(frame);
    else { layout.iteration = 120; animate(); }
    saveSoon();
  });
  reducedMotion.addEventListener("change", () => { if (reducedMotion.matches) { paused = true; cancelAnimationFrame(frame); updateMotion(); } });
  svg.addEventListener("wheel", event => { event.preventDefault(); zoom(Math.exp(Math.max(-80, Math.min(80, event.deltaY)) * 0.003), event.clientX, event.clientY); }, {passive: false});
  svg.addEventListener("pointerdown", event => {
    if (event.pointerType === "touch" || event.button !== 0) return;
    const slug = event.target.closest("[data-graph-slug]")?.dataset.graphSlug;
    drag = {id: event.pointerId, slug, x: event.clientX, y: event.clientY, start: world(event.clientX, event.clientY), moved: false};
    if (slug) { layout.byId.get(slug).pinned = true; cancelAnimationFrame(frame); }
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", event => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (Math.hypot(dx, dy) > 3) drag.moved = true;
    if (!drag.moved) return;
    svg.classList.add("is-dragging");
    const point = world(event.clientX, event.clientY);
    if (drag.slug) {
      const target = layout.byId.get(drag.slug); target.x = point.x; target.y = point.y; draw();
    } else {
      view.x -= point.x - drag.start.x; view.y -= point.y - drag.start.y; applyView();
    }
  });
  const endDrag = event => {
    if (!drag || event.pointerId !== drag.id) return;
    const {slug, moved} = drag;
    if (slug) layout.byId.get(slug).pinned = false;
    drag = null; svg.classList.remove("is-dragging");
    suppressClick = moved;
    // Pointer capture retargets the click to the canvas, so handle simple node taps here.
    if (slug && !moved && event.type !== "pointercancel") select(slug);
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
    setTimeout(() => { suppressClick = false; }, 0);
    saveSoon();
  };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);
  svg.addEventListener("keydown", event => {
    const slug = event.target.closest("[data-graph-slug]")?.dataset.graphSlug;
    if (["+", "=", "-", "0"].includes(event.key)) {
      event.preventDefault(); event.key === "0" ? fit() : zoom(event.key === "-" ? 1.25 : 0.8); return;
    }
    if (slug && ["Enter", " "].includes(event.key)) { event.preventDefault(); select(slug, true); return; }
    const direction = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[event.key];
    if (!direction) return;
    event.preventDefault();
    if (!slug) { pan(...direction); return; }
    const origin = layout.byId.get(slug);
    const candidates = layout.points.filter(point => point.slug !== slug).map(point => {
      const dx = point.x - origin.x, dy = point.y - origin.y;
      const forward = dx * direction[0] + dy * direction[1];
      return {point, forward, score: Math.hypot(dx, dy) + Math.abs(dx * direction[1] - dy * direction[0]) * 2};
    }).filter(candidate => candidate.forward > 0).sort((a, b) => a.score - b.score);
    if (candidates.length) {
      keyboardSlug = candidates[0].point.slug;
      nodeElements.forEach(({group}, id) => group.setAttribute("tabindex", id === keyboardSlug ? "0" : "-1"));
      const point = candidates[0].point;
      if (point.x < view.x + 20 || point.x > view.x + view.width - 20 || point.y < view.y + 20 || point.y > view.y + view.height - 20) {
        view.x = point.x - view.width / 2; view.y = point.y - view.height / 2; applyView();
      }
      nodeElements.get(keyboardSlug).group.focus();
    }
  });
  const outside = [...document.body.children].filter(element => !element.contains(workspace) && element.tagName !== "SCRIPT");
  function setExpanded(value) {
    expanded = value;
    if (value) expandedScroll = scrollY;
    workspace.classList.toggle("is-expanded", value);
    document.body.classList.toggle("graph-expanded", value);
    outside.forEach(element => { element.inert = value; });
    $("graph-expand").setAttribute("aria-expanded", String(value));
    $("graph-expand").setAttribute("aria-label", value ? "通常の表示に戻す" : "関係図を広く表示");
    $("graph-expand").title = value ? "通常の表示に戻す" : "広く表示";
    if (!value) { scrollTo(0, expandedScroll); $("graph-expand").focus(); }
  }
  $("graph-expand").addEventListener("click", () => setExpanded(!expanded));
  document.addEventListener("keydown", event => {
    if (!expanded) return;
    if (event.key === "Escape") { event.preventDefault(); setExpanded(false); }
    if (event.key === "Tab") {
      const focusable = [...workspace.querySelectorAll('a, button, input, select, summary, [tabindex="0"]')]
        .filter(element => !element.closest("[hidden]") && element.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  new ResizeObserver(() => {
    if (!view) return;
    if (Math.abs(view.width / view.height - aspect()) < 0.001) { paintLabels(); return; }
    const zoomFactor = fitted.width / view.width;
    const offsetX = (view.x + view.width / 2 - fitted.x - fitted.width / 2) / fitted.width;
    const offsetY = (view.y + view.height / 2 - fitted.y - fitted.height / 2) / fitted.height;
    fitted = fitView(layout.points, aspect());
    const width = fitted.width / zoomFactor, height = fitted.height / zoomFactor;
    view = {width, height, x: fitted.x + fitted.width * (0.5 + offsetX) - width / 2,
      y: fitted.y + fitted.height * (0.5 + offsetY) - height / 2};
    applyView();
  }).observe(svg);
  const restore = state => {
    restoring = true;
    requestAnimationFrame(() => {
      accessibleList.open = state.listOpen || false; settings.open = state.settingsOpen || false;
      const focus = state.focus || {};
      let element = focus.id ? $(focus.id) : null;
      if (focus.href) element = [...inspector.querySelectorAll("a")].find(item => item.getAttribute("href") === focus.href);
      if (focus.slug) element = focus.list ? [...list.querySelectorAll("button")].find(item => item.dataset.graphSlug === focus.slug) : nodeElements.get(focus.slug)?.group;
      element?.focus({preventScroll: true});
      document.querySelector(".graph-sidebar").scrollTop = state.sidebarScroll || 0;
      scrollTo(state.scrollX || 0, state.scrollY || 0); restoring = false;
    });
  };
  addEventListener("scroll", saveSoon, {passive: true});
  document.querySelector(".graph-sidebar").addEventListener("scroll", saveSoon, {passive: true});
  document.addEventListener("focusin", saveSoon);
  document.addEventListener("click", event => { if (event.target.closest("a")) save(); }, true);
  settings.addEventListener("toggle", saveSoon); accessibleList.addEventListener("toggle", saveSoon);
  addEventListener("pagehide", save);
  addEventListener("popstate", () => {
    options = readOptions(); const state = history.state?.paperGraph;
    selected = state?.selected || options.paper; positions = new Map(state?.positions || []);
    render(state); if (state) restore(state);
  });
  updateMotion(); render(initial); if (initial) restore(initial);
}

start().catch(error => {
  console.error(error);
  $("graph-count").textContent = "関係図を読み込めませんでした";
  inspector.replaceChildren(html("h2", "", "関係図を読み込めませんでした"),
    html("p", "", "ページを再読み込みしてください。全原稿の一覧からも探せます。"),
    link("全原稿の一覧へ", "../archive/"));
});
