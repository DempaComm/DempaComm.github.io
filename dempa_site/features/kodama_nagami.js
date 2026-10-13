"use strict";

(() => {
  const form = document.querySelector("[data-kn-filter]");
  if (!form) return;
  const items = Array.from(document.querySelectorAll("[data-kn-item]"));
  const count = document.querySelector("[data-kn-count]");
  const empty = document.querySelector("[data-kn-empty]");
  const normalize = text => text.normalize("NFKC").normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
  const searchable = new Map(items.map(item => [item, normalize(item.textContent)]));
  // Cache original text before adding search excerpts, so excerpts never become
  // search input themselves. Keep the original links and details untouched.
  const excerpts = new Map(items.map(item => {
    const outside = item.cloneNode(true);
    outside.querySelectorAll("details").forEach(details => details.remove());
    const blocks = Array.from(item.querySelectorAll("details h4, details p, details li, details dt, details dd"))
      .filter(block => !block.querySelector("p, li, dt, dd"))
      .map(block => block.textContent.trim()).filter(Boolean)
      // Prefer a short original sentence or locator over a long reading note.
      // Keep the full block as a fallback for queries spanning sentences.
      .flatMap(text => [text, ...text.split(/(?<=[。．！？])|(?<=[.!?])\s+/u)])
      .sort((left, right) => left.length - right.length);
    const container = document.createElement("div");
    container.className = "kn-matches";
    container.hidden = true;
    item.insertBefore(container, item.querySelector("details"));
    return [item, {outside: normalize(outside.textContent), blocks, container}];
  }));
  const names = ["q", "chapter", "section", "relationship", "era"].filter(name => form.elements.namedItem(name));

  function readFilters() {
    const parameters = new URLSearchParams(window.location.search);
    for (const name of names) {
      const field = form.elements.namedItem(name);
      const value = parameters.get(name) || "";
      field.value = field.tagName === "INPUT" || Array.from(field.options).some(option => option.value === value) ? value : "";
    }
  }

  function saveFilters(clearTarget = false) {
    const url = new URL(window.location.href);
    for (const name of names) {
      const value = form.elements.namedItem(name).value;
      if (value) url.searchParams.set(name, value); else url.searchParams.delete(name);
    }
    if (clearTarget) url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  }

  function targetFor(hash) {
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return null; }
    const target = document.getElementById(id);
    return target?.matches("[data-kn-item]") ? target : null;
  }

  function revealTarget(clearFilters = false) {
    const target = targetFor(window.location.hash);
    if (!target) return;
    if (target.hidden) {
      // Only following a new card link may relax the filters. Reload and Back
      // must honor the conditions explicitly saved in their URL.
      if (!clearFilters) return;
      for (const name of names) form.elements.namedItem(name).value = "";
      render();
      saveFilters();
    }
    const details = target.querySelector("details");
    if (details) details.open = true;
    target.scrollIntoView({block: "start"});
    if (clearFilters) {
      target.tabIndex = -1;
      target.focus({preventScroll: true});
    }
  }

  function render() {
    const tokens = normalize(form.elements.namedItem("q").value).split(/\s+/).filter(Boolean);
    const filters = names.filter(name => name !== "q").map(name => [name, form.elements.namedItem(name).value]);
    let visible = 0;
    for (const item of items) {
      const show = tokens.every(token => searchable.get(item).includes(token)) && filters.every(([name, value]) => !value || (item.dataset[name] || "").split("|").includes(value));
      item.hidden = !show;
      if (show) visible += 1;
      const {outside, blocks, container} = excerpts.get(item);
      const matches = show ? [...new Set(tokens.filter(token => !outside.includes(token))
        .map(token => blocks.find(text => normalize(text).includes(token))).filter(Boolean))] : [];
      container.replaceChildren();
      container.hidden = matches.length === 0;
      if (matches.length) {
        const label = document.createElement("strong");
        label.textContent = "検索語を含む付記・対応";
        container.append(label);
        for (const text of matches) {
          const paragraph = document.createElement("p");
          paragraph.textContent = text;
          container.append(paragraph);
        }
      }
    }
    count.textContent = `${visible} / ${items.length}件を表示している．`;
    empty.hidden = visible !== 0;
  }

  function filterChanged() { render(); saveFilters(true); }
  function restore() { readFilters(); render(); revealTarget(); }
  form.hidden = false;
  form.addEventListener("input", filterChanged);
  form.addEventListener("change", filterChanged);
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("reset", event => {
    event.preventDefault();
    for (const name of names) form.elements.namedItem(name).value = "";
    filterChanged();
  });
  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[href]");
    if (!link || link.target || link.hasAttribute("download") || !link.getAttribute("href").startsWith("#") || !targetFor(link.hash)) return;
    event.preventDefault();
    if (link.href !== window.location.href) window.history.pushState(null, "", link.href);
    revealTarget(true);
  });
  document.querySelectorAll("[data-kn-search-shortcut]").forEach(shortcut => {
    shortcut.hidden = false;
    shortcut.querySelector("a").addEventListener("click", event => {
      event.preventDefault();
      form.scrollIntoView({block: "start"});
      form.elements.namedItem("q").focus({preventScroll: true});
    });
  });
  window.addEventListener("popstate", restore);
  window.addEventListener("hashchange", restore);
  restore();
})();
