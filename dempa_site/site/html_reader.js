(() => {
  "use strict";
  const regions = [...document.querySelectorAll(".math-scroll")];
  let frame = 0;
  const updateScrollRegions = () => {
    frame = 0;
    for (const region of regions) {
      const overflowing = region.scrollWidth > region.clientWidth + 1;
      region.tabIndex = overflowing ? 0 : -1;
      region.classList.toggle("math-overflow", overflowing);
      if (overflowing) {
        region.setAttribute("role", "region");
        region.setAttribute("aria-label", "数式・表（左右の矢印キーでスクロールできます）");
      } else {
        region.removeAttribute("role");
        region.removeAttribute("aria-label");
      }
    }
  };
  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(updateScrollRegions);
  };
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(schedule);
    regions.forEach(region => observer.observe(region));
  }
  window.addEventListener("resize", schedule);
  window.addEventListener("load", schedule);
  document.fonts?.ready.then(schedule);
  schedule();

  const footnotes = [];
  for (const note of document.querySelectorAll(".ltx_note.ltx_role_footnote")) {
    const mark = note.querySelector(":scope > .ltx_note_mark");
    const content = note.querySelector(".ltx_note_content");
    if (!mark || !content) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "footnote-toggle";
    button.setAttribute("aria-label", `脚注${mark.textContent.trim()}`);
    if (!content.id) {
      let identifier = `dempa-footnote-${footnotes.length + 1}`;
      while (document.getElementById(identifier)) identifier += "-note";
      content.id = identifier;
    }
    button.setAttribute("aria-controls", content.id);
    const setOpen = (open) => {
      content.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      schedule();
    };
    mark.replaceWith(button);
    button.append(mark);
    note.classList.add("footnote-interactive");
    setOpen(false);
    button.addEventListener("click", () => setOpen(content.hidden));
    note.addEventListener("keydown", event => {
      if (event.key === "Escape" && !content.hidden) {
        event.preventDefault();
        setOpen(false);
        button.focus({preventScroll: true});
      }
    });
    footnotes.push({note, setOpen});
  }
  document.addEventListener("click", event => {
    for (const {note, setOpen} of footnotes) {
      if (!note.contains(event.target)) setOpen(false);
    }
  });

  // Keep MathML intact: highlight prose using the locally generated Pagefind asset.
  if (new URLSearchParams(window.location.search).has("highlight")) {
    import("/pagefind/pagefind-highlight.js").then(() => {
      new window.PagefindHighlight({
        highlightParam: "highlight",
        markOptions: {
          className: "pagefind-highlight",
          exclude: ["[data-pagefind-ignore]", "[data-pagefind-ignore] *", "math", "math *", "script", "style"],
          done: () => {
            for (const {note, setOpen} of footnotes) {
              if (note.querySelector("mark.pagefind-highlight")) setOpen(true);
            }
            const hash = window.location.hash.slice(1);
            let identifier = hash;
            try { identifier = decodeURIComponent(hash); } catch { /* Keep a literal malformed fragment. */ }
            const anchor = identifier ? document.getElementById(identifier) : null;
            const marks = [...document.querySelectorAll("mark.pagefind-highlight")];
            const match = marks.find(mark => !anchor || anchor.contains(mark) ||
              (anchor.compareDocumentPosition(mark) & Node.DOCUMENT_POSITION_FOLLOWING));
            const matchedNote = match?.closest(".footnote-interactive");
            const target = matchedNote || anchor || match;
            matchedNote?.querySelector(".footnote-toggle")?.focus({preventScroll: true});
            target?.scrollIntoView({block: "start"});
            schedule();
          }
        }
      });
    }).catch(error => console.warn("検索語の強調を読み込めませんでした。", error));
  }
})();
