"""Generate a human-readable lineage for every archived manuscript."""

from __future__ import annotations

import html
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page
from dempa_site.files import write_json
from dempa_site.manifests.model import Paper


_KIND_LABELS = {
    "published": "電波通信で初出",
    "migration": "数識電収へ収録",
    "revision": "保護原稿を改訂",
    "html": "HTML版を生成",
    "html-review": "HTML版を目視確認",
    "typst": "Typst版を生成",
    "correction": "訂正",
    "addendum": "追記",
}


def _events(paper: Paper) -> list[dict[str, str]]:
    events = [
        {
            "recorded_at": paper.published_at_text,
            "kind": "published",
            "summary": "電波通信での初出",
        }
    ]
    events.extend(
        {
            "recorded_at": event.recorded_at,
            "kind": event.kind,
            "summary": event.summary,
        }
        for event in paper.history
    )
    events.extend(
        {
            "recorded_at": change.approved_at,
            "kind": "revision",
            "summary": f"公開原稿を改訂（{len(change.files)}ファイル）",
        }
        for change in paper.approved_changes
    )
    for version in paper.html_versions:
        href = f"../papers/{paper.slug}/{version.path}"
        events.append(
            {
                "recorded_at": version.generated_at,
                "kind": "html",
                "summary": version.label,
                "href": href,
            }
        )
        if version.status == "approved" and version.reviewed_at != version.generated_at:
            events.append(
                {
                    "recorded_at": version.reviewed_at,
                    "kind": "html-review",
                    "summary": "PDFと比較して公開を承認",
                    "href": href,
                }
            )
    for correction in paper.corrections:
        href = f"../papers/{paper.slug}/"
        if correction.anchor and paper.html_version is not None:
            href += paper.html_version.path + correction.anchor
        events.append(
            {
                "recorded_at": correction.recorded_at,
                "kind": correction.kind,
                "summary": correction.summary,
                "href": href,
            }
        )
    unique = {
        (event["recorded_at"], event["kind"], event["summary"], event.get("href", "")): event
        for event in events
    }
    return sorted(unique.values(), key=lambda event: event["recorded_at"])


def _rendered_timeline(paper: Paper) -> str:
    items = []
    for event in _events(paper):
        date = event["recorded_at"][:10]
        label = _KIND_LABELS.get(event["kind"], event["kind"])
        summary = html.escape(event["summary"])
        if event.get("href"):
            summary = (
                f'<a href="{html.escape(event["href"], quote=True)}">{summary}</a>'
            )
        items.append(
            f"""          <li>
            <time datetime="{html.escape(event['recorded_at'], quote=True)}">{html.escape(date)}</time>
            <div><strong>{html.escape(label)}</strong><p>{summary}</p></div>
          </li>"""
        )
    if paper.migration_record_id:
        items.append(
            f"""          <li class="lineage-undated">
            <span>日付未記録</span>
            <div><strong>数識電収へ収録</strong><p>移行台帳 {html.escape(paper.migration_record_id)}</p></div>
          </li>"""
        )
    relations = ""
    if paper.relations:
        links = "".join(
            f'<li><a href="#paper-{html.escape(relation.target_slug, quote=True)}">'
            f'{html.escape(relation.label or relation.target_slug)}</a> '
            f'<span>({html.escape(relation.kind)})</span></li>'
            for relation in paper.relations
        )
        relations = f"<h3>明示された関係</h3><ul class=\"lineage-relations\">{links}</ul>"
    return f"""      <details class="lineage-paper" id="paper-{html.escape(paper.slug, quote=True)}">
        <summary><span>{html.escape(paper.title)}</span><span>{len(items)}項目</span></summary>
        <div class="lineage-paper-body">
          <p><a href="../papers/{html.escape(paper.slug, quote=True)}/">原稿ページを開く</a></p>
          <ol class="lineage-timeline">
{chr(10).join(items)}
          </ol>
          {relations}
        </div>
      </details>"""


def generate_lineage(catalog: SiteCatalog, output: Path) -> None:
    target = output / "lineage"
    target.mkdir(parents=True)
    papers = [paper for _, paper in catalog.selected]
    timelines = "\n".join(_rendered_timeline(paper) for paper in papers)
    body = f"""    <section aria-labelledby="lineage-title">
      <div class="section-heading">
        <h2 id="lineage-title">原稿ごとの記録</h2>
        <p>初出、移行、改訂、HTML化、目視確認、訂正・追記を同じ時間軸に置きます。</p>
      </div>
      <p class="lineage-note">移行日は旧資料に記録がないため「日付未記録」と表示します。今後の出来事は <code>paper.json</code> の <code>history</code> に追加できます。</p>
      <div class="lineage-list">
{timelines}
      </div>
    </section>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="原稿の系譜",
            eyebrow="MANUSCRIPT LINEAGE",
            description="電波通信での初出から、移行、改訂、HTML化、訂正・追記までを原稿ごとに追います。",
            canonical_path="/lineage/",
            body=body,
            body_class="lineage-page",
        ),
        encoding="utf-8",
    )
    write_json(
        target / "lineage.json",
        {
            "schema_version": 1,
            "papers": [
                {
                    "slug": paper.slug,
                    "title": paper.title,
                    "migration_record_id": paper.migration_record_id,
                    "events": _events(paper),
                    "relations": [
                        {
                            "target_slug": relation.target_slug,
                            "kind": relation.kind,
                            "label": relation.label,
                        }
                        for relation in paper.relations
                    ],
                }
                for paper in papers
            ],
        },
    )
