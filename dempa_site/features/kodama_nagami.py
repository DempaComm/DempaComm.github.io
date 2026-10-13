"""A bibliography guide with the handoff's correspondence and evidence limits."""

from __future__ import annotations

from collections import defaultdict
import html
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote

from dempa_site.config import SITE_URL
from dempa_site.features.exploration_common import rendered_exploration_page

DATA_ROOT = Path(__file__).resolve().parents[2] / "content" / "kodama-nagami"
MANUAL_LIST_SLUG = "2016-12-09-01"
PAGES = (("", "案内"), ("references", "文献一覧"), ("correspondence", "本文との対応"),
         ("afterword", "あとがきの文献"), ("notes", "推定と付記"))


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def prose(value) -> str:
    """Render source summaries safely, including the handoff's simple TeX text."""
    if isinstance(value, dict):
        return "<dl>" + "".join(f"<dt>{esc(k)}</dt><dd>{prose(v)}</dd>" for k, v in value.items()) + "</dl>"
    if isinstance(value, list):
        return "".join(prose(v) for v in value)
    text = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", str(value))
    text = re.sub(r"T_\{?([124])\}?", lambda m: "T" + m[1].translate(str.maketrans("124", "₁₂₄")), text)
    text = text.replace("$", "")
    return "".join(f"<p>{esc(line)}</p>" for line in text.splitlines() if line.strip())


def read_data() -> dict:
    return json.loads((DATA_ROOT / "bibliography.json").read_text(encoding="utf-8"))


def validate_kodama_nagami(_catalog) -> None:
    data = read_data()
    ids = [r["id"] for r in data["records"]]
    mids = [m["id"] for m in data["matches"]]
    if len(ids) != len(set(ids)) or len(mids) != len(set(mids)):
        raise ValueError("参考文献または対応の識別子が重複しています")
    if not {m["record_id"] for m in data["matches"]} <= set(ids):
        raise ValueError("本文対応の参照文献がありません")
    if not {r for n in data["inferred"] for k in ("selected_record_ids", "supporting_record_ids") for r in n[k]} <= set(ids):
        raise ValueError("推定表の参照文献がありません")
    for key, value in (("records", len(ids)), ("correspondences", len(mids)),
                       ("inferred_items", len(data["inferred"])), ("afterword_items", len(data["afterword"]))):
        if data["summary"][key] != value:
            raise ValueError(f"{key} の件数が一致しません")
    if not {c["record_id"] for a in data["afterword"] for c in a["citations"]} <= set(ids):
        raise ValueError("あとがきの参照文献がありません")
    for m in data["matches"]:
        book = m["book"]
        if "statement" in book or not isinstance(book.get("summary"), str) or not 1 <= len(book["summary"]) <= 140:
            raise ValueError("本書の説明は原文の記述を含まない短い要約にしてください")
    if any("statement" in x for x in data["book_conventions"]):
        raise ValueError("本書の規約は要約で掲載してください")
    for text in ((DATA_ROOT / "bibliography.json").read_text(), (DATA_ROOT / "kodama-nagami.bib").read_text()):
        if "/Users/" in text or re.search(r'(?:sources|evidence)/', text):
            raise ValueError("公開用データにローカル資料パスが残っています")
        if re.search(r"スキャン|写真|画像|OCR|レンダリング|見開き", text):
            raise ValueError("公開用データに非公開の取得・加工方法が残っています")


def chapter_for(data, section) -> str:
    return next((c["label"] for c in data["chapters"] if c["section_first"] <= section <= c["section_last"]), "")


def ref_link(record, prefix="../references/") -> str:
    return f'<a href="{prefix}#ref-{esc(record["id"])}">{esc(record["authors"])}，<cite>{esc(record["title"])}</cite>（{esc(record["year"])}）</a>'


def source_list(items) -> str:
    return '<ul class="kn-sources">' + "".join(
        "<li>" + (f'<a href="{esc(s["url"])}">{esc(s["label"])}</a>' if s["url"] else esc(s["label"]))
        + prose(s["scope"]) + "</li>" for s in items) + "</ul>"


def filter_controls(data, *, references=False) -> str:
    chapters = "".join(f'<option value="{esc(c["label"])}">{esc(c["label"])}　{esc(c["title"])}</option>' for c in data["chapters"])
    sections = "".join(f'<option value="{s["number"]}">§{s["number"]}　{esc(s["title"])}</option>' for s in data["sections"])
    extra = '''<label>対応の種類<select name="relationship"><option value="">すべて</option><option value="body">本文の特定箇所を照合</option><option value="afterword">あとがきに書誌指定</option><option value="inferred">推定・適用範囲の付記あり</option><option value="related">上記の対応がない関連候補</option></select></label>
<label>刊行時期<select name="era"><option value="">すべて</option><option value="early">初版刊行年以前・年未詳</option><option value="later">1974年より後の補助資料</option></select></label>''' if references else ""
    return f'''<form id="kn-search" class="kn-filters" data-kn-filter hidden role="search">
<label class="kn-query">著者・題名・本の頁・番号・付記を検索<input name="q" type="search" placeholder="例：Morita，47.25，箱位相"></label>
<label>章<select name="chapter"><option value="">すべての章</option>{chapters}</select></label>
<label>節<select name="section"><option value="">すべての節</option>{sections}</select></label>{extra}
<button type="reset">絞り込みを解除</button></form>
<p class="kn-result" data-kn-count aria-live="polite"></p>
<p data-kn-empty hidden>該当する項目がない．検索語や絞り込みを変えると探し直せる．</p>
<noscript><p>以下に全項目を掲載している．ブラウザーの「ページ内を検索」でも著者や番号を探せる．</p></noscript>'''


def intro(data, manual_list_url: str) -> str:
    s = data["summary"]
    chapters = []
    for c in data["chapters"]:
        sections = "".join(f'<a href="references/?section={x["number"]}">§{x["number"]} {esc(x["title"])}</a>'
                           for x in data["sections"] if c["section_first"] <= x["number"] <= c["section_last"])
        chapters.append(f'''<article class="kn-chapter"><p class="kn-kicker">{esc(c["label"])}・原本{c["page_start"]}頁から</p>
<h3><a href="references/?chapter={quote(c["label"])}">{esc(c["title"])}</a></h3><details><summary>この章の節から探す</summary><div class="kn-section-links">{sections}</div></details></article>''')
    return f'''<section class="kn-intro" aria-labelledby="kn-about"><p class="kn-kicker">1974年の本から文献をたどる</p>
<h2 id="kn-about">児玉・永見を読むための文献案内</h2>
<p>この文献案内は，<strong>電波通信の著者が人力で作成した参考文献リスト</strong>を引き継ぎ，AIを用いて整理・拡充したものである．</p>
<p>児玉之宏・永見啓応『位相空間論』（岩波書店，1974年）を読みながら，定理や演習の背景を原論文で確かめたい．そのために，書誌情報，本書との対応，照合するときの注意を一緒に調べられるようにした．<a href="{esc(data["book"]["source"])}">本書の図書館書誌</a>も参照できる．</p>
<p>もとのリストは，2016年の記事「&quot;児玉・永見&quot;の参考文献（未完）」である．<a href="{esc(manual_list_url)}">数識電収内の紹介ページ</a>と，<a href="{esc(data["source_blog"])}">電波通信の元の記事</a>を参照できる．本書の記載を原誌，出版社，図書館書誌，後続論文の引用と照合し，文献と対応の記録を追加した．</p>
<div class="kn-stats"><a href="references/"><strong>{s["records"]}</strong><span>文献を探す</span></a><a href="correspondence/"><strong>{s["correspondences"]}</strong><span>本文との個別対応を読む</span></a><a href="notes/"><strong>{s["inferred_items"]}</strong><span>推定理由と留保を読む</span></a></div>
<p class="kn-date">{esc(data["imported_on"])}に調査記録を取り込んだ．分冊・翻訳を分けたBibTeXは{s["bibtex_entries"]}項目である．</p></section>
<section class="kn-reading" aria-labelledby="kn-how"><h2 id="kn-how">探すときの手順</h2>
<ol><li>読んでいる章や節から<a href="references/">文献一覧</a>を開く．著者名・題名・定理番号でも検索できる．</li>
<li><a href="correspondence/">本文との対応</a>で，本書の所在と原論文の所在，仮定や結論の比較を読む．</li>
<li>原典の確認に条件が残る場合は，<a href="notes/">推定と付記</a>で採用理由と留保を確かめる．</li></ol>
<div class="kn-note"><strong>「本の頁」は1974年原本に印刷された頁番号である．</strong><p>定理・命題・演習・問題の番号も原本の番号を使う．</p></div></section>
<section aria-labelledby="kn-chapters"><h2 id="kn-chapters">章・節から探す</h2><div class="kn-chapters">{"".join(chapters)}</div></section>
<section class="kn-reading" aria-labelledby="kn-examples"><h2 id="kn-examples">文献をたどる三つの入口</h2>
<div class="kn-examples"><article><h3>完備化と逆スペクトル</h3><p>Moritaの <cite>Topological completions and M-spaces</cite>（1970年）は，あとがき5に指定された文献である．本書39.2・39.4との対応では，原文の定理と補足論証の範囲を付記している．</p><a href="references/#ref-Morita1970Completions">Moritaの文献と付記を読む</a></article>
<article><h3>本書に掲げられた問題</h3><p>ArhangelskijのICM講演録は，1970年の会議を1971年に刊行した資料である．本書47節などの問題について，問いの定式化と帰属を照合した箇所を探せる．</p><a href="references/#ref-Arhangelskii1971ICMSurvey">会議録と問題の対応を読む</a></article>
<article><h3>空間族の生成</h3><p>Nagamiの <cite>Minimal class generated by open compact and perfect mappings</cite>（1973年）は，あとがき10に誌名・巻・年が記されている．あとがきの指定と，本文の特定箇所との対応をそれぞれ参照できる．</p><a href="references/#ref-Nagami1973Generated">Nagamiの文献を読む</a></article></div></section>
<section class="kn-reading" aria-labelledby="kn-scope"><h2 id="kn-scope">記録の読み方</h2>
<dl class="kn-definitions"><dt>書誌を確認した</dt><dd>著者・題名・掲載誌・巻頁などを確認したことを表す．原論文の通読や証明の検証とは別である．</dd>
<dt>本文の特定箇所を照合した</dt><dd>本書と原論文の定義，主張，問題文などを比較したことを表す．{s["correspondences"]}件には，一部だけの対応や条件付きの対応も含む．各項目の確認範囲を読む必要がある．</dd>
<dt>推定・関連文献を採用した</dt><dd>直接の確定に条件が残る項目も，後続の引用，書評，回想，限定された対応を根拠に案内へ採用した．理由と留保を併記している．</dd></dl>
<p>1974年の初版刊行後の{s["post1974_records"]}文献は，後年の照合や歴史を知るための補助資料として表示する．本書全出典の網羅，著者が実際に使った文献の確定，歴史的な初出，独立した証明監査は，この案内の認定範囲に含めない．</p>
<p>保存資料の登録は{s["saved_document_records"]}文献・{s["unique_saved_pdfs"]}PDFである．プレビューや関連資料も含むため，原論文の全文を同数入手したという意味ではない．各文献に保存・閲読範囲の付記がある．</p>
<p><a href="kodama-nagami.bib" download>BibTeXを保存する（{s["bibtex_entries"]}項目）</a>　／　<a href="bibliography.json" download>書誌・対応・付記のデータを保存する</a></p></section>'''


def references_page(data) -> str:
    matches = defaultdict(list)
    notes = defaultdict(list)
    mentions = defaultdict(list)
    for m in data["matches"]:
        matches[m["record_id"]].append(m)
    for n in data["inferred"]:
        for ident in n["selected_record_ids"]:
            notes[ident].append(n)
    for a in data["afterword"]:
        for c in a["citations"]:
            mentions[c["record_id"]].append((a, c))
    cards = []
    for r in data["records"]:
        ident = r["id"]
        sections = set(r["candidate_sections"]) | {m["section"] for m in matches[ident]}
        chapters = set(r["chapters"]) | {chapter_for(data, s) for s in sections}
        if "序章・第1章" in chapters:
            chapters.update(("序章", "第1章"))
        relationships = [key for key, values in (("body", matches[ident]), ("afterword", mentions[ident]), ("inferred", notes[ident])) if values] or ["related"]
        era = "later" if r["published_after_book_first_edition"] else "early"
        badges = [f'<span class="kn-badge">{esc(r["status_label"])}</span>']
        if era == "later":
            badges.append('<span class="kn-badge kn-later">1974年より後の補助資料</span>')
        if matches[ident]: badges.append(f'<span class="kn-badge">本文の個別対応 {len(matches[ident])}件</span>')
        if mentions[ident]: badges.append('<span class="kn-badge">あとがきの指定あり</span>')
        if notes[ident]: badges.append('<span class="kn-badge kn-inferred">推定・適用範囲の付記あり</span>')
        metadata = "，".join(str(r[k]) for k in ("journal", "booktitle", "series", "publisher") if r.get(k))
        if r.get("volume"): metadata += f'，第{r["volume"]}巻'
        if r.get("number"): metadata += f'，{r["number"]}号' if r.get("journal") else f'，No. {r["number"]}'
        if r.get("pages"): metadata += f'，{r["pages"]}頁'
        links = []
        if r.get("url"): links.append(f'<a href="{esc(r["url"])}">原誌・書誌のページへ</a>')
        if r.get("doi"): links.append(f'<a href="https://doi.org/{esc(r["doi"])}">DOI: {esc(r["doi"])}</a>')
        variants = "".join('<li>' + esc("，".join(str(v[k]) for k in ("id", "title", "year", "volume", "translator", "note") if v.get(k))) + '</li>' for v in r.get("bib_variants", []))
        bib_keys = "，".join(v["id"] for v in r.get("bib_variants", [])) or ident
        details = "".join('<h4>付記</h4>' + prose(r[k]) for k in ("note", "correction", "blog_errors", "afterword_relationship_note", "citation_disambiguation", "unverified_fields", "source_reading_note") if r.get(k))
        details += "".join('<h4>確認資料と閲読範囲</h4>' + prose(r[k]) for k in ("saved_document_scope", "local_pdf_scope", "local_pdf_label", "source_pdf_completeness", "verified_text_edition", "verified_edition") if r.get(k))
        if variants: details += f'<h4>分冊・翻訳別の書誌</h4><ul>{variants}</ul>'
        if matches[ident]:
            details += '<h4>本文の特定箇所との対応</h4><ul>' + "".join(f'<li><a href="../correspondence/#match-{esc(m["id"])}">原本{esc(m["book"]["page"])}頁・{esc(m["book"]["kind"])} {esc(m["book"]["number"])}</a> — {esc(m["comparison_type"])}</li>' for m in matches[ident]) + '</ul>'
        if mentions[ident]:
            details += '<h4>あとがきの文献指定</h4><ul>' + "".join(f'<li><a href="../afterword/#afterword-{a["number"]}">あとがき{a["number"]}（原本{a["page"]}頁）</a>：{esc(c["identification"])}</li>' for a, c in mentions[ident]) + '</ul>'
        if notes[ident]:
            details += '<h4>推定理由・適用範囲の付記</h4><ul>' + "".join(f'<li><a href="../notes/#note-{esc(n["id"])}">原本{esc(n["book_page"])}頁・{esc(n["book_number"])}：{esc(n["adoption"])}</a></li>' for n in notes[ident]) + '</ul>'
        if r["candidate_sections"]:
            details += '<h4>主題から選んだ節対応候補</h4><p>' + "，".join(f'§{s}' for s in r["candidate_sections"]) + '</p>' + prose(r["candidate_reason"])
        if r["correspondence_note"]: details += '<h4>対応に関する調査付記</h4>' + prose(r["correspondence_note"])
        details += '<h4>確認に使った資料と範囲</h4>' + source_list(r["sources"])
        cards.append(f'''<article class="kn-card" id="ref-{esc(ident)}" data-kn-item data-chapter="{esc('|'.join(sorted(chapters)))}" data-section="{esc('|'.join(str(s) for s in sorted(sections)))}" data-relationship="{'|'.join(relationships)}" data-era="{era}">
<div class="kn-badges">{"".join(badges)}</div><p class="kn-byline">{esc(r["authors"])}（{esc(r["year"])}）</p><h3>{esc(r["title"])}</h3>
<p class="kn-citation">{esc(metadata)}</p><p class="kn-key">BibTeXの識別子：<code>{esc(bib_keys)}</code></p><p class="kn-links">{'　／　'.join(links)}</p>
<details><summary>対応・付記・確認資料を読む</summary>{details}</details></article>''')
    return '<section><h2>書誌と対応を一緒に探す</h2><p>書誌確認の状態と，本書との対応の種類を別々に表示している．節の絞り込みには，主題から選んだ候補と本文の個別対応の両方を含む．各項目で根拠を確かめられる．</p>' + filter_controls(data, references=True) + '<div class="kn-list">' + "".join(cards) + '</div></section>'


def correspondence_page(data) -> str:
    records = {r["id"]: r for r in data["records"]}
    cards = []
    for m in sorted(data["matches"], key=lambda x: (int(re.search(r"\d+", str(x["book"]["page"]))[0]), str(x["book"]["number"]), x["id"])):
        book, paper = m["book"], m["paper"]
        kind = {"theorem": "定理", "definition": "定義", "exercise": "演習", "prose": "叙述", "statement": "主張", "construction": "構成"}.get(book["kind"], book["kind"])
        details = '<h4>照合した範囲</h4>' + prose(m["verified_scope"])
        if book.get("condition_scope"):
            details += '<h4>本書の条件に関する付記</h4>' + prose(book["condition_scope"])
        if m.get("scope_limitation"): details += '<div class="kn-note"><h4>留保</h4>' + prose(m["scope_limitation"]) + '</div>'
        details += '<h4>原文の確認に関する付記</h4>' + prose(m["source_reading_note"])
        for key, label in (("additional_book_sources", "本書内で併せて確認した所在"), ("additional_paper_sources", "原文献内で併せて確認した所在")):
            if m[key]: details += f'<h4>{label}</h4>' + "".join(prose("，".join(str(v) for v in x.values())) for x in m[key])
        if m.get("supporting_match_ids"):
            details += '<h4>関連する対応</h4><ul>' + "".join(f'<li><a href="#match-{esc(ident)}">{esc(ident)}</a></li>' for ident in m["supporting_match_ids"]) + '</ul>'
        cards.append(f'''<article class="kn-card" id="match-{esc(m["id"])}" data-kn-item data-chapter="{esc(chapter_for(data, m["section"]))}" data-section="{m["section"]}">
<p class="kn-kicker">原本{esc(book["page"])}頁・§{m["section"]}</p><h3>{esc(kind)} {esc(book["number"])}</h3><p class="kn-comparison-type">{esc(m["comparison_type"])}</p>
<p class="kn-reference">{ref_link(records[m["record_id"]])}</p><div class="kn-passage-pair"><div><h4>本書の主張の要約</h4>{('<p class="kn-location">本書に記された帰属：' + esc(book["author_attribution"]) + '</p>') if book.get("author_attribution") else ''}{prose(book["summary"])}</div>
<div><h4>原文献の対応箇所</h4><p class="kn-location">{esc(paper["locator"])}・原文献{esc(paper["page"])}頁</p>{prose(paper["statement"])}</div></div>
<h4>比較の付記</h4>{prose(m["comparison"])}<details><summary>確認範囲・留保・所在の付記を読む</summary>{details}</details></article>''')
    conventions = "".join(f'<li>原本{x["page"]}頁：{esc(x["summary"])}</li>' for x in data["book_conventions"])
    return f'<section><h2>原本の頁・番号から文献へ</h2><p>「本書の主張の要約」は，文献を探すために趣旨と主要な条件を短く説明したものである．詳しい仮定と定式化は原著の該当頁を参照できる．351件には，定義・問題文の照合や限定された主張の対応も含む．「照合した範囲」と「留保」で各項目の射程を確認できる．独立した証明監査や，著者の実際の使用文献の確定を表すものではない．</p><p class="kn-note">本書の頁・番号は1974年原本の印刷頁・原本番号を使う．原文献の頁は当該文献の頁である．</p><details class="kn-conventions"><summary>比較するときに使う本書の空間の規約の要約</summary><ul>{conventions}</ul></details>' + filter_controls(data) + '<div class="kn-list">' + "".join(cards) + '</div></section>'


def afterword_page(data) -> str:
    records = {r["id"]: r for r in data["records"]}
    cards = []
    for a in data["afterword"]:
        refs = []
        for c in a["citations"]:
            r = records[c["record_id"]]
            locator = c.get("bib_id", c["record_id"])
            if c.get("bib_id"):
                variant = next(v for v in r["bib_variants"] if v["id"] == c["bib_id"])
                r = r | variant | {"id": r["id"]}
                if r.get("volume"):
                    r = r | {"title": r["title"] + f'，第{r["volume"]}巻'}
            refs.append('<li>' + ref_link(r) + f'<p class="kn-key">識別子：<code>{esc(locator)}</code></p>' + prose(c["identification"]) + prose(c.get("note", "")) + '</li>')
        names = "".join(prose("：".join(str(x[k]) for k in ("printed_name", "context", "status") if x.get(k))) for x in a.get("name_only_mentions", []))
        notes = prose(a.get("notes", [])) + source_list(a.get("note_sources", []))
        cards.append(f'<article class="kn-card" id="afterword-{a["number"]}"><p class="kn-kicker">あとがき{a["number"]}・原本{a["page"]}頁</p><h3>{esc(a["topic"])}</h3><ul class="kn-afterword-refs">{"".join(refs)}</ul>{notes}' + (f'<details><summary>人名のみの言及を読む</summary>{names}</details>' if names else '') + '</article>')
    return '<section><h2>あとがきの指定から読む</h2><p>原本411–412頁の全10項目から，書名や誌名・巻・年が指定された20文献へ対応付けた．以下の主題は内容の要約である．人名だけの言及は，特定の刊行論文を指定した記述と区別している．</p><div class="kn-note"><p>RudinのBulletin版とFundamenta版，Engelkingの1968年 <cite>Outline</cite> と1977年 <cite>General Topology</cite>，Kuratowskiの第I巻と第II巻は，別の書誌として参照できる．1974年当時の研究状況に関する記述を，現在の状況として読み替えない．</p></div><div class="kn-list">' + "".join(cards) + '</div></section>'


def notes_page(data) -> str:
    records = {r["id"]: r for r in data["records"]}
    cards = []
    for n in data["inferred"]:
        refs = '<ul>' + "".join('<li>' + ref_link(records[x]) + '</li>' for x in n["selected_record_ids"]) + '</ul>'
        supporting = '<ul>' + "".join('<li>' + ref_link(records[x]) + '</li>' for x in n["supporting_record_ids"]) + '</ul>'
        cards.append(f'<article class="kn-card" id="note-{esc(n["id"])}"><p class="kn-kicker">原本{esc(n["book_page"])}頁</p><h3>{esc(n["book_number"])}</h3><span class="kn-badge kn-inferred">{esc(n["adoption"])}</span><h4>案内に採用する文献</h4>{refs}<h4>採用の根拠</h4>{prose(n["basis"])}<div class="kn-note"><h4>留保・適用範囲</h4>{prose(n["limitations"])}</div>' + (f'<h4>裏付け・引用経路の資料</h4>{supporting}' if n["supporting_record_ids"] else '') + '</article>')
    return '<section><h2>推定した理由と，残る条件を読む</h2><p>直接の確定に条件が残る18項目とFrolíkの刊年問題について，参考文献を採用した理由と留保を記した．原典を入手できた範囲，間接的な引用経路，関連文献としての併記を各項目で区別している．この採用によって，直接照合の確認範囲を格上げしていない．</p><div class="kn-note"><p>Ishiiの演習10.Jは単一の収録先が未同定であり，主張を裏付ける関連文献を併記する．Worrellは後続引用による題名を未刊行原稿として採用し，刊年・誌名・巻頁を補わない．Frolíkの積論文は1960年を暫用し，書評の1961年との相違を残す．</p></div><div class="kn-list">' + "".join(cards) + '</div></section>'


def generate_kodama_nagami(catalog, output: Path) -> None:
    data = read_data()
    target = output / "kodama-nagami"
    target.mkdir(parents=True, exist_ok=True)
    manual_list_path = f"papers/{MANUAL_LIST_SLUG}/"
    manual_list_url = f"{SITE_URL}/{manual_list_path}"
    if catalog is not None and any(paper.slug == MANUAL_LIST_SLUG for _, paper in catalog.selected):
        manual_list_url = f"../{manual_list_path}"
    renderers = {"": lambda data: intro(data, manual_list_url), "references": references_page, "correspondence": correspondence_page,
                 "afterword": afterword_page, "notes": notes_page}
    for slug, label in PAGES:
        nested = bool(slug)
        asset_prefix = "../" if nested else ""
        nav = '<nav class="kn-navigation" aria-label="児玉・永見の文献案内">' + "".join(
            f'<a href="{asset_prefix + path + "/" if path else asset_prefix or "./"}"' + (' aria-current="page"' if path == slug else '') + f'>{text}</a>' for path, text in PAGES) + '</nav>'
        shortcut = ''
        if slug in ("references", "correspondence"):
            search_label = "文献を検索する" if slug == "references" else "本文との対応を検索する"
            shortcut = f'<p class="kn-search-shortcut" data-kn-search-shortcut hidden><a href="#kn-search">{search_label} ↓</a></p>'
        body = shortcut + nav + renderers[slug](data)
        path = target / slug
        path.mkdir(exist_ok=True)
        (path / "index.html").write_text(rendered_exploration_page(
            title="児玉・永見『位相空間論』の参考文献" + (f" — {label}" if slug else ""),
            eyebrow="KODAMA & NAGAMI · BIBLIOGRAPHY",
            description="本書の学習・照合に役立つ，根拠と留保を付けた参考文献案内．書誌・本文との対応・あとがきの指定をたどれる．",
            canonical_path="/kodama-nagami/" + (slug + "/" if slug else ""),
            body=body, prefix="../../" if nested else "../", body_class="kn-page", current_navigation="",
            extra_head=f'  <link rel="stylesheet" href="{asset_prefix}bibliography.css">\n  <script src="{asset_prefix}bibliography.js" defer></script>\n',
        ), encoding="utf-8")
    for name in ("bibliography.json", "kodama-nagami.bib"):
        shutil.copy2(DATA_ROOT / name, target / name)
    for name, ext in (("bibliography.css", ".css"), ("bibliography.js", ".js")):
        shutil.copy2(Path(__file__).with_suffix(ext), target / name)
