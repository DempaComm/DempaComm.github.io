(() => {
  "use strict";
  const svg = document.querySelector("#paper-graph");
  const tagSelect = document.querySelector("#graph-tag");
  const yearSelect = document.querySelector("#graph-year");
  const contentSelect = document.querySelector("#graph-content");
  const count = document.querySelector("#graph-count");
  const list = document.querySelector("#graph-paper-list");
  const detail = document.querySelector("#graph-detail");
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

      const showDetail = node => {
        detail.replaceChildren();
        const heading = document.createElement("h3");
        heading.textContent = node.title;
        const meta = document.createElement("p");
        meta.textContent = `${node.year} / ${node.math_section}`;
        const facts = document.createElement("p");
        const statementSummary = Object.entries(node.statement_counts)
          .filter(([, value]) => value)
          .map(([key, value]) => `${data.statement_labels[key]}${value}`)
          .join("・");
        facts.textContent = [
          node.html_path ? "HTML版あり" : "HTML版なし",
          statementSummary || "定理等の登録なし",
          node.correction_count ? `訂正・追記${node.correction_count}件` : "訂正・追記なし"
        ].join(" / ");
        const actions = document.createElement("nav");
        actions.className = "paper-actions";
        const paperLink = document.createElement("a");
        paperLink.href = `../papers/${node.slug}/`;
        paperLink.textContent = "原稿ページ";
        actions.append(paperLink);
        if (node.html_path) {
          const htmlLink = document.createElement("a");
          htmlLink.href = `../papers/${node.slug}/${node.html_path}`;
          htmlLink.textContent = "HTML本文";
          actions.append(htmlLink);
        }
        if (node.statement_count) {
          const statementLink = document.createElement("a");
          statementLink.href = `../statements/?paper=${node.slug}`;
          statementLink.textContent = `定理等${node.statement_count}件`;
          actions.append(statementLink);
        }
        if (node.reading_paths.length) {
          const paths = document.createElement("p");
          paths.textContent = `読書経路: ${node.reading_paths.map(path => path.title).join("、")}`;
          detail.append(heading, meta, facts, actions, paths);
        } else {
          detail.append(heading, meta, facts, actions);
        }
      };

      const draw = () => {
        const selectedTag = tagSelect.value;
        const selectedYear = yearSelect.value;
        const selectedContent = contentSelect.value;
        let nodes = data.nodes.filter(node =>
          (!selectedTag || node.tags.includes(selectedTag)) &&
          (!selectedYear || String(node.year) === selectedYear) &&
          (!selectedContent ||
            (selectedContent === "html" && node.html_path) ||
            (selectedContent === "statements" && node.statement_count) ||
            (selectedContent === "corrections" && node.correction_count))
        );
        const total = nodes.length;
        nodes = nodes.sort((a, b) => b.order - a.order).slice(0, 60);
        const selected = new Set(nodes.map(node => node.slug));
        const edges = data.edges.filter(edge => selected.has(edge.source) && selected.has(edge.target));
        svg.replaceChildren();
        list.replaceChildren();
        count.textContent = total > 60 ? `${total}件中、新しい60件を表示` : `${total}件を表示`;
        detail.innerHTML = "<p>図または一覧から原稿を選ぶと、HTML版や定理等への入口を表示します。</p>";

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
            class: edge.explicit.length ? "graph-edge graph-edge-explicit" :
              edge.reading_paths.length ? "graph-edge graph-edge-path" : "graph-edge",
            "stroke-width": Math.min(5, 1 + edge.weight * 0.75)
          });
          const title = make("title");
          title.textContent = [
            edge.explicit.length ? `明示関係: ${edge.explicit.join("、")}` : "",
            edge.reading_paths.length ? `読書経路: ${edge.reading_paths.join("、")}` : "",
            edge.tags.length ? `希少タグ: ${edge.tags.join("、")}` : ""
          ].filter(Boolean).join(" / ");
          line.append(title);
          svg.append(line);
        });

        nodes.forEach(node => {
          const position = positions.get(node.slug);
          const group = make("g", {class: "graph-node", transform: `translate(${position.x} ${position.y})`, tabindex: "0", role: "button", "aria-label": `${node.title}の詳細を表示`});
          const circle = make("circle", {r: 9});
          const label = make("text", {x: 13, y: 4});
          label.textContent = shorten(node.title);
          const title = make("title");
          title.textContent = `${node.title} (${node.year})`;
          group.append(circle, label, title);
          group.addEventListener("click", () => showDetail(node));
          group.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              showDetail(node);
            }
          });
          svg.append(group);

          const item = document.createElement("li");
          const itemLink = document.createElement("a");
          itemLink.href = `../papers/${node.slug}/`;
          itemLink.textContent = node.title;
          const meta = document.createElement("span");
          meta.textContent = `${node.year} / ${node.html_path ? "HTMLあり" : "HTMLなし"} / 定理等${node.statement_count}件 / ${node.tags.join("・")}`;
          item.addEventListener("click", () => showDetail(node));
          item.append(itemLink, meta);
          list.append(item);
        });
        resetView();
      };

      tagSelect.addEventListener("change", draw);
      yearSelect.addEventListener("change", draw);
      contentSelect.addEventListener("change", draw);
      reset.addEventListener("click", () => {
        tagSelect.value = data.default_tag || "";
        yearSelect.value = "";
        contentSelect.value = "";
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
