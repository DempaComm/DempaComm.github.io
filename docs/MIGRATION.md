# 原稿無改変の移行手順

## 基本方針

- 通常の移行では、TeX原稿、図版、BibTeXデータ、BSTなどをバイト単位でコピーする。
- 各ファイルの原本SHA-256と現在承認済みSHA-256を `paper.json` に分けて保存する。
- 明示的な書き換え指示がない限り、保護対象ファイルを編集しない。
- 指示によって書き換えた場合は、理由と変更前後のSHA-256を承認履歴に残す。
- 題名、分類、説明、元記事URLなど、サイト表示用の情報は `paper.json` に置く。
- 原稿名は公開日と同日内の公開順から `YYYY-MM-DD-NN` とする。
- 電波通信の既存タグは原表記のまま `tags` に保存し、追加検索語は `keywords` に分ける。
- `keywords.txt` は `paper.json` から自動生成し、手作業では編集しない。

## 新しい原稿の取り込み

まず、リポジトリ外に取り込み仕様JSONを作る。仕様例は `examples/paper-import.example.json` にある。

```sh
python3 scripts/paper_tool.py import-paper /path/to/import-spec.json
```

この操作は次を行う。

1. 公開日時と同日内の順番から保存先 `papers/YYYY-MM-DD-NN/` を決める。
2. 指定ファイルをその保存先へコピーする。
3. コピー元とコピー先のSHA-256が一致することを確認する。
4. 原本SHA-256と現在承認済みSHA-256が同一の `paper.json` を作る。
5. 標準の `.latexmkrc` がなければ生成する。
6. `paper.json` から `keywords.txt` と `index.html` の原稿一覧を再生成する。

既存PDFを原稿と一緒に保存するだけの試験公開では、取り込み仕様の `build_enabled` を `false` にし、完成PDFを `published.pdf` として保護対象へ含める。この場合は原稿を自動コンパイルせず、保存されたPDFを公開時に `main.pdf` として配置する。

既存の保存先がある場合は上書きせず停止する。

## 検証と監査

現在のファイルが承認済みハッシュと一致するか確認する。

```sh
python3 scripts/paper_tool.py verify
```

原本のままか、指示による変更が承認済みかを表示する。

```sh
python3 scripts/paper_tool.py audit
```

`original` は原本と同一、`approved-modified` は明示的な変更が記録済みであることを表す。ハッシュが承認値と一致しないファイルは、どちらの操作でもエラーになる。

## 明示的に指示された書き換え

原稿を指示どおり編集した後、変更理由と対象ファイルを明示して承認記録を作る。

```sh
python3 scripts/paper_tool.py approve-change SLUG \
  --reason "依頼された誤植修正" \
  --file main.tex
```

この操作は原稿を書き換えない。変更後ハッシュを承認値として記録し、原本ハッシュは保持する。

## 記事一覧と公開物

`paper.json` から記事カードと各原稿の `keywords.txt` を再生成する。

```sh
python3 scripts/paper_tool.py catalog
```

一覧が最新かだけを確認する。

```sh
python3 scripts/paper_tool.py catalog --check
```

GitHub Actionsでは、公開前に `verify` と `catalog --check` を実行する。PDF生成後は次の操作で公開用ディレクトリを作る。

```sh
python3 scripts/paper_tool.py stage _site
```

記事カードには電波通信のタグを表示する。検索欄では、題名、説明、タグ、検索キーワードを横断検索でき、元タグと公開年による絞り込みもできる。トップページには件数付きのタグ索引と公開年別記事一覧を置き、タグごとの記事一覧は `tags/<タグ名>/` に公開年別で自動生成する。

旧形式の原稿名が `legacy_slugs` に登録されている場合、公開時には旧URLにも同じファイルを配置する。改名後も既存リンクは維持される。

したがって、新しい `paper.json` を追加すれば、検索情報、記事一覧、PDF生成対象、Pagesへの配置へ自動的に反映される。
