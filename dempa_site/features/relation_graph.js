(() => {
  "use strict";
  const svg = document.querySelector("#paper-graph");
  const tagSelect = document.querySelector("#graph-tag");
  const yearSelect = document.querySelector("#graph-year");
  const contentSelect = document.querySelector("#graph-content");
  const query = document.querySelector("#graph-query");
  const count = document.querySelector("#graph-count");
  const list = document.querySelector("#graph-paper-list");
  const detail = document.querySelector("#graph-detail");
  const reset = document.querySelector("#graph-reset");
  const zoomIn = document.querySelector("#graph-zoom-in");
  const zoomOut = document.querySelector("#graph-zoom-out");
  const viewReset = document.querySelector("#graph-view-reset");
  const panButtons = [...document.querySelectorAll(".graph-pan-controls button")];
  const context = document.querySelector("#graph-context");
  const showAll = document.querySelector("#graph-all");
  let focusedSlug = "";
  const ns = "http://www.w3.org/2000/svg";
  const initialView = {x: 0, y: 0, width: 1200, height: 820};
  let view = {...initialView};
  let fittedView = {...initialView};
  let pan = null;
  const make = (name, attrs = {}) => {
    const element = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  };
  const shorten = (value, length = 14) => value.length > length ? `${value.slice(0, length)}…` : value;
  const applyView = () => svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
  const resetView = () => {
    const box = svg.getBBox();
    fittedView = box.width && box.height
      ? {x: box.x - 32, y: box.y - 32, width: box.width + 64, height: box.height + 64}
      : {...initialView};
    view = {...fittedView};
    applyView();
  };
  const changeZoom = (factor, clientX = null, clientY = null) => {
    const rect = svg.getBoundingClientRect();
    const ratioX = clientX === null ? 0.5 : (clientX - rect.left) / rect.width;
    const ratioY = clientY === null ? 0.5 : (clientY - rect.top) / rect.height;
    const nextWidth = Math.max(fittedView.width / 8, Math.min(fittedView.width * 4, view.width * factor));
    const nextHeight = nextWidth * fittedView.height / fittedView.width;
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
      const accessibleList = list.closest("details");
      const defaultListOpen = window.matchMedia("(max-width: 680px)").matches;
      let selectedSlug = "";
      let selectedSource = "";
      let displayedNodes = [];
      let restoration = 0;
      let restoring = false;

      const saveView = (active = document.activeElement) => {
        if (restoring) return;
        const node = active?.closest("[data-graph-slug]");
        window.history.replaceState({
          ...window.history.state,
          paperGraph: {
            location: window.location.pathname + window.location.search,
            selectedSlug, selectedSource, view: {...view}, listOpen: accessibleList.open,
            scrollX: window.scrollX, scrollY: window.scrollY,
            focus: {
              id: active?.id || "",
              href: detail.contains(active) && active.matches("a") ? active.getAttribute("href") : "",
              slug: node?.dataset.graphSlug || "",
              list: node?.classList.contains("graph-list-select") || false,
              back: active?.classList.contains("graph-return") || false,
            },
          },
        }, "");
      };
      // Coalesce continuous scrolling/zooming to avoid flooding History APIs.
      let saveTimer = 0;
      const saveSoon = () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => saveView(), 150);
      };

      const showDetail = (node, trigger = null, focus = true) => {
        selectedSlug = node.slug;
        selectedSource = trigger?.classList.contains("graph-list-select") ? "list" : "graph";
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
          statementLink.href = `../statements/years/${node.slug.slice(0, 4)}/?paper=${node.slug}`;
          statementLink.textContent = `定理等${node.statement_count}件`;
          actions.append(statementLink);
        }
        if (node.reading_paths.length) {
          const paths = document.createElement("p");
          paths.append("読書経路: ");
          node.reading_paths.forEach((path, index) => {
            if (index) paths.append("、");
            const link = document.createElement("a");
            link.href = `../reading-paths/${encodeURIComponent(path.slug)}/`;
            link.textContent = path.title;
            paths.append(link);
          });
          detail.append(heading, meta, facts, actions, paths);
        } else {
          detail.append(heading, meta, facts, actions);
        }
        if (trigger) {
          const back = document.createElement("button");
          back.type = "button";
          back.className = "graph-return";
          back.textContent = trigger.classList.contains("graph-list-select") ? "選んだ原稿の一覧に戻る" : "関係図に戻る";
          back.addEventListener("click", () => {
            trigger.focus();
            trigger.scrollIntoView({block: "center"});
          });
          detail.append(back);
          heading.tabIndex = -1;
          if (focus) {
            heading.focus({preventScroll: true});
            heading.scrollIntoView({block: "start"});
          }
        }
      };

      const draw = () => {
        const selectedTag = tagSelect.value;
        const selectedYear = yearSelect.value;
        const selectedContent = contentSelect.value;
        const words = query.value.normalize("NFKC").toLocaleLowerCase("ja").trim().split(/\s+/).filter(Boolean);
        const focused = data.nodes.find(node => node.slug === focusedSlug);
        const related = new Set([focusedSlug]);
        if (focused) {
          for (const edge of data.edges) {
            if (edge.source === focusedSlug) related.add(edge.target);
            if (edge.target === focusedSlug) related.add(edge.source);
          }
        }
        if (context) {
          context.hidden = !focused;
          context.textContent = focused ? `「${focused.title}」と直接つながる原稿を表示しています。` : "";
        }
        if (showAll) showAll.hidden = !focused;
        let nodes = data.nodes.filter(node =>
          (!focused || related.has(node.slug)) &&
          (!selectedTag || node.tags.includes(selectedTag)) &&
          (!selectedYear || String(node.year) === selectedYear) &&
          words.every(word => `${node.title} ${node.tags.join(" ")}`.normalize("NFKC").toLocaleLowerCase("ja").includes(word)) &&
          (!selectedContent ||
            (selectedContent === "html" && node.html_path) ||
            (selectedContent === "statements" && node.statement_count) ||
            (selectedContent === "corrections" && node.correction_count))
        );
        const total = nodes.length;
        const allNodes = nodes.sort((a, b) => Number(b.slug === focusedSlug) - Number(a.slug === focusedSlug) || b.order - a.order);
        displayedNodes = allNodes;
        selectedSlug = "";
        selectedSource = "";
        nodes = allNodes.slice(0, 60);
        const selected = new Set(nodes.map(node => node.slug));
        const edges = data.edges.filter(edge => selected.has(edge.source) && selected.has(edge.target));
        svg.replaceChildren();
        list.replaceChildren();
        count.textContent = total > 60 ? `${total}件が一致。図は新しい60件、一覧は全${total}件を表示` : `${total}件を表示`;
        detail.innerHTML = "<p>図または一覧から原稿を選ぶと、HTML版や定理等への入口を表示します。</p>";

        if (!nodes.length) {
          const message = make("text", {x: 500, y: 360, "text-anchor": "middle", class: "graph-empty"});
          message.textContent = "条件に一致する原稿がありません";
          svg.append(message);
          resetView();
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
          group.dataset.graphSlug = node.slug;
          if (node.slug === focusedSlug) group.classList.add("graph-node-current");
          const circle = make("circle", {r: 9});
          const label = make("text", {x: 13, y: 4});
          label.textContent = shorten(node.title);
          const title = make("title");
          title.textContent = `${node.title} (${node.year})`;
          group.append(circle, label, title);
          group.addEventListener("click", () => showDetail(node, group));
          group.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              showDetail(node, group);
            }
          });
          svg.append(group);
        });
        allNodes.forEach(node => {
          const item = document.createElement("li");
          const itemLink = document.createElement("button");
          itemLink.type = "button";
          itemLink.className = "graph-list-select";
          itemLink.dataset.graphSlug = node.slug;
          itemLink.textContent = node.title;
          const meta = document.createElement("span");
          meta.textContent = `${node.year} / ${node.html_path ? "HTMLあり" : "HTMLなし"} / 定理等${node.statement_count}件 / ${node.tags.join("・")}`;
          itemLink.addEventListener("click", () => showDetail(node, itemLink));
          item.append(itemLink, meta);
          list.append(item);
        });
        resetView();
        if (focused && selected.has(focusedSlug)) showDetail(focused);
      };

      const update = () => {
        restoration += 1;
        restoring = false;
        const url = new URL(window.location.href);
        for (const [key, value] of Object.entries({paper: focusedSlug, year: yearSelect.value, content: contentSelect.value, q: query.value.trim()})) {
          value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
        }
        // An empty tag intentionally means all tags, even after reload.
        url.searchParams.set("tag", tagSelect.value);
        window.history.replaceState({...window.history.state, paperGraph: null}, "", url);
        draw();
        saveView();
      };
      tagSelect.addEventListener("change", update);
      yearSelect.addEventListener("change", update);
      contentSelect.addEventListener("change", update);
      query.addEventListener("input", update);
      reset.addEventListener("click", () => {
        tagSelect.value = focusedSlug ? "" : data.default_tag || "";
        yearSelect.value = "";
        contentSelect.value = "";
        query.value = "";
        update();
      });
      showAll?.addEventListener("click", () => {
        focusedSlug = "";
        tagSelect.value = "";
        yearSelect.value = "";
        contentSelect.value = "";
        query.value = "";
        update();
      });
      zoomIn.addEventListener("click", () => changeZoom(0.8));
      zoomOut.addEventListener("click", () => changeZoom(1.25));
      viewReset.addEventListener("click", resetView);
      panButtons.forEach(button => button.addEventListener("click", () => {
        view.x += Number(button.dataset.panX) * view.width * 0.2;
        view.y += Number(button.dataset.panY) * view.height * 0.2;
        applyView();
      }));
      svg.addEventListener("wheel", event => {
        event.preventDefault();
        changeZoom(event.deltaY < 0 ? 0.86 : 1.16, event.clientX, event.clientY);
        saveSoon();
      }, {passive: false});
      svg.addEventListener("pointerdown", event => {
        if (event.pointerType === "touch") return;
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
        saveView();
      };
      svg.addEventListener("pointerup", endPan);
      svg.addEventListener("pointercancel", endPan);
      const restore = () => {
        const token = ++restoration;
        restoring = true;
        const parameters = new URLSearchParams(window.location.search);
        focusedSlug = parameters.get("paper") || "";
        if (!data.nodes.some(node => node.slug === focusedSlug)) focusedSlug = "";
        tagSelect.value = parameters.get("tag") ?? (focusedSlug ? "" : data.default_tag || "");
        yearSelect.value = parameters.get("year") || "";
        contentSelect.value = parameters.get("content") || "";
        query.value = parameters.get("q") || "";
        const stored = window.history.state?.paperGraph;
        const saved = stored?.location === window.location.pathname + window.location.search ? stored : null;
        accessibleList.open = typeof saved?.listOpen === "boolean" ? saved.listOpen : defaultListOpen;
        draw();
        const node = displayedNodes.find(item => item.slug === saved?.selectedSlug);
        if (node) {
          const container = saved.selectedSource === "list" ? list : svg;
          const trigger = [...container.querySelectorAll("[data-graph-slug]")]
            .find(item => item.dataset.graphSlug === node.slug);
          showDetail(node, trigger, false);
        }
        if (saved?.view && ["x", "y", "width", "height"].every(key => Number.isFinite(saved.view[key]))
            && saved.view.width > 0 && saved.view.height > 0) {
          view = {...saved.view};
          applyView();
        }
        if (Number.isFinite(saved?.scrollY)) {
          requestAnimationFrame(() => {
            if (token !== restoration) return;
            const focus = saved.focus || {};
            const container = focus.list ? list : svg;
            const target = (focus.id && document.getElementById(focus.id))
              || (focus.href && [...detail.querySelectorAll("a")].find(link => link.getAttribute("href") === focus.href))
              || (focus.slug && [...container.querySelectorAll("[data-graph-slug]")].find(item => item.dataset.graphSlug === focus.slug))
              || (focus.back && detail.querySelector(".graph-return")) || null;
            target?.focus({preventScroll: true});
            window.scrollTo(saved.scrollX || 0, saved.scrollY);
            restoring = false;
          });
        } else restoring = false;
      };
      document.addEventListener("click", event => {
        const link = event.target.closest("a[href]");
        saveView(link || document.activeElement);
      });
      document.addEventListener("focusin", () => saveView());
      accessibleList.addEventListener("toggle", () => saveView());
      window.addEventListener("scroll", saveSoon, {passive: true});
      window.addEventListener("pagehide", () => { clearTimeout(saveTimer); saveView(); });
      window.addEventListener("pageshow", event => { if (event.persisted) restore(); });
      window.addEventListener("popstate", restore);
      restore();
    })
    .catch(error => {
      count.textContent = `関係図を読み込めませんでした: ${error.message}`;
    });
})();
