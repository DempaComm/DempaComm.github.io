"""Small machine-readable catalog and browser logic for serendipitous reading."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dempa_site.manifests.model import Paper


def paper_summary_data(
    selected: Sequence[tuple[Path, Paper]],
) -> dict[str, object]:
    """Return the stable, public-only fields needed by the home-page picker."""
    papers = []
    for _, paper in selected:
        papers.append(
            {
                "slug": paper.slug,
                "title": paper.title,
                "published_at": paper.published_at_text[:10],
                "year": paper.year,
                "math_section": paper.math_section,
                "summary": paper.summary,
                "tags": list(paper.tags),
            }
        )
    return {"schema_version": 1, "papers": papers}


DISCOVERY_SCRIPT = r'''(() => {
  "use strict";

  const todayTarget = document.querySelector("#today-paper");
  const randomTarget = document.querySelector("#random-paper");
  const randomButton = document.querySelector("#random-paper-button");
  const randomScope = document.querySelector("#random-paper-scope");
  if (!todayTarget || !randomTarget || !randomButton || !randomScope) return;

  const make = (name, className, text) => {
    const element = document.createElement(name);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  };

  const showPaper = (target, paper, note) => {
    const meta = make("p", "discovery-note", note);
    const title = make("h3", "", "");
    const link = make("a", "", paper.title);
    link.href = `papers/${encodeURIComponent(paper.slug)}/`;
    title.append(link);
    const summary = make("p", "", paper.summary);
    const detail = make(
      "p",
      "discovery-meta",
      `${paper.published_at} · ${paper.math_section || "未分類"}`
    );
    target.replaceChildren(meta, title, summary, detail);
  };

  const dayNumber = (date) => Number(
    `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, "0")}${String(date.getDate()).padStart(2, "0")}`
  );

  const randomIndex = (length) => {
    if (globalThis.crypto && globalThis.crypto.getRandomValues) {
      const value = new Uint32Array(1);
      globalThis.crypto.getRandomValues(value);
      return value[0] % length;
    }
    return Math.floor(Math.random() * length);
  };

  const inScope = (paper, scope) => {
    if (scope === "all") return true;
    if (scope === "substantial") return paper.tags.includes("断片ではないもの");
    return paper.math_section === scope;
  };

  fetch("papers-summary.json")
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((data) => {
      const papers = Array.isArray(data.papers) ? data.papers : [];
      if (!papers.length) throw new Error("記事一覧が空です");

      const now = new Date();
      const monthDay = `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      const onThisDay = papers.filter((paper) => paper.published_at.slice(5) === monthDay);
      const todayCandidates = onThisDay.length ? onThisDay : papers;
      const todayPaper = todayCandidates[dayNumber(now) % todayCandidates.length];
      const todayNote = onThisDay.length
        ? `${now.getMonth() + 1}月${now.getDate()}日に初出した記事から`
        : "同じ月日の記事がないため、今日の一篇を選びました";
      showPaper(todayTarget, todayPaper, todayNote);

      const chooseRandom = () => {
        const candidates = papers.filter((paper) => inScope(paper, randomScope.value));
        if (!candidates.length) {
          randomTarget.replaceChildren(
            make("p", "discovery-note", "この範囲には記事がありません。")
          );
          return;
        }
        showPaper(
          randomTarget,
          candidates[randomIndex(candidates.length)],
          `${candidates.length}件から選びました`
        );
      };
      randomButton.addEventListener("click", chooseRandom);
      randomScope.addEventListener("change", chooseRandom);
      chooseRandom();
    })
    .catch(() => {
      const message = "記事を選べませんでした。全原稿ページからお探しください。";
      todayTarget.replaceChildren(make("p", "discovery-note", message));
      randomTarget.replaceChildren(make("p", "discovery-note", message));
    });
})();
'''
