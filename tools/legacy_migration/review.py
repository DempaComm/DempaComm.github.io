"""Render the private legacy-migration metadata review page."""

from __future__ import annotations

import html
from typing import Any

from dempa_site.dates import local_now_isoformat
from dempa_site.files import compact_json


def metadata_review_html(records: list[dict[str, Any]]) -> str:
    payload = compact_json(records).replace("</", "<\\/")
    generated_at = local_now_isoformat()
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>メタデータ候補確認</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #10171c;
      --panel: #172229;
      --panel-2: #1e2c34;
      --line: #40515b;
      --text: #f5f7f8;
      --muted: #b5c0c6;
      --accent: #58c4c6;
      --exact: #65c98f;
      --likely: #74b7e8;
      --ambiguous: #e6b85c;
      --unmatched: #d98282;
      --accepted: #65c98f;
      --held: #e6b85c;
      --rejected: #d98282;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
        "Yu Gothic UI", sans-serif;
      line-height: 1.6;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 1rem max(1rem, calc((100vw - 1180px) / 2));
      border-bottom: 1px solid var(--line);
      background: rgba(16, 23, 28, .96);
      backdrop-filter: blur(12px);
    }}
    h1 {{ margin: 0; font-size: clamp(1.35rem, 4vw, 2rem); }}
    header p {{ margin: .25rem 0 .8rem; color: var(--muted); }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(14rem, 1fr) repeat(3, minmax(8rem, auto));
      gap: .55rem;
    }}
    input, select, button {{
      min-height: 2.7rem;
      border: 1px solid var(--line);
      border-radius: .55rem;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }}
    input, select {{ padding: .45rem .7rem; }}
    button {{ padding: .45rem .8rem; cursor: pointer; }}
    button:hover, button:focus-visible {{ border-color: var(--accent); }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: .55rem 1rem;
      max-width: 1180px;
      margin: 1rem auto;
      padding: 0 1rem;
      color: var(--muted);
    }}
    main {{
      display: grid;
      gap: 1rem;
      max-width: 1180px;
      margin: 0 auto 4rem;
      padding: 0 1rem;
    }}
    article {{
      overflow: hidden;
      border: 1px solid var(--line);
      border-left: .35rem solid var(--line);
      border-radius: .8rem;
      background: var(--panel);
    }}
    article[data-match="exact"] {{ border-left-color: var(--exact); }}
    article[data-match="likely"] {{ border-left-color: var(--likely); }}
    article[data-match="ambiguous"] {{ border-left-color: var(--ambiguous); }}
    article[data-match="unmatched"] {{ border-left-color: var(--unmatched); }}
    article[data-decision="accepted"] {{ box-shadow: inset 0 0 0 1px var(--accepted); }}
    article[data-decision="held"] {{ box-shadow: inset 0 0 0 1px var(--held); }}
    article[data-decision="rejected"] {{ opacity: .72; }}
    .card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding: .9rem 1rem;
      background: var(--panel-2);
    }}
    .card-head h2 {{ margin: 0; font-size: 1.05rem; overflow-wrap: anywhere; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: .4rem; justify-content: flex-end; }}
    .badge {{
      padding: .15rem .5rem;
      border: 1px solid currentColor;
      border-radius: 999px;
      font-size: .78rem;
      white-space: nowrap;
    }}
    .comparison {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
    }}
    .side {{ padding: 1rem; min-width: 0; }}
    .side + .side {{ border-left: 1px solid var(--line); }}
    .side h3 {{ margin: 0 0 .55rem; color: var(--accent); font-size: .9rem; }}
    dl {{ display: grid; grid-template-columns: 6.5rem 1fr; margin: 0; gap: .25rem .6rem; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    a {{ color: #8ed9e1; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: .5rem;
      padding: .8rem 1rem;
      border-top: 1px solid var(--line);
    }}
    .decision[aria-pressed="true"] {{ color: #0d1519; font-weight: 700; }}
    .decision[data-value="accepted"][aria-pressed="true"] {{ background: var(--accepted); }}
    .decision[data-value="held"][aria-pressed="true"] {{ background: var(--held); }}
    .decision[data-value="rejected"][aria-pressed="true"] {{ background: var(--rejected); }}
    .decision:disabled {{ cursor: not-allowed; opacity: .45; }}
    .empty {{ padding: 2rem; text-align: center; color: var(--muted); }}
    #notice {{
      position: fixed;
      right: 1rem;
      bottom: 1rem;
      max-width: min(30rem, calc(100vw - 2rem));
      padding: .7rem 1rem;
      border-radius: .55rem;
      background: #e8f7f7;
      color: #102025;
      opacity: 0;
      pointer-events: none;
      transition: opacity .18s;
    }}
    #notice.show {{ opacity: 1; }}
    @media (max-width: 800px) {{
      .controls {{ grid-template-columns: 1fr 1fr; }}
      .controls input {{ grid-column: 1 / -1; }}
      .comparison {{ grid-template-columns: 1fr; }}
      .side + .side {{ border-left: 0; border-top: 1px solid var(--line); }}
      dl {{ grid-template-columns: 5.5rem 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>メタデータ候補確認</h1>
    <p>端末内専用。判定はこのブラウザに自動保存されます。</p>
    <div class="controls">
      <input id="query" type="search" placeholder="題名・原稿名・タグ・台帳番号を検索">
      <select id="match-filter" aria-label="照合区分">
        <option value="all">全照合区分</option>
        <option value="exact">完全一致</option>
        <option value="likely">有力候補</option>
        <option value="ambiguous">要確認</option>
        <option value="unmatched">未対応</option>
      </select>
      <select id="decision-filter" aria-label="判定">
        <option value="all">全判定</option>
        <option value="pending">未判定</option>
        <option value="accepted">採用</option>
        <option value="held">保留</option>
        <option value="rejected">却下</option>
      </select>
      <select id="priority-filter" aria-label="アーカイブ優先度">
        <option value="all">全候補</option>
        <option value="priority">優先アーカイブのみ</option>
        <option value="standard">通常候補のみ</option>
      </select>
      <select id="tag-filter" aria-label="タグ">
        <option value="favorite">僕のお気に入り</option>
        <option value="all">全タグ</option>
      </select>
      <select id="scope-filter" aria-label="原稿状態">
        <option value="new-candidates">未移行の新規記事候補</option>
        <option value="published-variants">既存記事の別版</option>
        <option value="all">公開済み・重複を含む全候補</option>
        <option value="published">公開済みのみ</option>
        <option value="duplicates">重複候補のみ</option>
      </select>
      <select id="year-filter" aria-label="公開年"><option value="all">全年</option></select>
      <button id="copy-command" type="button">採用分の確定コマンドをコピー</button>
      <button id="export-decisions" type="button">判定JSONを保存</button>
      <button id="import-decisions" type="button">判定JSONを読み込む</button>
      <input id="import-file" type="file" accept="application/json,.json" hidden>
    </div>
  </header>
  <div class="summary" id="summary"></div>
  <main id="cards"></main>
  <div id="notice" role="status" aria-live="polite"></div>
  <script>
    const records = {payload};
    const storageKey = "dempa-metadata-review-v1";
    const decisions = loadDecisions();
    const cards = document.getElementById("cards");
    const summary = document.getElementById("summary");
    const query = document.getElementById("query");
    const matchFilter = document.getElementById("match-filter");
    const decisionFilter = document.getElementById("decision-filter");
    const priorityFilter = document.getElementById("priority-filter");
    const tagFilter = document.getElementById("tag-filter");
    const scopeFilter = document.getElementById("scope-filter");
    const yearFilter = document.getElementById("year-filter");
    const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({{
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }})[char]);
    const list = values => values?.length ? values.map(escapeHtml).join(" / ") : "—";
    const decisionOf = record => {{
      const stored = decisions[record.record_id];
      if (!stored || stored.candidate_url !== record.metadata_original_url) return "pending";
      return stored.decision;
    }};
    function loadDecisions() {{
      try {{ return JSON.parse(localStorage.getItem(storageKey) || "{{}}"); }}
      catch {{ return {{}}; }}
    }}
    function saveDecisions() {{
      localStorage.setItem(storageKey, JSON.stringify(decisions));
    }}
    function notify(message) {{
      const notice = document.getElementById("notice");
      notice.textContent = message;
      notice.classList.add("show");
      clearTimeout(notify.timer);
      notify.timer = setTimeout(() => notice.classList.remove("show"), 2200);
    }}
    function setDecision(record, decision) {{
      if (decision === "pending") delete decisions[record.record_id];
      else decisions[record.record_id] = {{
        decision,
        candidate_url: record.metadata_original_url,
        updated_at: new Date().toISOString()
      }};
      saveDecisions();
      render();
    }}
    function recordYear(record) {{
      return record.metadata_published_at?.slice(0, 4) || "不明";
    }}
    function visible(record) {{
      const text = [
        record.record_id, record.source_dir, record.local_title,
        record.metadata_title, ...(record.metadata_tags || []),
        ...(record.pdf_files || []), ...(record.metadata_pdf_files || [])
      ].join(" ").toLocaleLowerCase("ja");
      return (!query.value || text.includes(query.value.toLocaleLowerCase("ja")))
        && (matchFilter.value === "all" || record.metadata_match === matchFilter.value)
        && (decisionFilter.value === "all" || decisionOf(record) === decisionFilter.value)
        && (priorityFilter.value === "all"
          || (priorityFilter.value === "priority" && record.priority_archive)
          || (priorityFilter.value === "standard" && !record.priority_archive))
        && (tagFilter.value === "all"
          || (tagFilter.value === "favorite"
            && record.metadata_tags.includes("僕のお気に入り")))
        && (scopeFilter.value === "all"
          || (scopeFilter.value === "new-candidates"
            && record.status !== "published"
            && record.duplicate_status !== "duplicate"
            && !record.article_already_published)
          || (scopeFilter.value === "published-variants"
            && record.status !== "published"
            && record.article_already_published)
          || (scopeFilter.value === "published" && record.status === "published")
          || (scopeFilter.value === "duplicates"
            && record.duplicate_status === "duplicate"))
        && (yearFilter.value === "all" || recordYear(record) === yearFilter.value);
    }}
    function card(record) {{
      const decision = decisionOf(record);
      const canAccept = ["exact", "likely"].includes(record.metadata_match);
      const score = record.metadata_score == null ? "—" : record.metadata_score.toFixed(1);
      const articleLink = record.metadata_original_url
        ? `<a href="${{escapeHtml(record.metadata_original_url)}}" target="_blank" rel="noreferrer">元記事を開く</a>`
        : "—";
      const button = (value, label, disabled = false) =>
        `<button class="decision" data-id="${{escapeHtml(record.record_id)}}"
          data-value="${{value}}" aria-pressed="${{decision === value}}"
          ${{disabled ? "disabled" : ""}}>${{label}}</button>`;
      return `<article data-match="${{record.metadata_match}}" data-decision="${{decision}}">
        <div class="card-head">
          <h2>${{escapeHtml(record.metadata_title || record.local_title || record.source_dir)}}</h2>
          <div class="badges">
            ${{record.priority_archive ? '<span class="badge">優先アーカイブ</span>' : ""}}
            ${{record.metadata_tags.includes("僕のお気に入り")
              ? '<span class="badge">僕のお気に入り</span>' : ""}}
            ${{record.article_already_published
              ? '<span class="badge">元記事は公開済み</span>' : ""}}
            ${{record.duplicate_status !== "unique"
              ? `<span class="badge">${{escapeHtml(record.duplicate_status)}}</span>` : ""}}
            <span class="badge">${{escapeHtml(record.metadata_match)}}</span>
            <span class="badge">score ${{score}}</span>
            <span class="badge">${{escapeHtml(decision)}}</span>
          </div>
        </div>
        <div class="comparison">
          <section class="side">
            <h3>原稿側</h3>
            <dl>
              <dt>台帳番号</dt><dd><code>${{escapeHtml(record.record_id)}}</code></dd>
              <dt>場所</dt><dd>${{escapeHtml(record.source_dir || "—")}}</dd>
              <dt>既存題名</dt><dd>${{escapeHtml(record.local_title || "—")}}</dd>
              <dt>TeX</dt><dd>${{list(record.tex_files)}}</dd>
              <dt>PDF</dt><dd>${{list(record.pdf_files)}}</dd>
            </dl>
          </section>
          <section class="side">
            <h3>はてな候補</h3>
            <dl>
              <dt>記事名</dt><dd>${{escapeHtml(record.metadata_title || "—")}}</dd>
              <dt>公開日時</dt><dd>${{escapeHtml(record.metadata_published_at || "—")}}</dd>
              <dt>同日番号</dt><dd>${{record.metadata_sequence ?? "—"}}</dd>
              <dt>タグ</dt><dd>${{list(record.metadata_tags)}}</dd>
              <dt>PDF</dt><dd>${{list(record.metadata_pdf_files)}}</dd>
              <dt>根拠</dt><dd>${{escapeHtml(record.metadata_evidence || "—")}}</dd>
              <dt>記事</dt><dd>${{articleLink}}</dd>
            </dl>
          </section>
        </div>
        <div class="actions">
          ${{button("accepted", "採用", !canAccept)}}
          ${{button("held", "保留")}}
          ${{button("rejected", "却下")}}
          ${{button("pending", "未判定に戻す")}}
        </div>
      </article>`;
    }}
    function render() {{
      const shown = records.filter(visible);
      cards.innerHTML = shown.length ? shown.map(card).join("") :
        '<div class="empty">条件に一致する候補はありません。</div>';
      cards.querySelectorAll(".decision").forEach(element => {{
        element.addEventListener("click", () => {{
          const record = records.find(item => item.record_id === element.dataset.id);
          setDecision(record, element.dataset.value);
        }});
      }});
      const counts = {{pending: 0, accepted: 0, held: 0, rejected: 0}};
      records.forEach(record => counts[decisionOf(record)]++);
      summary.innerHTML = [
        `表示 ${{shown.length}} / ${{records.length}}件`,
        `未判定 ${{counts.pending}}`,
        `採用 ${{counts.accepted}}`,
        `保留 ${{counts.held}}`,
        `却下 ${{counts.rejected}}`,
        `生成日時 {html.escape(generated_at)}`
      ].map(value => `<span>${{value}}</span>`).join("");
    }}
    const years = [...new Set(records.map(recordYear))].sort();
    years.forEach(year => {{
      const option = document.createElement("option");
      option.value = year;
      option.textContent = year;
      yearFilter.appendChild(option);
    }});
    [
      query, matchFilter, decisionFilter, priorityFilter,
      tagFilter, scopeFilter, yearFilter
    ].forEach(element =>
      element.addEventListener(element === query ? "input" : "change", render));
    document.getElementById("copy-command").addEventListener("click", async () => {{
      const accepted = records.filter(record =>
        decisionOf(record) === "accepted" && ["exact", "likely"].includes(record.metadata_match));
      if (!accepted.length) return notify("採用済み候補がありません");
      const command = "python3 scripts/migration_ledger.py confirm-metadata " +
        accepted.map(record => JSON.stringify(record.record_id)).join(" ");
      try {{
        await navigator.clipboard.writeText(command);
        notify(`${{accepted.length}}件分の確定コマンドをコピーしました`);
      }} catch {{
        window.prompt("次のコマンドをコピーしてください", command);
      }}
    }});
    document.getElementById("export-decisions").addEventListener("click", () => {{
      const data = {{
        schema_version: 1,
        exported_at: new Date().toISOString(),
        decisions: records.map(record => ({{
          record_id: record.record_id,
          candidate_url: record.metadata_original_url,
          decision: decisionOf(record)
        }})).filter(item => item.decision !== "pending")
      }};
      const blob = new Blob([JSON.stringify(data, null, 2)], {{type: "application/json"}});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "metadata-review-decisions.json";
      link.click();
      URL.revokeObjectURL(link.href);
    }});
    document.getElementById("import-decisions").addEventListener("click", () =>
      document.getElementById("import-file").click());
    document.getElementById("import-file").addEventListener("change", async event => {{
      const file = event.target.files[0];
      if (!file) return;
      try {{
        const data = JSON.parse(await file.text());
        if (data.schema_version !== 1 || !Array.isArray(data.decisions)) throw new Error();
        for (const item of data.decisions) {{
          if (!["accepted", "held", "rejected"].includes(item.decision)) continue;
          decisions[item.record_id] = {{
            decision: item.decision,
            candidate_url: item.candidate_url || "",
            updated_at: new Date().toISOString()
          }};
        }}
        saveDecisions();
        render();
        notify("判定JSONを読み込みました");
      }} catch {{
        notify("判定JSONを読み込めませんでした");
      }}
      event.target.value = "";
    }});
    render();
  </script>
</body>
</html>
"""
