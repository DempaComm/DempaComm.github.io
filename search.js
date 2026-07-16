(() => {
  const queryInput = document.querySelector("#paper-query");
  const tagSelect = document.querySelector("#paper-tag");
  const count = document.querySelector("#paper-count");
  const cards = [...document.querySelectorAll(".paper-card")];

  if (!queryInput || !tagSelect || !count || cards.length === 0) return;

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

  const normalize = (value) => value.normalize("NFKC").toLocaleLowerCase("ja").trim();

  function filterPapers() {
    const words = normalize(queryInput.value).split(/\s+/).filter(Boolean);
    const selectedTag = tagSelect.value;
    let visible = 0;

    for (const card of cards) {
      const searchable = normalize(card.dataset.search);
      const cardTags = tagsFor(card);
      const matchesWords = words.every((word) => searchable.includes(word));
      const matchesTag = !selectedTag || cardTags.includes(selectedTag);
      card.hidden = !(matchesWords && matchesTag);
      if (!card.hidden) visible += 1;
    }

    count.textContent = `${cards.length}件中${visible}件を表示`;
  }

  queryInput.addEventListener("input", filterPapers);
  tagSelect.addEventListener("change", filterPapers);
  filterPapers();
})();
