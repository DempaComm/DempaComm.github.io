# 変換手順

## 1. 作業領域を作る

元TeXとは別の空フォルダを用意する。元原稿を直接出力先にしない。

```sh
mkdir -p work
```

## 2. Tylaxの生出力を保存する

```sh
t2l input.tex -o work/tylax.raw.typ
```

`tylax.raw.typ` は比較の基準なので、人間も補正プログラムも上書きしない。

## 3. 安全な補正を実行する

```sh
dempa-typst-correct work/tylax.raw.typ \
  --output work/main.typ \
  --report work/correction-report.json
```

補正可能な場合は `main.typ` と報告を生成する。意味の判断を必要とする構造が残る場合は、
報告だけを書き、終了コード `2` で停止する。停止を無視して公開へ進んではならない。
入力・補正版・報告には別々のパスを指定する。補正版または報告が既に存在する場合も、
意図しない上書きを避けるため停止する。

報告には次を記録する。

- 生出力と補正版のSHA-256
- 適用した規則と置換回数
- 未対応構造と停止理由
- `manual_review_required: true`
- `publishable: false`

## 4. スタイルを読み込む

補正後の文書から `dempa-style.typ` を読み込む。定理環境の自動変換が未対応の間は、
`#definition`、`#proposition`、`#theorem`、`#proof` への変換を人間が確認する。

## 5. TypstでPDFを生成する

```sh
typst compile work/main.typ work/main.pdf
```

コンパイル成功は内容一致の証明ではない。

## 6. 人が比較する

元PDFと生成PDFの全ページについて、次を確認する。

1. 日本語、数式、記号が欠落していない。
2. 定義、命題、定理、証明の範囲と番号が一致する。
3. 相互参照、引用、参考文献が一致する。
4. 図版、表、TikZ由来の内容が欠落していない。
5. タイトル、著者、日付、メタデータが意図どおりである。

## 7. 公開判断を分離する

このパッケージは公開登録、Git commit、pushを行わない。公開先リポジトリ側の保護・個人情報・
差分承認手順を別途通す。
