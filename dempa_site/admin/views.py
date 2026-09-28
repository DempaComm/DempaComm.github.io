"""HTML presentation for the loopback administration UI."""
from __future__ import annotations

import html
import json
from urllib.parse import quote
from .service import LocalAdmin, ReviewResult

LOCAL_ADMIN_TITLE = "数識電収 ローカル管理"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _csrf_field(app: LocalAdmin) -> str:
    return f'<input type="hidden" name="csrf" value="{_escape(app.csrf_token)}">'


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)} — {LOCAL_ADMIN_TITLE}</title>
<style>
body{{margin:0;background:#f6f7fb;color:#202431;font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:1060px;margin:0 auto;padding:28px 20px 64px}} h1{{margin:0 0 8px}} h2{{margin-top:34px}}
a{{color:#144ea0}} .muted{{color:#637083}} .card{{background:#fff;border:1px solid #d9deea;border-radius:12px;padding:18px;margin:14px 0}}
.ok{{color:#087443}} .warn{{color:#a35100}} .danger{{color:#a12222}} .status{{font-family:ui-monospace,SFMono-Regular,monospace}}
button{{background:#164e9b;color:#fff;border:0;border-radius:7px;padding:9px 14px;font:inherit;cursor:pointer}} button.warn{{background:#9a5000}} button.danger{{background:#9b2929}}
input[type=text]{{width:min(100%,620px);padding:8px;border:1px solid #aeb8c9;border-radius:6px;font:inherit}} pre{{white-space:pre-wrap;background:#161a22;color:#edf0f5;padding:14px;border-radius:8px;overflow:auto}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #e1e5ec;padding:8px;text-align:left;vertical-align:top}} .actions{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.pages{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}} .pages img{{display:block;width:100%;height:auto;border:1px solid #cbd2df;border-radius:6px}}
</style></head><body><main><p><a href="/">← 記事一覧</a></p>{body}</main></body></html>""".encode("utf-8")


def _message(title: str, message: str, *, output: str = "", good: bool = False) -> bytes:
    category = "ok" if good else "danger"
    block = f"<pre>{_escape(output)}</pre>" if output else ""
    return _page(title, f"<h1>{_escape(title)}</h1><p class=\"{category}\">{_escape(message)}</p>{block}")


def _dashboard(app: LocalAdmin) -> bytes:
    status = app.git_status()
    dirty = {path.split("/")[1] for _, path in status if path.startswith("papers/")}
    rows = []
    for manifest_path, paper in app.papers():
        changed = app.changed_files(manifest_path, paper)
        state = []
        if paper.slug in dirty:
            state.append("VS Codeの変更あり")
        if changed:
            state.append("未承認: " + ", ".join(sorted(changed)))
        if not state:
            state.append("変更なし")
        html_state = "HTMLあり" if paper.html_versions else "HTMLなし"
        rows.append(
            "<tr><td><a href=\"/papers/" + quote(paper.slug) + "\">"
            + _escape(paper.title) + "</a><br><span class=\"muted\">"
            + _escape(paper.slug) + "</span></td><td>" + _escape(html_state)
            + "</td><td>" + _escape(" / ".join(state)) + "</td></tr>"
        )
    changes = "\n".join(f"{code} {path}" for code, path in status) or "変更はありません"
    body = f"""<h1>{LOCAL_ADMIN_TITLE}</h1>
<p>原稿はVS Codeで編集します。この画面は、検査・HTML生成・公開準備だけを行います。Gitへのコミットとpushは行いません。</p>
<div class="card"><strong>作業ツリー</strong><pre>{_escape(changes)}</pre></div>
<div class="card actions"><form method="post" action="/actions/check-all">{_csrf_field(app)}<button class="warn">全体検査を実行</button></form>
<form method="post" action="/actions/prepare-baseline">{_csrf_field(app)}<button class="danger">公開差分を表示</button></form></div>
<h2>記事</h2><table><thead><tr><th>記事</th><th>HTML</th><th>状態</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"""
    return _page(LOCAL_ADMIN_TITLE, body)


def _paper_page(app: LocalAdmin, slug: str) -> bytes:
    manifest_path, paper = app.paper(slug)
    changed = app.changed_files(manifest_path, paper)
    git_rows = app.status_for_slug(slug)
    changed_rows = []
    for entry in paper.files:
        state = "未承認の変更" if entry.path in changed else "承認済み"
        checked = " checked" if entry.path in changed else ""
        changed_rows.append(
            f"<tr><td><input type=\"checkbox\" name=\"file\" value=\"{_escape(entry.path)}\"{checked}></td>"
            f"<td>{_escape(entry.path)}</td><td>{_escape(entry.role)}</td><td>{_escape(state)}</td></tr>"
        )
    git_text = "\n".join(f"{code} {path}" for code, path in git_rows) or "VS Codeからの未保存・未追跡変更はありません"
    html_note = "あり" if paper.html_versions else "なし"
    body = f"""<h1>{_escape(paper.title)}</h1><p class="muted">{_escape(slug)} · HTML版: {html_note}</p>
<div class="card"><strong>VS Codeの変更</strong><pre>{_escape(git_text)}</pre>
<p class="muted">新規BibTeX・図版など、paper.json未登録の公開ファイルはこの初期版では登録しません。先に移行手順を使ってください。</p></div>
<form class="card" method="post" action="/papers/{quote(slug)}/review">{_csrf_field(app)}<h2>1. 修正を検査</h2><p>変更した保護ファイルを選び、個人情報検査レポートを作ります。</p>
<table><thead><tr><th></th><th>ファイル</th><th>種類</th><th>状態</th></tr></thead><tbody>{''.join(changed_rows)}</tbody></table><p><button>変更を検査</button></p></form>
<form class="card" method="post" action="/papers/{quote(slug)}/finish">{_csrf_field(app)}<h2>2. 承認して事前検査</h2><p>PDF全ページと検査報告を確認した後だけ実行してください。選択した既存ファイルを承認し、古くなったHTML版があれば回復可能な隔離領域へ退避します。</p>
<input name="reason" type="text" required placeholder="修正理由"><p><label><input type="checkbox" name="privacy_reviewed" value="yes"> PDF全ページと個人情報検査報告を確認した</label></p>
<p><label><input type="checkbox" name="accept_public_change" value="yes"> 意図した公開差分だけを承認する</label></p>
<p>承認するファイル:</p><table><tbody>{''.join(changed_rows)}</tbody></table><p><button class="danger">承認して事前検査</button></p></form>
<div class="card"><h2>3. HTML版を生成</h2><p>未承認の原稿変更がない場合だけ、隔離領域に試験HTMLを生成します。</p><form method="post" action="/papers/{quote(slug)}/trial">{_csrf_field(app)}<button>HTML試験版を生成</button></form></div>"""
    return _page(paper.title, body)


def _result_page(app: LocalAdmin, slug: str, token: str, report: dict) -> bytes:
    item = report["results"][0]
    file_token = app.token_for(app._trials[token][1], f"{slug} のLaTeXML試験")
    html_path = item.get("html", "")
    result_link = ""
    if html_path:
        result_link = f'<p><a href="/files/{file_token}/{quote(html_path)}" target="_blank">試験HTMLを開く</a></p>'
    passed = bool(item.get("automatic_checks_passed"))
    reasons = "\n".join(item.get("blocking_reasons", [])) or "なし"
    publish = ""
    if passed:
        publish = f"""<form class="card" method="post" action="/papers/{quote(slug)}/publish">{_csrf_field(app)}
<input type="hidden" name="trial" value="{_escape(token)}"><h2>HTML版を公開登録</h2>
<p>PDFとHTMLを比較した後にだけ進めます。公開登録後は「全体検査」と「公開差分を表示」を行ってください。</p>
<label><input type="checkbox" name="reviewed" value="yes"> PDFと比較して公開してよいことを確認した</label><p><button class="danger">HTML版を公開登録</button></p></form>"""
    body = f"""<h1>HTML試験版</h1><p class="{'ok' if passed else 'danger'}">自動検査: {'合格' if passed else '不合格'}</p>{result_link}
<div class="card"><strong>停止理由</strong><pre>{_escape(reasons)}</pre><strong>変換処理</strong><pre>{_escape(json.dumps(item.get('source_normalizations', []), ensure_ascii=False, indent=2))}</pre></div>{publish}"""
    return _page("HTML試験版", body)


def _review_result_card(result: ReviewResult) -> str:
    report_link = ""
    pages = ""
    if result.token:
        report_link = (
            f' <a href="/files/{result.token}/report.txt" target="_blank">'
            "検査報告を開く</a>"
        )
        page_links = []
        for number, page in enumerate(result.rendered_pages, start=1):
            href = f"/files/{result.token}/{quote(page)}"
            page_links.append(
                f'<a href="{href}" target="_blank"><img src="{href}" '
                f'alt="{_escape(result.path)} {number}ページ"></a>'
            )
        if page_links:
            pages = (
                '<p><strong>PDF全ページ画像</strong></p><div class="pages">'
                + "".join(page_links)
                + "</div>"
            )
    return (
        f'<div class="card"><strong>{_escape(result.path)}</strong>{report_link}'
        f'<pre>{_escape(result.findings)}</pre>{pages}</div>'
    )


def _baseline_preview_page(
    app: LocalAdmin, token: str, differences: tuple[str, ...], checks: str
) -> bytes:
    rows = "".join(f"<li>{_escape(value)}</li>" for value in differences)
    body = f"""<h1>公開差分の確認</h1><p class="ok">公開基準以外の事前検査は成功しました。</p>
<pre>{_escape(checks)}</pre><div class="card"><h2>承認対象の公開差分</h2><ul>{rows}</ul></div>
<form class="card" method="post" action="/actions/write-baseline">{_csrf_field(app)}
<input type="hidden" name="preview" value="{_escape(token)}"><input name="reason" type="text" required placeholder="基準更新の理由">
<p><label><input type="checkbox" name="accept" value="yes"> 上記の公開差分をすべて確認した</label></p>
<button class="danger">確認した差分を公開基準へ反映</button></form>"""
    return _page("公開差分の確認", body)
