"use strict";

(() => {
  const form = document.querySelector("[data-kn-filter]");
  if (!form) return;
  const items = Array.from(document.querySelectorAll("[data-kn-item]"));
  const count = document.querySelector("[data-kn-count]");
  const empty = document.querySelector("[data-kn-empty]");
  const normalize = text => text.normalize("NFKC").normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
  const searchable = new Map(items.map(item => [item, normalize(item.textContent)]));
  const names = ["q", "chapter", "section", "relationship", "era"].filter(name => form.elements.namedItem(name));
  const parameters = new URLSearchParams(window.location.search);
  for (const name of names) {
    const field = form.elements.namedItem(name);
    const value = parameters.get(name) || "";
    if (field.tagName === "INPUT" || Array.from(field.options).some(option => option.value === value)) field.value = value;
  }

  function revealTarget() {
    if (!window.location.hash) return;
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target?.matches("[data-kn-item]")) return;
    if (target.hidden) {
      for (const name of names) form.elements.namedItem(name).value = "";
      apply();
    }
    const details = target.querySelector("details");
    if (details) details.open = true;
    target.scrollIntoView({block: "start"});
  }

  function apply() {
    const tokens = normalize(form.elements.namedItem("q").value).split(/\s+/).filter(Boolean);
    const filters = names.filter(name => name !== "q").map(name => [name, form.elements.namedItem(name).value]);
    let visible = 0;
    for (const item of items) {
      const show = tokens.every(token => searchable.get(item).includes(token)) && filters.every(([name, value]) => !value || (item.dataset[name] || "").split("|").includes(value));
      item.hidden = !show;
      if (show) visible += 1;
    }
    count.textContent = `${visible} / ${items.length}件を表示している．`;
    empty.hidden = visible !== 0;
    const url = new URL(window.location.href);
    for (const name of names) {
      const value = form.elements.namedItem(name).value;
      if (value) url.searchParams.set(name, value); else url.searchParams.delete(name);
    }
    window.history.replaceState(null, "", url);
  }
  form.hidden = false;
  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("reset", event => {
    event.preventDefault();
    for (const name of names) form.elements.namedItem(name).value = "";
    apply();
  });
  window.addEventListener("hashchange", revealTarget);
  apply();
  revealTarget();
})();
