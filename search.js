(() => {
  const queryInput = document.querySelector("#paper-query");
  const tagSelect = document.querySelector("#paper-tag");
  const yearSelect = document.querySelector("#paper-year");
  const count = document.querySelector("#paper-count");
  const empty = document.querySelector("#paper-empty");
  const resetButtons = [
    document.querySelector("#paper-reset"),
    ...document.querySelectorAll("[data-reset-papers]"),
  ].filter(Boolean);
  const cards = [...document.querySelectorAll(".paper-card")];

  if (!queryInput || !tagSelect || !count || cards.length === 0) return;
  const form = queryInput.closest("form");
  const more = document.querySelector("#paper-more");
  const fulltext = document.querySelector("#archive-fulltext-link");
  const pageSize = Number(form.dataset.pageSize) || cards.length;
  let limit = pageSize;

  const tagsFor = (card) => JSON.parse(card.dataset.tags);
  const tags = [...new Set(cards.flatMap(tagsFor))]
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, "ja"));

  for (const tag of tags) {
    const option = document.createElement("option");
    option.value = tag;
    option.textContent = tag;
    tagSelect.append(option);
  }

  const years = [...new Set(cards.map((card) => card.dataset.year))]
    .filter(Boolean)
    .sort((left, right) => Number(right) - Number(left));

  for (const year of yearSelect ? years : []) {
    if ([...yearSelect.options].some(option => option.value === year)) continue;
    const option = document.createElement("option");
    option.value = year;
    option.textContent = `${year}年`;
    yearSelect.append(option);
  }

  const normalize = (value) => value.normalize("NFKC").toLocaleLowerCase("ja").trim();

  const searchableCards = cards.map(card => ({
    card, text: normalize(card.dataset.search), tags: tagsFor(card)
  }));

  function filterPapers(save = true) {
    if (fulltext) {
      const url = new URL(fulltext.href);
      const query = queryInput.value.trim();
      query ? url.searchParams.set("q", query) : url.searchParams.delete("q");
      fulltext.href = url.href;
    }
    const words = normalize(queryInput.value).split(/\s+/).filter(Boolean);
    const selectedTag = tagSelect.value;
    const selectedYear = yearSelect?.value || "";
    let matched = 0;

    for (const {card, text, tags} of searchableCards) {
      const matchesWords = words.every((word) => text.includes(word));
      const matchesTag = !selectedTag || tags.includes(selectedTag);
      const matchesYear = !selectedYear || card.dataset.year === selectedYear;
      const matches = matchesWords && matchesTag && matchesYear;
      if (matches) matched += 1;
      card.hidden = !matches || matched > limit;
    }

    count.textContent = `${cards.length}件中${matched}件が一致` +
      (matched > limit ? `（先頭${limit}件を表示）` : "");
    if (empty) empty.hidden = matched !== 0;
    if (more) more.hidden = matched <= limit;
    if (save) {
      const url = new URL(window.location.href);
      for (const [key, value] of Object.entries({q: queryInput.value.trim(), tag: selectedTag, year: selectedYear})) {
        value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
      }
      window.history.replaceState(null, "", url);
    }
  }

  const changed = () => { limit = pageSize; filterPapers(); };
  queryInput.addEventListener("input", changed);
  tagSelect.addEventListener("change", changed);
  yearSelect?.addEventListener("change", changed);
  form.addEventListener("submit", event => { event.preventDefault(); changed(); });
  more?.addEventListener("click", () => { limit += pageSize; filterPapers(false); });
  for (const button of resetButtons) {
    button.addEventListener("click", () => {
      queryInput.value = "";
      tagSelect.value = "";
      if (yearSelect) yearSelect.value = "";
      changed();
      queryInput.focus();
    });
  }

  function openDirectoryFromHash() {
    if (!window.location.hash.startsWith("#year-")) return;
    const target = document.getElementById(window.location.hash.slice(1));
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
    }
  }

  window.addEventListener("hashchange", openDirectoryFromHash);
  const restore = () => {
    const parameters = new URLSearchParams(window.location.search);
    queryInput.value = parameters.get("q") || "";
    tagSelect.value = parameters.get("tag") || "";
    if (!tagSelect.value) tagSelect.value = "";
    if (yearSelect) yearSelect.value = parameters.get("year") || "";
    limit = pageSize;
    filterPapers(false);
  };
  window.addEventListener("popstate", restore);
  restore();
  openDirectoryFromHash();
})();
