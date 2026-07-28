(() => {
  const form = document.querySelector("#fulltext-search-form");
  const input = document.querySelector("#fulltext-query");
  const status = document.querySelector("#fulltext-status");
  const results = document.querySelector("#fulltext-results");
  if (!form || !input || !status || !results) return;

  let pagefindPromise;
  const pagefind = () => {
    pagefindPromise ||= import("/pagefind/pagefind.js");
    return pagefindPromise;
  };

  const plainText = (markup) => {
    const template = document.createElement("template");
    template.innerHTML = markup || "";
    return template.content.textContent.trim();
  };

  const resultItem = (data) => {
    const item = document.createElement("li");
    const title = document.createElement("h2");
    const link = document.createElement("a");
    link.href = data.url;
    link.textContent = data.meta?.title || data.url;
    title.append(link);
    const excerpt = document.createElement("p");
    excerpt.textContent = plainText(data.excerpt);
    const path = document.createElement("p");
    path.className = "fulltext-result-path";
    path.textContent = data.url;
    item.append(title, excerpt, path);
    return item;
  };

  async function search(query) {
    const normalized = query.normalize("NFKC").trim();
    results.replaceChildren();
    if (!normalized) {
      status.textContent = "検索語を入力してください。";
      return;
    }
    status.textContent = "検索中です…";
    try {
      const engine = await pagefind();
      const response = await engine.search(normalized);
      const entries = await Promise.all(response.results.map((result) => result.data()));
      for (const entry of entries) results.append(resultItem(entry));
      status.textContent = entries.length
        ? `${entries.length}件見つかりました。`
        : "一致するHTML本文はありません。";
    } catch (error) {
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

  const initial = new URLSearchParams(window.location.search).get("q") || "";
  if (initial) {
    input.value = initial;
    search(initial);
  }
})();
