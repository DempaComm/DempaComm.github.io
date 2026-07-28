# ローカル生成物の整理

原稿、公開PDF、現在の `_site/` を残したまま、再生成できるローカルファイルを整理できる。
最初は削除せず、対象件数と容量だけを表示する。

```sh
python3 scripts/paper_tool.py clean-local
```

表示内容を確認してから削除する。

```sh
python3 scripts/paper_tool.py clean-local --apply
```

対象は番号付きの `_site 2/` など、TeX中間物、`.DS_Store`、`tmp/`、および
`paper.json` に `reviewed` または理由付きの `overridden` と記録済みのSHAに対応する
`.privacy-review/` である。
未承認のプライバシー検査結果、原稿、PDF、現在の `_site/` は削除しない。

過去のLaTeXML試験出力も削除する場合だけ、次を使う。

```sh
python3 scripts/paper_tool.py clean-local --include-experiments --apply
```

`_experiments/` は再生成可能だが、未公開の試験結果を目視確認している途中なら削除しない。
