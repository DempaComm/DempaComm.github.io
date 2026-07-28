# Typst変換比較試験

TeX原稿を変更せず、TylaxとPandocでTypstへ変換し、TypstコンパイラでPDFを生成して比較する。
これは公開処理ではなく、結果はGit管理外の `_experiments/` にだけ置く。

## 使用ツール

- Typst 0.15.1以降: Typstソースのコンパイル
- Tylax 0.3.7以降: 原稿全体を対象にする第一候補
- Pandoc 3以降: 比較基準

macOSでは次の順に導入する。

```sh
brew install typst pandoc rust
cargo install tylax
```

導入後にバージョンを確認する。

```sh
typst --version
t2l --version
pandoc --version
```

## 代表4分類を変換する

リポジトリのルートで実行する。

```sh
python3 scripts/paper_tool.py typst-trial
```

対象は `experiments/typst-trial.json` に記録している。

- 単純なTeX
- 図や参照を含むTeX
- 複雑なTeX
- BibTeXを使う原稿

原稿ごとに次のファイルを `_experiments/typst/記事番号/` へ生成する。

- `tylax.typ`、`tylax.pdf`、変換・コンパイルログ
- `pandoc.typ`、`pandoc.pdf`、変換・コンパイルログ

全体結果は `_experiments/typst/report.json` に記録する。出力先が空でなければ上書きせず停止する。
再試験では別の出力先を指定する。

```sh
python3 scripts/paper_tool.py typst-trial \
  --output _experiments/typst-2
```

特定原稿だけを試すこともできる。

```sh
python3 scripts/paper_tool.py typst-trial 2015-08-28-01 \
  --output _experiments/typst-primes
```

## 安全条件

変換時は原稿フォルダを一時領域へコピーし、Tylax、Pandoc、Typstはコピーだけを読み書きする。
元TeX、PDF、BibTeX、BST、図版、`paper.json` は変更しない。試験出力は自動公開されず、
`report.json` の `publishable` は常に `false`、`manual_review_required` は常に `true` である。

## 人が比較する項目

1. 日本語が欠落または文字化けしていないか。
2. 数式、定理環境、番号、相互参照が元PDFと一致するか。
3. 図版、TikZ、引用、参考文献が欠落していないか。
4. 変換された `.typ` が人間に編集できる構造か。
5. 元PDFと意味およびページ内容が変わっていないか。

変換・コンパイルに成功しても公開承認にはならない。公開機能は、4分類の差異を確認して
派生ファイルの保護・履歴・再生成規則を別途設計した後に検討する。

## 2026-07-28の初回結果

Typst 0.15.1、Tylax 0.3.7、Pandoc 3.10.1で代表4分類を変換した。Pandocは4件すべて、
Tylaxは3件で日本語を含む `.typ` を生成した。「図や参照を含むTeX」のTylax変換は
180秒で停止した。生成された7件の `.typ` は、いずれも未補正ではPDFコンパイルに至らなかった。

- 単純なTeX:
  - Tylaxは短く比較的読みやすい出力を生成したが、`\text` 内に残ったLaTeX数式を
    Typstの変数として解釈して停止した。
  - Pandocは文書構造を保持したが、命題への参照先を参照可能な要素として生成できず停止した。
- 図や参照を含むTeX:
  - Tylaxは変換が制限時間を超えた。
  - Pandocは本文を生成したが、引用・定理参照のラベルが解決されず停止した。
- 複雑なTeX:
  - TylaxはLaTeXの寸法命令、独自見出し、区切り記号などをTypstへ未変換のまま残した。
  - Pandocは本文を広く保持したが、数式中で連結した文字列を未定義変数として解釈した。
- BibTeXを使う原稿:
  - Tylaxは列挙ラベルと独自構造のLaTeX命令を残した。
  - Pandocは引用キーと直後の日本語を一つの参照名として解釈し、参照を解決できなかった。

初回結果から、どちらも現状のまま公開用一括変換器にはできない。ただし、変換器ごとの生出力と
ログを同じ形式で比較する基盤は完成した。次は単純なTeXを対象に、元TeXを変更せず、
変換後だけに適用する明示的な補正规則の範囲を決める。参照や数式の意味を推測する補正は
自動化せず、失敗として残す。
