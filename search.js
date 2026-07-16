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

  if (!queryInput || !tagSelect || !yearSelect || !count || cards.length === 0) return;

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

  for (const year of years) {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = `${year}年`;
    yearSelect.append(option);
  }

  const normalize = (value) => value.normalize("NFKC").toLocaleLowerCase("ja").trim();

  function filterPapers() {
    const words = normalize(queryInput.value).split(/\s+/).filter(Boolean);
    const selectedTag = tagSelect.value;
    const selectedYear = yearSelect.value;
    let visible = 0;

    for (const card of cards) {
      const searchable = normalize(card.dataset.search);
      const cardTags = tagsFor(card);
      const matchesWords = words.every((word) => searchable.includes(word));
      const matchesTag = !selectedTag || cardTags.includes(selectedTag);
      const matchesYear = !selectedYear || card.dataset.year === selectedYear;
      card.hidden = !(matchesWords && matchesTag && matchesYear);
      if (!card.hidden) visible += 1;
    }

    count.textContent = `${cards.length}件中${visible}件を表示`;
    if (empty) empty.hidden = visible !== 0;
  }

  queryInput.addEventListener("input", filterPapers);
  tagSelect.addEventListener("change", filterPapers);
  yearSelect.addEventListener("change", filterPapers);
  for (const button of resetButtons) {
    button.addEventListener("click", () => {
      queryInput.value = "";
      tagSelect.value = "";
      yearSelect.value = "";
      filterPapers();
      queryInput.focus();
    });
  }

  function openDirectoryFromHash() {
    if (!window.location.hash.startsWith("#year-")) return;
    const target = document.querySelector(window.location.hash);
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
    }
  }

  window.addEventListener("hashchange", openDirectoryFromHash);
  filterPapers();
  openDirectoryFromHash();
})();
