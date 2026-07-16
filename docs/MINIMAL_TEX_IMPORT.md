# TeXファイル1本から公開する非常用手順

PDFファイル1本だけの場合は `docs/MINIMAL_PDF_IMPORT.md` を使う。

この文書は、Codexに限らず、一般的なLLMやAIへそのまま渡して作業を依頼できる最低限の手順書です。

## AIへの最重要指示

- 渡されたTeX原稿の内容を編集してはいけない。
- TeX原稿はバイト単位で同一のままコピーする。
- 題名などを直す必要がある場合は、原稿ではなく生成された `paper.json` を編集する。
- コンパイルできなくても取り込みを中止しない。まずソースのみの記事として公開する。
- 既存原稿の `.tex`、`.bib`、`.bst`、図版、PDFを変更してはいけない。

## 最短の取り込み

リポジトリの最上位ディレクトリで次を実行する。

```sh
python3 scripts/paper_tool.py import-tex /path/to/manuscript.tex
```

この操作は次を自動的に行う。

1. `\title{...}` が単純に読み取れる場合は題名に使い、読めない場合はファイル名を題名にする。
2. 実行日と、その日の未使用の連番から `YYYY-MM-DD-NN` を決める。
3. 原稿を内容無変更で `papers/YYYY-MM-DD-NN/source.tex` へコピーする。
4. 最低限の `paper.json` と `keywords.txt` を作る。
5. 数学記事総覧の「その他」と、数学タグ、公開年、検索一覧へ追加する。
6. PDFを作れなくても、TeXソースを読める個別記事ページを作れる状態にする。

題名、公開日時、同日内番号、元記事URLが分かっている場合は指定できる。

```sh
python3 scripts/paper_tool.py import-tex /path/to/manuscript.tex \
  --title "原稿の題名" \
  --published-at "2026-07-16T12:00:00+09:00" \
  --sequence 1 \
  --original-url "https://example.com/original"
```

同じ保存先がすでにある場合は上書きせず停止する。

## 必ず行う確認

```sh
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py catalog --check
```

両方が成功したら、変更内容を確認する。特に、取り込んだ元のTeXファイルと `source.tex` のSHA-256が同一であること、既存の原稿ファイルに差分がないことを確認する。

```sh
shasum -a 256 /path/to/manuscript.tex papers/YYYY-MM-DD-NN/source.tex
git diff -- . ':!papers/YYYY-MM-DD-NN/source.tex'
```

最後のコマンドでは、`paper.json`、`keywords.txt`、生成された一覧ページ、手順書などの予定した差分は許容する。ただし、既存の原稿ファイルに本文変更があれば作業を止める。

## 後から情報を詳しくする

生成された `papers/YYYY-MM-DD-NN/paper.json` では、次の項目だけを必要に応じて整える。

- `title`: 表示題名
- `published_at`: 本来の公開日時
- `sequence`: 同日内の公開順
- `slug`: `公開日-sequence` と一致させる
- `year`: 公開年
- `order`: `YYYYMMDDNN` 形式の並び順
- `kind`: 原稿の種類
- `summary`: 説明
- `original_url`: 元記事URL。なければ空文字でよい
- `tags`: 電波通信の元タグ
- `keywords`: 追加検索語
- `math_section`: 数学記事総覧の分類。空欄なら「その他」になる

公開日や連番を変更するとフォルダ名も変える必要があるため、自信がない場合は取り込み時の値を維持する。編集後は `python3 scripts/paper_tool.py catalog` を実行し、再度 `verify` と `catalog --check` を行う。

## PDFも公開したくなった場合

非常用取り込みの初期状態は、公開失敗を避けるため `build.enabled` が `false` のソースのみ公開である。PDF生成は別作業として、使用エンジン、必要な画像・BibTeX・BST、コンパイル手順が確定してから設定する。原稿本文を書き換えてコンパイルを通してはいけない。

既存の完成PDFを使う場合は、内容無変更で `published.pdf` として同じフォルダへ置き、`paper.json` の `files` に保護対象として登録する。登録には正しいSHA-256が必要なので、通常取り込みの `examples/paper-import.example.json` と `docs/MIGRATION.md` を参照する。

## 公開

確認後、通常のGit運用で変更をコミットして `main` ブランチへプッシュする。GitHub Pagesの処理が成功すれば公開される。AIには、プッシュ前に変更ファイル一覧と原稿ファイルの無変更確認を報告させる。
