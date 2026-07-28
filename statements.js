(() => {
  const directory = document.querySelector("[data-statement-directory]");
  if (directory) {
    const parameters = new URLSearchParams(window.location.search);
    const paper = parameters.get("paper") || "";
    const year = parameters.get("year") || paper.slice(0, 4);
    const kind = parameters.get("kind") || window.location.hash.slice(1);
    if (/^\d{4}$/.test(year)) {
      parameters.delete("year");
      const query = parameters.toString();
      window.location.replace(`years/${year}/${query ? `?${query}` : ""}`);
    } else if (["theorem", "definition", "proposition", "counterexample"].includes(kind)) {
      parameters.delete("kind");
      const query = parameters.toString();
      window.location.replace(`kinds/${kind}/${query ? `?${query}` : ""}`);
    }
    return;
  }
  const form = document.querySelector("#statement-filter");
  const query = document.querySelector("#statement-query");
  const kind = document.querySelector("#statement-kind");
  const year = document.querySelector("#statement-year");
  const paper = document.querySelector("#statement-paper");
  const reset = document.querySelector("#statement-reset");
  const status = document.querySelector("#statement-filter-status");
  const sections = [...document.querySelectorAll(".statement-section")];
  const items = [...document.querySelectorAll(".statement-list li[data-kind]")];
  if (!form || !query || !paper || !reset || !status) return;

  const normalized = (value) => value.normalize("NFKC").toLocaleLowerCase("ja").trim();

  const update = () => {
    const wantedQuery = normalized(query.value);
    const wantedKind = kind?.value || "";
    const wantedYear = year?.value || "";
    const wantedPaper = paper.value;
    let visible = 0;
    for (const item of items) {
      const matches =
        (!wantedQuery || normalized(item.textContent).includes(wantedQuery)) &&
        (!wantedKind || item.dataset.kind === wantedKind) &&
        (!wantedYear || item.dataset.year === wantedYear) &&
        (!wantedPaper || item.dataset.paper === wantedPaper);
      item.hidden = !matches;
      if (matches) visible += 1;
    }
    for (const section of sections) {
      section.hidden = !section.querySelector(".statement-list li[data-kind]:not([hidden])");
    }
    status.textContent = `${items.length}件中${visible}件を表示しています。`;
    const url = new URL(window.location.href);
    const values = { q: query.value.trim(), kind: wantedKind, year: wantedYear, paper: wantedPaper };
    for (const [key, value] of Object.entries(values)) {
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
    }
    window.history.replaceState(null, "", url);
  };

  const parameters = new URLSearchParams(window.location.search);
  query.value = parameters.get("q") || "";
  if (kind) kind.value = parameters.get("kind") || "";
  if (year) year.value = parameters.get("year") || "";
  paper.value = parameters.get("paper") || "";
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("submit", (event) => event.preventDefault());
  reset.addEventListener("click", () => {
    form.reset();
    update();
    query.focus();
  });
  update();
})();
