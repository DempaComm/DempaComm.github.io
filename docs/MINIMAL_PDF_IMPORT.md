# PDFファイル1本から公開する非常用手順

この文書は、Codexに限らず、一般的なLLMやAIへそのまま渡して作業を依頼できる最低限の手順書です。

## AIへの最重要指示

- 渡されたPDFの内容を編集、再圧縮、再変換してはいけない。
- PDFはバイト単位で同一のままコピーする。
- 題名などを直す必要がある場合は、PDFではなく生成された `paper.json` を編集する。
- PDFからTeXを推測したり、新しいTeX原稿を作ったりしない。
- 既存原稿の `.tex`、`.bib`、`.bst`、図版、PDFを変更してはいけない。

## 最短の取り込み

最初に個人情報検査を実行する。

```sh
python3 scripts/paper_tool.py inspect-file /path/to/manuscript.pdf
```

`.privacy-review/.../` に検査報告、抽出文字、全ページのPNG画像が作られる。`report.txt` を読み、すべてのページ画像を実際に開いて、著者名、本名、メール、所属、住所、PDFメタデータを確認する。文字抽出は日本語や数式を正しく読めない場合があるため、画像確認を省略してはいけない。

フォント欠落や文字描画失敗が報告されたPDFは、画像から個人情報が消えて見える危険があるため検査不合格になる。別の正常に表示できる環境で確認するか、公開対象から外す。警告を無視して `report.json` を手作業で作ってはいけない。

別の正常なPDF閲覧環境などで全ページを確認し、それでも公開すると判断した場合は理由を記録して強制取り込みできる。

```sh
python3 scripts/paper_tool.py import-pdf /path/to/manuscript.pdf \
  --privacy-override "別環境で全ページと著者欄を確認済み"
```

`inspect-file` を一度も実行していないファイルには使えない。理由は `paper.json` に公開判断の監査記録として残る。

確認が終わった場合だけ、リポジトリの最上位ディレクトリで次を実行する。

```sh
python3 scripts/paper_tool.py import-pdf /path/to/manuscript.pdf --privacy-reviewed
```

この操作は次を自動的に行う。

1. PDFのファイル名を暫定題名にする。
2. 実行日と、その日の未使用の連番から `YYYY-MM-DD-NN` を決める。
3. PDFを内容無変更で `papers/YYYY-MM-DD-NN/published.pdf` へコピーする。
4. 最低限の `paper.json` と `keywords.txt` を作る。
5. 数学記事総覧の「その他」と、数学タグ、公開年、検索一覧へ追加する。
6. 公開ページでは保存したPDFを `main.pdf` として読めるようにする。

題名、公開日時、同日内番号、元記事URLが分かっている場合は指定できる。

```sh
python3 scripts/paper_tool.py import-pdf /path/to/manuscript.pdf \
  --title "原稿の題名" \
  --published-at "2026-07-16T12:00:00+09:00" \
  --sequence 1 \
  --original-url "https://example.com/original" \
  --privacy-reviewed
```

PDFの内部メタデータは不正確なことがあるため、非常用取り込みでは題名の自動採用に使わない。同じ保存先がすでにある場合は上書きせず停止する。

## 必ず行う確認

```sh
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py catalog --check
```

両方が成功したら、渡されたPDFと `published.pdf` のSHA-256が同一であること、既存の原稿ファイルに差分がないことを確認する。

```sh
shasum -a 256 /path/to/manuscript.pdf papers/YYYY-MM-DD-NN/published.pdf
git status --short -- '*.tex' '*.bib' '*.bst' '*.pdf'
```

新しく追加した `published.pdf` が未追跡ファイルとして表示されることは正常である。既存の原稿ファイルに本文変更があれば作業を止める。

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

公開日や連番を変更するとフォルダ名も変える必要があるため、自信がない場合は取り込み時の値を維持する。編集後は `python3 scripts/paper_tool.py catalog` を実行し、再度 `verify` と `catalog --check` を行う。PDF自体は編集しない。

## 公開

確認後、通常のGit運用で変更をコミットして `main` ブランチへプッシュする。GitHub Pagesの処理が成功すれば公開される。AIには、プッシュ前に変更ファイル一覧、PDFのハッシュ一致、既存原稿の無変更確認を報告させる。
