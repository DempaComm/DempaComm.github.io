# LaTeXML HTML変換試験

LaTeXMLはTeX/LaTeXをXML、HTML、MathMLへ変換する公開リポジトリである。このサイトでは
通常デプロイへ直接入れず、代表原稿を別フォルダに変換して人が比較する段階に限定する。

- 公式リポジトリ: https://github.com/brucemiller/LaTeXML
- Homebrew: LaTeXML 0.8.8、public domain表記
- 使用形式: HTML5 + Presentation MathML

## 導入

```sh
brew install latexml
latexmlc --VERSION
```

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
2. 日本語が欠落・文字化けしていないか。
3. 数式、定理環境、番号、相互参照が対応しているか。
4. 図版、TikZ、BibTeX、独自BSTが欠落していないか。
5. 元PDFと意味が変わっていないか。

`report.json` の `publishable` は常に `false`、`manual_review_required` は常に `true` である。
変換の成功だけでは公開承認にならない。正式公開機能は、この試験結果を見てから別途実装する。

## 2026-07-26の初回結果

4件ともHTMLファイル自体は生成されたが、完全成功とは扱えない結果もあった。

- 単純なTeX: `ltjsarticle` の専用bindingがなく、警告付きで生成。
- 図や参照を含むTeX: PDF図版を画像化するモジュールがなく、図を欠いた部分生成。
- 複雑なTeX: `jsarticle`、`pxjahyper`、独自マクロの処理で多数のエラーがあり、部分生成。
- BibTeXを使う原稿: 独自文献処理を再現できず、引用・文献警告付きで生成。

したがって現時点では自動公開へ進めない。日本語クラス用binding、画像変換依存、BibTeXの
読み込み方法をそれぞれ調査し、元PDFとの目視比較を続ける。
