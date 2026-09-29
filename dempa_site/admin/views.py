"""HTML presentation for the loopback administration UI."""
from __future__ import annotations

import html
import json
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode
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
<link rel="stylesheet" href="/admin.css"><script src="/admin.js" defer></script>
</head><body><a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header"><div class="header-inner"><a class="brand" href="/">数識電収 <span>原稿の管理</span></a>
<nav aria-label="管理画面の案内"><a href="/">記事を選ぶ</a><a href="/#publish">公開前の確認</a><a href="/help">使い方</a></nav>
<span class="local-badge">このMacでの作業</span></div></header>
<main id="main">{body}</main>
<div id="busy-message" class="busy-message" role="status" hidden>処理中です。このまま結果が表示されるまでお待ちください。</div>
<footer>この画面では、このMacに保存した原稿を検査し、公開の準備をします。サイトへの反映は、その後の送信（push）で行います。</footer>
</body></html>""".encode("utf-8")


def _message(
    title: str, message: str, *, output: str = "", good: bool = False,
    next_url: str = "/", next_label: str = "記事一覧に戻る",
) -> bytes:
    category = "success" if good else "warning"
    block = (
        f'<details class="technical"{" open" if not good else ""}>'
        f'<summary>検査の詳細</summary><pre>{_escape(output)}</pre></details>'
        if output else ""
    )
    return _page(title, f"""<p class="eyebrow">操作の結果</p><h1>{_escape(title)}</h1>
<div class="notice {category}"><p>{_escape(message)}</p></div>{block}
<div class="actions"><a class="button" href="{_escape(next_url)}">{_escape(next_label)}</a><a href="/help">手順を確認する</a></div>""")


def _dashboard(app: LocalAdmin, query: str = "", view: str = "") -> bytes:
    status = app.git_status()
    dirty = {path.split("/")[1] for _, path in status if path.startswith("papers/") and len(path.split("/")) > 2}
    papers = [(paper, app.changed_files(path, paper)) for path, paper in app.papers()]
    pending = sum(bool(changed) for _, changed in papers)
    edited = sum(bool(changed) or paper.slug in dirty for paper, changed in papers)
    view = view if view in {"all", "changed"} else ("changed" if edited and not query else "all")
    terms = unicodedata.normalize("NFKC", query).casefold().split()
    papers.sort(key=lambda item: (not bool(item[1]), item[0].slug not in dirty, -item[0].order))
    rows = []
    for paper, changed in papers:
        if view == "changed" and not (changed or paper.slug in dirty):
            continue
        haystack = unicodedata.normalize("NFKC", " ".join([
            paper.title, paper.slug, *paper.tags, *[entry.path for entry in paper.files],
        ])).casefold()
        if any(term not in haystack for term in terms):
            continue
        if changed:
            state = '<span class="badge waiting">修正の確認待ち</span>'
            note = "修正したファイル：" + ", ".join(sorted(changed))
            action = "修正を確認する"
        elif paper.slug in dirty:
            state = '<span class="badge">保存済みの変更あり</span>'
            note = "登録済みファイルの内容は同じです。追加ファイルや記事情報の変更を確認してください。"
            action = "続きを開く"
        else:
            state = '<span class="badge quiet">登録内容と同じ</span>'
            note = ""
            action = "記事を開く"
        href = f"/papers/{quote(paper.slug)}"
        html_state = "HTML版あり" if paper.html_versions else "HTML版なし"
        rows.append(f"""<li class="article-row{' needs-review' if changed else ''}">
<div class="article-copy"><p class="article-meta">{_escape(paper.slug)} <span>・ {html_state}</span></p>
<h3><a href="{href}">{_escape(paper.title)}</a></h3><div>{state}</div>
{'<p class="file-note">' + _escape(note) + '</p>' if note else ''}</div>
<a class="button {'primary' if changed else 'secondary'}" href="{href}" aria-label="{_escape(paper.title)}：{action}">{action} →</a></li>""")
    changes = "\n".join(f"{code} {path}" for code, path in status) or "変更はありません"
    tabs = []
    for value, label in (("changed", f"修正した記事 {edited}"), ("all", f"すべての記事 {len(papers)}")):
        href = "/?" + urlencode({"view": value, "q": query}) + "#articles"
        current = ' aria-current="page"' if view == value else ""
        tabs.append(f'<a class="filter{" active" if view == value else ""}" href="{_escape(href)}"'
                    f'{current}>{label}</a>')
    notice = (
        f"<strong>修正の確認待ちが {pending} 件あります。</strong><span>記事を開いて、修正したファイルを検査してください。</span>"
        if pending else "<strong>登録済みの原稿に、未確認の修正はありません。</strong><span>原稿を保存したあとは、この画面を更新してください。</span>"
    )
    empty = '<li class="empty">該当する記事がありません。検索する言葉を短くするか、「すべての記事」を選んでください。</li>'
    body = f"""<p class="eyebrow">原稿の修正と公開準備</p><h1>修正する記事を選ぶ</h1>
<p class="lead">VS Codeで原稿を編集・保存したら、ここで修正内容を確認します。</p>
<ol class="workflow" aria-label="修正の流れ"><li><span>1</span><div><strong>原稿を直す</strong><small>VS Codeで編集・保存</small></div></li>
<li class="current"><span>2</span><div><strong>記事ごとに確認する</strong><small>修正の検査・登録、HTML版の更新</small></div></li>
<li><span>3</span><div><strong>公開前に確認する</strong><small>サイト全体を検査</small></div></li></ol>
<div class="notice {'warning' if pending else 'success'}">{notice}</div>
<section id="articles" aria-labelledby="articles-title"><div class="section-heading"><h2 id="articles-title">記事を探す</h2><a href="/">保存した変更を再確認 ↻</a></div>
<form class="search" method="get" action="/#articles"><label for="article-query">記事名・記事番号・ファイル名</label>
<div class="search-controls"><input id="article-query" type="search" name="q" value="{_escape(query)}" placeholder="例：星型、2024-07-21-01、StarDiffeo.tex">
<input type="hidden" name="view" value="all"><button>検索する</button>{'<a href="/?view=all#articles">検索を解除</a>' if query else ''}</div></form>
<nav class="filters" aria-label="記事の絞り込み">{''.join(tabs)}</nav>
<p class="muted result-count">{len(rows)} 件を表示 ・ 修正の確認待ちを先に、新しい記事から並べています。</p>
<ul class="article-list">{''.join(rows) or empty}</ul></section>
<section id="publish" class="card" aria-labelledby="publish-title"><p class="eyebrow">記事の作業が終わったら</p><h2 id="publish-title">公開前の確認</h2>
<p>修正の登録と、必要なHTML版の更新を終えてから進みます。公開するページに、どんな変更があるか確認できます。</p>
<div class="actions"><form method="post" action="/actions/prepare-baseline">{_csrf_field(app)}<button>公開前の検査と変更点の確認</button></form>
<a href="/help#publish">公開までの手順を読む →</a></div>
<details class="technical"><summary>検査だけを実行したいとき</summary><p>サイト全体の検査をします。未登録の修正や、まだ確認していない公開ページの変更がある場合は停止します。</p>
<form method="post" action="/actions/check-all">{_csrf_field(app)}<button class="secondary">サイト全体を検査する</button></form></details></section>
<details class="technical"><summary>詳しい変更一覧（システムのファイルを含む）</summary>
<p class="muted">保存されたファイルとGitの記録との違いです。エディタで保存していない変更は表示されません。</p><pre>{_escape(changes)}</pre></details>"""
    return _page("記事を選ぶ", body)


def _paper_page(app: LocalAdmin, slug: str) -> bytes:
    manifest_path, paper = app.paper(slug)
    changed = app.changed_files(manifest_path, paper)
    git_rows = app.status_for_slug(slug)
    changed_rows = []
    other_rows = []
    missing = []
    for entry in paper.files:
        exists = (manifest_path.parent / entry.path).is_file()
        if not exists:
            missing.append(entry.path)
        state = "ファイルが見つかりません" if not exists else ("修正の確認待ち" if entry.path in changed else "登録内容と同じ")
        row = (
            f'<tr><td><code>{_escape(entry.path)}</code></td>'
            f'<td>{_escape(entry.label)}</td><td>{state}</td></tr>'
        )
        (changed_rows if entry.path in changed else other_rows).append(row)
    git_text = "\n".join(f"{code} {path}" for code, path in git_rows) or "Gitの記録と異なる保存済みファイルはありません。"
    hidden_files = "".join(f'<input type="hidden" name="file" value="{_escape(path)}">' for path in sorted(changed))
    if changed:
        next_step = f"{len(changed)} 件の修正があります。下の「修正したファイルを検査する」から進めてください。"
        review = f"""<p>以下のファイルを検査します。次の画面で検査報告を読み、修正を登録します。</p>
<form method="post" action="/papers/{quote(slug)}/review">{_csrf_field(app)}{hidden_files}
<div class="table-scroll"><table><thead><tr><th>ファイル</th><th>内容</th><th>状態</th></tr></thead><tbody>{''.join(changed_rows)}</tbody></table></div>
{'<p class="warn">見つからないファイルを元に戻してから、この画面を開き直してください。</p>' if missing else ''}
<p><button{' disabled' if missing else ''}>修正したファイルを検査する</button></p></form>"""
    else:
        next_step = "登録済みの原稿に未確認の修正はありません。HTML版の更新、または公開前の確認へ進めます。"
        review = '<p class="ok">登録済みの原稿に未確認の修正はありません。</p><p>これから直す場合は、VS Codeで編集・保存し、このページを更新してください。</p>'
    has_tex = any(Path(entry.path).suffix.casefold() == ".tex" for entry in paper.files)
    html_note = "HTML版あり" if paper.html_versions else "HTML版なし"
    if has_tex:
        html_action = f"""<p>HTML版は、ブラウザで本文を読むためのページです。原稿を直した記事は、必要に応じて作り直します。</p>
{'<p class="muted">先に修正を検査・登録すると、このボタンを使えます。</p>' if changed else '<p>作成したHTMLをPDFと見比べてから、公開用のファイルとして登録します。</p>'}
<form method="post" action="/papers/{quote(slug)}/trial">{_csrf_field(app)}<button{' disabled' if changed else ''}>確認用のHTML版を作る</button></form>"""
    else:
        html_action = '<p>この記事にはTeX原稿がないため、この画面でのHTML変換は使いません。公開前の確認へ進んでください。</p>'
    body = f"""<p><a href="/">← 記事一覧に戻る</a></p><p class="eyebrow">記事の修正</p>
<h1 class="paper-title">{_escape(paper.title)}</h1><p class="muted">記事番号 {_escape(slug)} ・ {html_note}</p>
<div class="notice {'warning' if changed else 'success'}"><strong>次にすること</strong><span>{next_step}</span></div>
<section class="card" id="review"><p class="eyebrow">STEP 1</p><h2>修正したファイルを検査する</h2>{review}
<details class="technical"><summary>このほかの登録済みファイルを見る（{len(other_rows)} 件）</summary>
<div class="table-scroll"><table><thead><tr><th>ファイル</th><th>内容</th><th>状態</th></tr></thead><tbody>{''.join(other_rows)}</tbody></table></div></details></section>
<section class="card subdued"><p class="eyebrow">STEP 2 ・ 検査のあとの画面で行います</p><h2>内容を確認して、修正を登録する</h2>
<p>検査報告とPDFの全ページを確認し、修正理由を書いて登録します。自分で確認したことをチェックしてから進みます。</p></section>
<section class="card" id="html"><p class="eyebrow">STEP 3 ・ HTML版も更新するとき</p><h2>ブラウザで読む版を作る</h2>{html_action}</section>
<section class="card"><h2>記事の作業を終えたら</h2><p>ほかに直した記事があれば、同じ手順で確認してください。全部終わったらサイト全体を検査します。</p>
<a class="button secondary" href="/#publish">公開前の確認へ進む →</a></section>
<details class="technical"><summary>原稿の保存場所と、詳しい変更一覧</summary><p>保存場所</p><pre>{_escape(manifest_path.parent)}</pre>
<p>保存済みのファイルとGitの記録との違い</p><pre>{_escape(git_text)}</pre>
<p>新しい文献ファイルや図を追加した場合は、別途ファイルの登録が必要です。<a href="/help#new-files">追加したファイルについて</a></p></details>"""
    return _page(paper.title, body)


def _review_page(app: LocalAdmin, slug: str, results: list[ReviewResult]) -> bytes:
    cards = "".join(_review_result_card(result) for result in results)
    files = "".join(f'<input type="hidden" name="file" value="{_escape(result.path)}">' for result in results)
    body = f"""<p><a href="/papers/{quote(slug)}">← この記事に戻る</a></p><p class="eyebrow">STEP 2</p>
<h1>内容を確認して、修正を登録する</h1><p class="lead">検査報告を作りました。まだ修正の登録はしていません。</p>
<div class="notice"><strong>ここで確認すること</strong><span>報告に挙がった氏名・メールアドレスなどと、PDFの全ページを確認してください。TeXを直した場合は、手元で作り直したPDFを開いて確認します。</span></div>
{cards}<form class="card" method="post" action="/papers/{quote(slug)}/finish">{_csrf_field(app)}{files}
<h2>確認が終わったら</h2><label class="field-label" for="reason">修正理由</label>
<input id="reason" name="reason" type="text" required placeholder="例：定理2の誤植を修正した">
<label class="check-line"><input type="checkbox" name="privacy_reviewed" value="yes" required> PDFの全ページと検査報告を自分で確認した</label>
<label class="check-line"><input type="checkbox" name="accept_public_change" value="yes" required> 今回の修正内容を確認し、公開用として登録してよい</label>
<p class="muted">登録すると修正理由を記録し、全体検査を行います。古くなったHTML版は控えを残して外します。サイトへの反映は、最後の送信（push）のあとです。</p>
<button>この修正を登録して検査する</button></form>
<p>検査後に原稿をもう一度直した場合は、<a href="/papers/{quote(slug)}#review">この記事に戻って検査し直してください</a>。</p>"""
    return _page("修正内容の確認", body)


def _result_page(app: LocalAdmin, slug: str, token: str, report: dict) -> bytes:
    item = report["results"][0]
    file_token = app.token_for(app._trials[token][1], f"{slug} のLaTeXML試験")
    html_path = item.get("html", "")
    result_link = ""
    if html_path:
        result_link = f'<p><a class="button secondary" href="/files/{file_token}/{quote(html_path)}" target="_blank" rel="noopener">作成したHTML版を開く ↗</a></p>'
    passed = bool(item.get("automatic_checks_passed"))
    reasons = "\n".join(item.get("blocking_reasons", [])) or "なし"
    publish = ""
    if passed:
        publish = f"""<form class="card" method="post" action="/papers/{quote(slug)}/publish">{_csrf_field(app)}
<input type="hidden" name="trial" value="{_escape(token)}"><h2>PDFと見比べて確認する</h2>
<p>数式・図・参照番号・本文に欠けや崩れがないか、手元のPDFと比較してください。</p>
<label class="check-line"><input type="checkbox" name="reviewed" value="yes" required> PDFと見比べて、公開してよいことを自分で確認した</label>
<p><button>このHTML版を公開用に登録する</button></p><p class="muted">登録後は「公開前の確認」へ進みます。サイトへの反映は、最後の送信（push）のあとです。</p></form>"""
    body = f"""<p><a href="/papers/{quote(slug)}#html">← この記事に戻る</a></p><p class="eyebrow">STEP 3</p>
<h1>{'HTML版ができました' if passed else 'HTML版の確認が必要です'}</h1>
<div class="notice {'success' if passed else 'warning'}"><strong>{'自動検査を通過しました。続けてPDFと見比べてください。' if passed else '自動検査で問題が見つかりました。まだ公開用に登録できません。'}</strong></div>{result_link}
{'' if passed else '<div class="card"><h2>確認が必要な点</h2><pre>' + _escape(reasons) + '</pre></div>'}{publish}
<details class="technical"><summary>変換処理の詳細</summary><pre>{_escape(json.dumps(item.get('source_normalizations', []), ensure_ascii=False, indent=2))}</pre></details>"""
    return _page("HTML版の確認", body)


def _review_result_card(result: ReviewResult) -> str:
    report_link = ""
    pages = ""
    if result.token:
        report_link = (
            f' <a href="/files/{result.token}/report.txt" target="_blank" rel="noopener">'
            "検査報告を開く</a>"
        )
        page_links = []
        for number, page in enumerate(result.rendered_pages, start=1):
            href = f"/files/{result.token}/{quote(page)}"
            page_links.append(
                f'<a href="{href}" target="_blank" rel="noopener"><img src="{href}" '
                f'alt="{_escape(result.path)} {number}ページ"></a>'
            )
        if page_links:
            pages = (
                '<p><strong>PDF全ページ画像</strong></p><div class="pages">'
                + "".join(page_links)
                + "</div>"
            )
    return (
        f'<div class="card"><h2 class="file-heading">{_escape(result.path)}</h2>{report_link}'
        f'<pre>{_escape(result.findings)}</pre>{pages}</div>'
    )


def _baseline_preview_page(
    app: LocalAdmin, token: str, differences: tuple[str, ...], checks: str
) -> bytes:
    labels = {"changed": "変更", "added": "追加", "removed": "削除"}
    rows = "".join(
        f'<li><span class="badge">{_escape(labels.get(value.partition(": ")[0], "確認"))}</span> '
        f'<code>{_escape(value.partition(": ")[2] or value)}</code></li>'
        for value in differences
    )
    body = f"""<p><a href="/#publish">← 公開前の確認に戻る</a></p><p class="eyebrow">公開前の確認</p>
<h1>公開するページの変更点</h1><div class="notice success"><strong>事前の検査を通過しました。</strong><span>下の一覧が、前回確認した状態から変わるファイルです。今回の修正に関係する変更だけか確認してください。</span></div>
<div class="card"><h2>変更されるファイル（{len(differences)} 件）</h2><ul class="difference-list">{rows}</ul></div>
<form class="card" method="post" action="/actions/write-baseline">{_csrf_field(app)}
<input type="hidden" name="preview" value="{_escape(token)}"><label class="field-label" for="baseline-reason">今回の変更理由</label>
<input id="baseline-reason" name="reason" type="text" required placeholder="例：記事の誤植修正とHTML版の更新">
<label class="check-line"><input type="checkbox" name="accept" value="yes" required> 一覧をすべて確認し、今回の修正で意図した変更だけである</label>
<button>確認した変更を記録する</button><p class="muted">次回の検査で比較する基準を更新します。実際の公開は、このあとGitで記録（commit）して送信（push）します。</p></form>
<details class="technical"><summary>事前検査の詳細</summary><pre>{_escape(checks)}</pre></details>"""
    return _page("公開するページの変更点", body)


def _help_page() -> bytes:
    return _page("使い方", """<p class="eyebrow">管理画面の使い方</p><h1>原稿を直して、公開するまで</h1>
<p class="lead">本文の編集はVS Codeで行います。保存した修正を、この画面で順番に確認します。</p>
<section class="card"><h2>1. 原稿を編集して保存する</h2><p>修正するTeXなどをVS Codeで開きます。修正後にPDFを作り直し、数式や図も含めて全ページを確認してください。</p>
<p>保存できたら、<a href="/">記事一覧</a>を開きます。すでに開いていた場合は「保存した変更を再確認」を押してください。</p></section>
<section class="card"><h2>2. 記事を選び、修正を検査する</h2><p>「修正した記事」から選びます。見つからないときは、記事名・記事番号・ファイル名で検索できます。</p>
<p>記事を開き、「修正したファイルを検査する」を押します。検査報告の氏名・メールアドレスなどを確認し、PDFも全ページ確認します。</p></section>
<section class="card"><h2>3. 確認した修正を登録する</h2><p>検査結果の下に修正理由を書き、自分で確認した2項目にチェックを入れて「この修正を登録して検査する」を押します。</p>
<p>原稿の修正が登録され、全体検査が走ります。古い原稿から作られたHTML版は、控えを残して外されます。</p></section>
<section class="card"><h2>4. HTML版も更新する</h2><p>HTML版は、ブラウザで本文を読むためのページです。必要な記事では「確認用のHTML版を作る」を押します。</p>
<p>できたHTML版を開いてPDFと見比べ、数式・図・参照番号・本文を確認します。問題がなければ確認欄にチェックを入れ、「このHTML版を公開用に登録する」を押します。</p>
<p>PDFだけで公開する記事は、この手順を飛ばせます。</p></section>
<section class="card" id="publish"><h2>5. サイト全体を確認して、公開する</h2><p>修正したすべての記事の作業を終えたら、<a href="/#publish">公開前の確認</a>で「公開前の検査と変更点の確認」を押します。</p>
<p>表示された変更をすべて確認し、理由と確認チェックを入れて「確認した変更を記録する」を押します。</p>
<p>最後に、意図したファイルだけをGitで記録（commit）し、送信（push）します。GitHub Actionsのbuild・deployが成功したら、公開サイトで修正を確認してください。</p>
<p>Codexに公開まで依頼するときは、対象記事を添えて「この修正をcommitしてpushして」と伝えられます。</p></section>
<section class="card"><h2>途中で原稿をもう一度直したとき</h2><p>保存してから記事の画面に戻り、「修正したファイルを検査する」からやり直します。古い検査報告では登録できません。</p>
<h2>検査で止まったとき</h2><p>画面の説明と「検査の詳細」を確認してください。Codexにその内容を伝えると、原因を調べられます。修正の登録後に止まった場合は、その旨が表示されます。</p>
<h2 id="new-files">新しい文献ファイルや図を追加したとき</h2><p>この画面は登録済みファイルの修正用です。新しく追加したファイルは別途登録が必要なので、Codexに記事番号とファイル名を伝えて依頼してください。</p></section>
<a class="button" href="/">記事を選ぶ →</a>""")
