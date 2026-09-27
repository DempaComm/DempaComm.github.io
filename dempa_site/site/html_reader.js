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

  // Keep MathML intact: highlight prose using the locally generated Pagefind asset.
  if (new URLSearchParams(window.location.search).has("highlight")) {
    import("/pagefind/pagefind-highlight.js").then(() => {
      new window.PagefindHighlight({
        highlightParam: "highlight",
        markOptions: {
          className: "pagefind-highlight",
          exclude: ["[data-pagefind-ignore]", "[data-pagefind-ignore] *", "math", "math *", "script", "style"],
          done: () => {
            const hash = window.location.hash.slice(1);
            let identifier = hash;
            try { identifier = decodeURIComponent(hash); } catch { /* Keep a literal malformed fragment. */ }
            const target = identifier ? document.getElementById(identifier) : document.querySelector("mark.pagefind-highlight");
            target?.scrollIntoView({block: "start"});
            schedule();
          }
        }
      });
    }).catch(error => console.warn("検索語の強調を読み込めませんでした。", error));
  }
})();
