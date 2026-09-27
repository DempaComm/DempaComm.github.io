(() => {
  const form = document.querySelector("#fulltext-search-form");
  const input = document.querySelector("#fulltext-query");
  const status = document.querySelector("#fulltext-status");
  const results = document.querySelector("#fulltext-results");
  const more = document.querySelector("#fulltext-more");
  const archive = document.querySelector("#fulltext-archive-link");
  if (!form || !input || !status || !results) return;

  let pagefindPromise;
  let request = 0;
  let matches = [];
  let shown = 0;
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
        jump.textContent = section.title;
        passage.append(jump);
        passages.append(passage);
      }
      item.append(passages);
    }
    return item;
  };

  async function showMore(token) {
    if (more) more.disabled = true;
    try {
      const entries = await Promise.all(matches.slice(shown, shown + 20).map(result => result.data()));
      if (token !== request) return;
      for (const entry of entries) results.append(resultItem(entry));
      shown += entries.length;
      status.textContent = matches.length
        ? `${matches.length}件見つかりました。` + (shown < matches.length ? `先頭${shown}件を表示しています。` : "")
        : "一致するHTML本文はありません。全原稿の題名・タグ検索もお試しください。";
      if (more) more.hidden = shown >= matches.length;
    } finally {
      if (token === request && more) more.disabled = false;
    }
  }

  async function search(query) {
    const token = ++request;
    const normalized = query.normalize("NFKC").trim();
    results.replaceChildren();
    matches = [];
    shown = 0;
    if (more) { more.hidden = true; more.disabled = false; }
    if (archive) archive.href = `../archive/${normalized ? `?q=${encodeURIComponent(normalized)}` : ""}`;
    if (!normalized) {
      status.textContent = "検索語を入力してください。";
      return;
    }
    status.textContent = "検索中です…";
    try {
      const engine = await pagefind();
      const response = await engine.search(normalized);
      if (token !== request) return;
      matches = response.results;
      await showMore(token);
    } catch (error) {
      if (token !== request) return;
      console.error(error);
      status.textContent = "全文検索索引を読み込めませんでした。しばらくしてから再度お試しください。";
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = input.value;
    const url = new URL(window.location.href);
    query.trim() ? url.searchParams.set("q", query) : url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
    search(query);
  });

  more?.addEventListener("click", () => {
    const token = request;
    showMore(token).catch(error => {
      if (token !== request) return;
      console.error(error);
      status.textContent = "続きの結果を読み込めませんでした。もう一度お試しください。";
    });
  });

  const initial = new URLSearchParams(window.location.search).get("q") || "";
  if (initial) {
    input.value = initial;
    search(initial);
  }
})();
