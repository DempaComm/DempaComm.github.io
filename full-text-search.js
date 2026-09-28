(() => {
  const form = document.querySelector("#fulltext-search-form");
  const input = document.querySelector("#fulltext-query");
  const status = document.querySelector("#fulltext-status");
  const results = document.querySelector("#fulltext-results");
  const more = document.querySelector("#fulltext-more");
  const reset = document.querySelector("#fulltext-reset");
  const archive = document.querySelector("#fulltext-archive-link");
  if (!form || !input || !status || !results) return;

  let pagefindPromise;
  let request = 0;
  let matches = [];
  let shown = 0;
  let currentQuery = "";
  let ready = false;
  const saveView = (active = document.activeElement) => {
    // Do not replace a saved view with an empty, still-loading result list.
    if (!ready) return;
    window.history.replaceState({
      ...window.history.state,
      fulltextSearch: {
        query: currentQuery, shown, scrollX: window.scrollX, scrollY: window.scrollY,
        link: [...results.querySelectorAll("a")].indexOf(active),
      },
    }, "");
  };
  const pagefind = () => {
    pagefindPromise ||= import("/pagefind/pagefind.js").then(async engine => {
      await engine.options({highlightParam: "highlight"});
      return engine;
    }).catch(error => { pagefindPromise = undefined; throw error; });
    return pagefindPromise;
  };

  const excerptNodes = (markup) => {
    const template = document.createElement("template");
    template.innerHTML = markup || "";
    const fragment = document.createDocumentFragment();
    const copy = (node, parent) => {
      if (node.nodeType === Node.TEXT_NODE) {
        parent.append(document.createTextNode(node.textContent));
      } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "MARK") {
        const mark = document.createElement("mark");
        mark.textContent = node.textContent;
        parent.append(mark);
      } else {
        for (const child of node.childNodes) copy(child, parent);
      }
    };
    copy(template.content, fragment);
    return fragment;
  };

  const headingNodes = (markup) => {
    const template = document.createElement("template");
    template.innerHTML = markup;
    const fragment = document.createDocumentFragment();
    const mathTags = new Set("math mi mn mo mtext mrow mstyle mfrac msqrt mroot msub msup msubsup munder mover munderover mmultiscripts mprescripts none mtable mtr mtd mspace menclose mpadded mphantom mfenced semantics".split(" "));
    const mathAttributes = new Set("mathvariant stretchy symmetric largeop movablelimits accent accentunder fence separator lspace rspace linethickness bevelled rowalign columnalign columnspan rowspan notation width height depth open close separators".split(" "));
    const copy = (node, parent) => {
      if (node.nodeType === Node.TEXT_NODE) {
        parent.append(document.createTextNode(node.textContent));
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        if (["annotation", "annotation-xml", "script", "style"].includes(node.localName)) return;
        let target = parent;
        if (mathTags.has(node.localName)) {
          target = document.createElementNS("http://www.w3.org/1998/Math/MathML", node.localName);
          for (const attribute of node.attributes) {
            if (mathAttributes.has(attribute.name)) target.setAttribute(attribute.name, attribute.value);
          }
          parent.append(target);
        }
        // Unwrap source links and formatting; result labels are already links.
        for (const child of node.childNodes) copy(child, target);
      }
    };
    for (const child of template.content.childNodes) copy(child, fragment);
    return fragment;
  };

  const resultItem = (data) => {
    const item = document.createElement("li");
    const title = document.createElement("h2");
    const link = document.createElement("a");
    const sections = data.sub_results || [];
    const best = sections.find(section => section.anchor) || sections[0] || data;
    link.href = best.url;
    link.textContent = data.meta?.title || data.url;
    title.append(link);
    const excerpt = document.createElement("p");
    excerpt.append(excerptNodes(best.excerpt || data.excerpt));
    item.append(title, excerpt);
    const anchored = sections.filter(section => section.anchor);
    if (anchored.length) {
      const passages = document.createElement("ul");
      passages.className = "fulltext-passages";
      for (const section of anchored.slice(0, 3)) {
        const passage = document.createElement("li");
        const jump = document.createElement("a");
        jump.href = section.url;
        const heading = data.meta?.[`heading_html_${section.anchor.id}`];
        if (heading) jump.append(headingNodes(heading));
        else jump.textContent = section.title;
        passage.append(jump);
        passages.append(passage);
      }
      item.append(passages);
    }
    return item;
  };

  async function showMore(token, focusNew = false) {
    if (more) more.disabled = true;
    try {
      const entries = await Promise.all(matches.slice(shown, shown + 20).map(result => result.data()));
      if (token !== request) return;
      const items = entries.map(resultItem);
      for (const item of items) results.append(item);
      shown += entries.length;
      status.textContent = matches.length
        ? `${matches.length}件見つかりました。` + (shown < matches.length ? `先頭${shown}件を表示しています。` : "")
        : "一致するHTML本文はありません。全原稿の題名・タグ検索もお試しください。";
      if (more) more.hidden = shown >= matches.length;
      if (focusNew) items[0]?.querySelector("h2 a")?.focus();
    } finally {
      if (token === request && more) more.disabled = false;
    }
  }

  async function search(query, saved = null) {
    const token = ++request;
    const normalized = query.normalize("NFKC").trim();
    currentQuery = normalized;
    ready = false;
    results.replaceChildren();
    matches = [];
    shown = 0;
    if (more) { more.hidden = true; more.disabled = false; }
    if (archive) archive.href = `../archive/${normalized ? `?q=${encodeURIComponent(normalized)}` : ""}`;
    if (!normalized) {
      status.textContent = "検索語を入力してください。";
      ready = true;
      return;
    }
    status.textContent = "検索中です…";
    try {
      const engine = await pagefind();
      const response = await engine.search(normalized);
      if (token !== request) return;
      matches = response.results;
      const limit = Number.isInteger(saved?.shown) ? Math.max(20, Math.min(saved.shown, matches.length)) : 20;
      // Restore in normal-sized batches, including when every result was open.
      do {
        await showMore(token);
      } while (token === request && shown < limit && shown < matches.length);
      if (token !== request) return;
      if (Number.isFinite(saved?.scrollY)) {
        requestAnimationFrame(() => {
          if (token !== request) return;
          const link = Number.isInteger(saved.link) ? [...results.querySelectorAll("a")][saved.link] : null;
          link?.focus({preventScroll: true});
          window.scrollTo(saved.scrollX || 0, saved.scrollY);
          ready = true;
        });
      } else ready = true;
    } catch (error) {
      if (token !== request) return;
      console.error(error);
      status.textContent = "全文検索索引を読み込めませんでした。しばらくしてから再度お試しください。";
    }
  }

  const runSearch = (query) => {
    const url = new URL(window.location.href);
    query.trim() ? url.searchParams.set("q", query) : url.searchParams.delete("q");
    window.history.replaceState({...window.history.state, fulltextSearch: null}, "", url);
    search(query);
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch(input.value);
  });
  input.addEventListener("input", () => {
    if (!input.value.trim()) runSearch("");
  });
  reset?.addEventListener("click", () => {
    input.value = "";
    runSearch("");
    input.focus();
  });

  more?.addEventListener("click", () => {
    const token = request;
    showMore(token, true).then(() => {
      if (token === request) saveView();
    }).catch(error => {
      if (token !== request) return;
      console.error(error);
      status.textContent = "続きの結果を読み込めませんでした。もう一度お試しください。";
    });
  });

  const restore = () => {
    const query = new URLSearchParams(window.location.search).get("q") || "";
    const saved = window.history.state?.fulltextSearch;
    input.value = query;
    search(query, saved?.query === query.normalize("NFKC").trim() ? saved : null);
  };
  document.addEventListener("click", event => {
    const link = event.target.closest("a[href]");
    if (link) saveView(link);
  });
  document.addEventListener("focusin", () => saveView());
  let saveTimer = 0;
  window.addEventListener("scroll", () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => saveView(), 150);
  }, {passive: true});
  window.addEventListener("pagehide", () => { clearTimeout(saveTimer); saveView(); });
  window.addEventListener("pageshow", event => { if (event.persisted) restore(); });
  window.addEventListener("popstate", restore);
  restore();
})();
