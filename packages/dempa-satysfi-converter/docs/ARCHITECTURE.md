# 構成

```text
LaTeX原稿（読み取り専用）
  ↓ 一時領域へコピーしてPandocを実行
pandoc-ast.json
  ↓ ASTと数式命令を許可リストで検査
main.saty + dempa.satyh + conversion-report.json
  ↓ 任意の --compile
main.pdf + satysfi.log
```

`cli.py` は隔離、Pandoc・SATySFi実行、成果物と報告の保存を担当する。`converter.py` はPandoc
ASTの構造検査とSATySFiコード生成、`math.py` は数式命令の限定変換を担当する。見た目と相互参照
登録はパッケージデータの `styles/dempa.satyh` に閉じ込める。

変換は全体成功か全体失敗のどちらかである。未対応ノード、未対応数式命令、重複ラベル、未解決参照を
検出した場合は報告を残すが `main.saty` を出力しない。コンパイラ警告も変換報告へ記録する。

変換器は生成と検査までを担当し、数識電収への登録、公開承認、Git操作を行わない。サイト本体の
公開成否もこの変換器に依存させない。
