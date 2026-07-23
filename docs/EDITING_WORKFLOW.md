# 原稿修正の簡単手順

この手順は、既存原稿を原稿フォルダ内でコンパイルしながら修正し、個人情報検査、
SHA承認、公開サイト生成、公開物基準更新まで安全に完了するためのものである。

## 最初に三項目だけ書き換える

リポジトリのルートで、次の三行を実際の記事番号、ファイル名、修正理由へ書き換えて
実行する。以後のコマンドはそのままコピーできる。

```sh
SLUG="2015-08-28-01"
FILE="main.tex"
REASON="LuaLaTeX対応と原稿修正"
```

値を確認する。

```sh
echo "記事: $SLUG"
echo "ファイル: $FILE"
echo "理由: $REASON"
```

ターミナルを閉じた場合は、上の三行をもう一度実行する。

## 1. 編集とコンパイル

```sh
cd "papers/$SLUG"
latexmk "$FILE"
```

VS Codeで修正し、保存するたびに `latexmk "$FILE"` を実行してPDFを確認する。
`.latexmkrc` が原稿ごとのTeXエンジンを選ぶ。作業完了後にルートへ戻る。

```sh
cd ../..
```

## 2. 修正ファイルを検査する

```sh
python3 scripts/paper_tool.py review-change "$SLUG" --file "$FILE"
```

表示された `PRIVACY REVIEW FILES` の報告を開き、実名、メール、所属、住所などを
人間が確認する。PDFの場合は全ページ画像も確認する。報告を見ずに次へ進まない。

## 3. 承認・公開物更新・全検査をまとめて行う

報告とローカルPDFを確認した後だけ実行する。

```sh
python3 scripts/paper_tool.py finish-change "$SLUG" \
  --reason "$REASON" \
  --file "$FILE" \
  --privacy-reviewed \
  --accept-public-change
```

この一つのコマンドが次を行う。

1. 変更前後のSHA-256と理由を `paper.json` へ記録する。
2. 個人情報検査記録を現在のSHAへ更新する。
3. 自動テスト、SHA、監査、カタログ、台帳を検査する。
4. 公開サイトを生成し、リンクを検査する。
5. 指定記事と旧URLだけが変わったことを確認する。
6. 無関係な公開差分がなければ公開物基準を更新する。
7. 更新後の公開物基準が一致することを再確認する。

指定記事以外の公開差分、ファイル追加、ファイル削除がある場合は、公開物基準を
書き換えず停止する。

## 4. コミットしてpushする

```sh
git status
git diff -- "papers/$SLUG"
git diff -- tests/fixtures/site-baseline.json
```

意図した変更だけなら、既存の追跡対象を登録する。

```sh
git add -u "papers/$SLUG"
git add tests/fixtures/site-baseline.json
git status
git commit -m "$REASON"
git push origin main
```

新しいファイルを追加した場合は `git add -u` では登録されない。新規ファイルの追加は
`paper.json` への新しいSHA登録も必要なので、この簡単手順では扱わず、先に個別対応する。
生成した `main.pdf`、`_site/`、個人情報検査報告はGitへ追加しない。

## 複数ファイルを同時に修正した場合

`--file` を繰り返す。

```sh
python3 scripts/paper_tool.py review-change "$SLUG" \
  --file main.tex \
  --file references.bib

python3 scripts/paper_tool.py finish-change "$SLUG" \
  --reason "$REASON" \
  --file main.tex \
  --file references.bib \
  --privacy-reviewed \
  --accept-public-change
```

公開TeX・PDFはすべて個人情報報告を確認する。BibTeX、BST、図版などには現在の自動
個人情報検査はないが、内容と公開可否を人間が確認する。

## VS Codeの入力画面を使う

コマンドを入力したくない場合は、VS Codeで「ターミナル」→「タスクの実行」を開く。

1. 「数識電収: 原稿修正を検査」を選ぶ。
2. 記事番号とファイル名を入力する。
3. 表示された個人情報報告を確認する。
4. 「数識電収: 原稿修正を承認して全確認」を選ぶ。
5. 同じ記事番号、ファイル名、修正理由を入力する。

最後のコミットとpushだけは、差分を確認してから手動で行う。

## 途中で再修正した場合

`review-change` の後で原稿を再修正すると検査時のSHAが古くなる。もう一度
`review-change` を実行し、新しい報告を確認してから `finish-change` を実行する。

`finish-change` の途中で検査に失敗した場合は、表示された項目だけを直す。TeX、PDF、
BibTeXなどの保護ファイルを再修正していなければ、同じ記事番号、理由、ファイルを指定して
`finish-change` を再実行すると直前の承認から再開する。保護ファイルを再修正した場合は、
再び `review-change` から始める。
