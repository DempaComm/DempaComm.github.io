# 別スレッドへの引き継ぎ

## 目的

LaTeX原稿を変更せず、構造を保ったSATySFiソースとPDFを隔離生成する変換器を試作する。
このスレッドでは予約領域と要件だけを作成し、変換器本体には着手していない。

## ローカル環境

2026-08-01時点で確認済み。

```text
SATySFi: v0.0.11-22-gc2cbc48
SATySFi executable: /Users/yoshitoishiki/.opam/satysfi/bin/satysfi
opam: 2.5.2
Pandoc: 3.10.1
Pandoc executable: /opt/homebrew/bin/pandoc
```

## 最初の作業

1. `REQUIREMENTS.md` の安全条件をテストとして先に固定する。
2. 新規作成した最小LaTeXをPandoc JSON ASTへ変換し、情報保持を確認する。
3. SATySFiの最小文書と共通スタイルの責務を決める。
4. 言語、パッケージ形式、ライセンスを決定する。
5. 単純な見出し・本文・数式だけの最小変換器を作る。
6. 未対応ASTノードでは警告継続せず、安全停止する。

## 未決事項

- 実装言語をPython、OCaml、その他のどれにするか。
- Pandoc ASTを正式な中間表現にするか。
- SATySFiスタイルを `.satyh`、クラス、パッケージのどの形で配布するか。
- Apache-2.0、MIT等のライセンス選択。
- 引用、定理参照、TikZ代替をどこまで初期範囲に含めるか。

## 禁止事項

- `papers/*` を変更しない。
- 実原稿を公開テストへ追加しない。
- 未知の構造を黙って削除しない。
- 変換結果を自動公開しない。
- この予約領域を完成済みと記載しない。
