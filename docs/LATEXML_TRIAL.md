# LaTeXML HTML変換試験

LaTeXMLはTeX/LaTeXをXML、HTML、MathMLへ変換する公開リポジトリである。このサイトでは
通常デプロイへ直接入れず、代表原稿を別フォルダに変換して人が比較する段階に限定する。

- 公式リポジトリ: https://github.com/brucemiller/LaTeXML
- Homebrew: LaTeXML 0.8.8、public domain表記
- 使用形式: HTML5 + Presentation MathML

LaTeXMLが直接対応していない文書クラスは、原稿を変更せず
`experiments/latexml-bindings/` の外置きbindingでHTML向けの文書構造へ対応させる。
最初の対象は `ltjsarticle` で、ページ組版ではなくLaTeXMLの `article` 構造を利用する。

## 導入

```sh
brew install latexml poppler
latexmlc --VERSION
pdftoppm -v
```

Popplerの `pdftoppm` は、原稿がPDFの特定ページを図として読み込む場合だけ使う。

## 代表4分類を変換する

リポジトリのルートで実行する。

```sh
python3 scripts/paper_tool.py latexml-trial
```

対象は `experiments/latexml-trial.json` に記録している。

- 単純なTeX
- 図や参照を含むTeX
- 複雑なTeX
- BibTeXを使う原稿

結果は `_experiments/latexml/` に生成され、Gitには追加されない。各原稿の `index.html`、
`latexml.log` と、全体の `report.json` を確認する。出力先が既に空でない場合は上書きせず停止する。
再試験では別名を指定する。

変換には `--nocomments` を常に指定し、TeXコメントを派生HTMLへ残さない。`report.json` には
変換元SHA-256、使用したbinding、題名保持、警告・エラー、`ltx_ERROR`、簡易個人情報検査、
自動検査を通らなかった理由を記録する。PDF図版は元TeXを書き換えず、指定ページだけを
144 dpiのPNGへ変換する。変換したページ、出力名、表示幅も `report.json` に記録し、
未変換の図が一枚でも残れば自動検査を不合格にする。

原稿内の `\date` や `\today` が出力した日付は、変換後に
`HTML変換日：YYYY年M月D日` へ置き換える。この日付はサイトのデプロイ日ではなく、実際に
LaTeXML変換を実行した日であり、同じ日付と時刻を `report.json` にも記録する。

```sh
python3 scripts/paper_tool.py latexml-trial --output _experiments/latexml-2
```

特定原稿だけなら原稿番号を指定できる。

```sh
python3 scripts/paper_tool.py latexml-trial 2015-08-28-01 \
  --output _experiments/latexml-primes
```

## 人が確認する項目

1. 題名、著者名などに公開したくない情報がないか。
2. HTML変換日が実際の変換日と一致しているか。
3. 日本語が欠落・文字化けしていないか。
4. 数式、定理環境、番号、相互参照が対応しているか。
5. 図版、TikZ、BibTeX、独自BSTが欠落していないか。
6. 元PDFと意味が変わっていないか。

`report.json` の `publishable` は常に `false`、`manual_review_required` は常に `true` である。
変換の成功だけでは公開承認にならない。公開には次節の目視確認と、独立した公開コマンドが必要になる。

`automatic_checks_passed` が `true` になる条件は、LaTeXMLの警告・エラーがなく、生成HTMLに
`ltx_ERROR` と未変換図版がなく、題名が保持され、簡易個人情報検査にも確認事項がないことである。
TikZなどから生成したインラインSVGについては、`script`、イベント属性、外部資源参照がないことも
検査する。`report.json` の `inline_svg_count` で生成数を確認できる。
この条件を満たしても、数式、定理番号、相互参照、内容を元PDFと目視比較するまで公開してはならない。

## 単純なTeXの限定パイロット

最初は「素数の無限性」だけを別出力へ変換する。

```sh
python3 scripts/paper_tool.py latexml-trial 2015-08-28-01 \
  --output _experiments/latexml-primes-pilot
```

HTML版はPDF・TeXを置き換える正本ではなく、全確認を終えた原稿だけに追加できる派生版として扱う。

## 確認済みHTMLを公開する

上の確認項目をすべて目視し、公開してよいと判断した場合だけ、試験出力を指定して実行する。

```sh
python3 scripts/paper_tool.py publish-latexml 2015-08-28-01 \
  --trial _experiments/latexml-primes-pilot \
  --reviewed
```

この処理は次の条件を再検査してから `papers/原稿番号/html/` に公開版を追加する。

- 試験時から変換元TeXのSHA-256が変わっていない。
- LaTeXMLの自動検査に合格し、個人情報候補が残っていない。
- `script`、`iframe`、フォームなどの動的要素を含まない。
- 公開対象がHTML、CSS、画像だけであり、変換ログを含まない。

公開HTMLにはサイト共通の案内と見た目を加え、記事ページ、PDF、TeX、トップページへの
導線を付ける。記事ページには「HTML版を読む（試験）」が表示され、サイトマップにもHTML版を
追加する。PDFとTeXが引き続き正本であり、HTMLは検索・閲覧を補助する派生版である。

元TeXを後で変更すると、登録された変換元SHAと一致しなくなるため通常検査が停止する。
その場合は古いHTML版をそのまま承認し直さず、最新版から新しい試験出力を作り、PDFとの
目視比較を再度行ってから更新する。

## 2026-07-26の初回結果

4件ともHTMLファイル自体は生成されたが、完全成功とは扱えない結果もあった。

- 単純なTeX: `ltjsarticle` の専用bindingがなく、警告付きで生成。
- 図や参照を含むTeX: PDF図版を画像化するモジュールがなく、図を欠いた部分生成。
- 複雑なTeX: `jsarticle`、`pxjahyper`、独自マクロの処理で多数のエラーがあり、部分生成。
- BibTeXを使う原稿: 独自文献処理を再現できず、引用・文献警告付きで生成。

したがって一括自動公開へは進めない。日本語クラス用binding、画像変換依存、BibTeXの
読み込み方法をそれぞれ調査し、原稿ごとに元PDFとの目視比較を続ける。自動検査と目視確認を
ともに通過した原稿だけを、上記の限定公開手順で個別に追加する。

## 図・相互参照原稿の改善結果

「二次元以上の球面の基本群」では、次の二点を変換処理側で解決した。

- `jsarticle` をHTMLの `article` 構造へ対応させる外置きbindingを追加した。
- `Figures.pdf` の `page` 指定を読み、必要な6ページだけをPopplerでPNG化した。

元TeXと元PDFは変更していない。2026-07-26の再試験ではLaTeXMLの警告・エラー、
欠落図版、`ltx_ERROR`、簡易個人情報候補がすべて0となり、定理への相互参照もHTML内リンクとして
保持された。試験結果は `_experiments/latexml-sphere-graphics-2/2024-01-08-01/index.html` で
目視確認できる。公開承認はこのHTMLと元PDFを人が比較した後に行う。

## 複雑なTeX原稿の改善結果

「Urysohn universal spaces」では、公開原稿を変更せず、変換時だけ使う一時コピーに対して
次の互換処理を行うようにした。

- `pxjahyper` をHTML変換では何もしない外置きbindingとして扱う。
- `\textgt` をHTML上の太字へ変換する。
- `\text{...}` の中にある数式をLaTeXMLが解釈できる形へ一時的に正規化する。
- `align` の複数行にまたがる集合の波括弧を表示用文字として一時的に正規化する。
- HTML本文中の一般語としての「著者」を個人情報ラベルと誤判定しないようにする。

一時コピーは変換終了時に削除し、正規化の種類と件数だけを `report.json` に記録する。
2026-07-26の再試験では警告、エラー、未解釈数式、欠落要素、簡易個人情報候補がすべて0となった。
目次、394件の内部参照、3点のXy-pic図、58件の文献も生成された。試験結果は
`_experiments/latexml-urysohn-clean/2018-10-14-01/index.html` で確認できる。
公開承認はこのHTMLと元PDFを人が比較した後に行う。

## BibTeX原稿の改善結果

「CW複体のパラコンパクト性」では、公開対象として登録された `.bib` だけをLaTeXMLへ
明示的に渡すようにした。手書きの `thebibliography` とBibTeXを併用する原稿では、手書き文献の
キーが外部 `.bib` にないという警告が出る。この警告は生成HTML内の全引用が解決済みの場合だけ
記録付きで無害と判定し、引用欠落が一つでもあれば従来どおり公開を停止する。

LaTeXMLが `\nocite{*}` から未引用文献を1件省略したため、変換時の一時コピーでは公開BibTeXの
全キーを明示的な `\nocite{...}` へ展開する。また、商空間の記法 `/\sim` には一時的に
数式原子の型を補い、未解釈数式を防ぐ。いずれも元TeX、BibTeX、BSTは変更しない。

2026-07-26の再試験では28箇所の引用がすべて内部リンクとなり、手書き7件とBibTeX 15件の
計22件の文献を生成した。警告、エラー、未解釈数式、引用欠落、簡易個人情報候補はすべて0である。
独自BSTの外観は再現せず、LaTeXMLの意味的な標準書式を使う。試験結果は
`_experiments/latexml-cw-complete/2024-01-13-01/index.html` で確認できる。
公開承認はこのHTMLと元PDFを人が比較した後に行う。

## TikZ可換図式の試験結果

本名や既存原稿を含まない人工素材
`experiments/latexml-fixtures/tikz-commutative-diagram.tex` を使い、4対象と4射からなる
可換四角形を試験した。通常のLaTeXML試験は `--svg` を常に指定し、TikZ図をインラインSVGへ
変換する。2026-07-26の試験では警告・エラーなしで、頂点 `A, B, C, D`、射のラベル
`f, g, h, k`、4本の矢印と矢印先端が保持された。

生成HTMLにはSVG数と安全性検査結果を記録する。SVG内の `script`、`onload` などのイベント属性、
HTTP・data URL・JavaScriptによる外部資源参照を検出した場合は、自動検査と正式公開の両方を停止する。
SVGが生成できても、複雑なTikZライブラリ、色、線種、配置は元PDFとの目視比較を必須とする。
