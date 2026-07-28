# Pagefind本文全文検索

## 対象

既存の全原稿アーカイブは、全191記事の題名、説明、タグ、キーワード、公開年を検索する。
Pagefindはこれを置き換えず、主LaTeXML HTML版がある記事だけを本文、節見出し、定理名、
参考文献から検索する。元版などの別HTMLは重複結果を避けるため索引しない。

索引はPagefind 1.5.2 extendedで日本語用に生成し、検索処理は公開ブラウザ内だけで行う。
外部の検索サーバーへ原稿や検索語を送らない。

## 最初の一度だけ行う準備

リポジトリのルートで次を実行する。

```sh
python3 -m pip install --user -r requirements-pagefind.txt
```

VS Codeでは「ターミナル」→「タスクの実行」→
「数識電収: Pagefindを導入」を選んでもよい。

## 普段の確認

準備後は従来どおり次の一つだけでよい。

```sh
python3 scripts/paper_tool.py check-all
```

自動テスト、移行台帳、サイト生成に続いてPagefind索引を生成し、公開物を承認済み基準と
比較する。Pagefind索引はmacOSとGitHub ActionsのLinuxでチャンク名やWASMのバイト列が
変わるため、SHAの一括比較からは除外し、直前の索引生成工程で必須ファイル群を検査する。
検索ページと起動スクリプトは従来どおりSHAで厳密に比較する。索引生成だけをやり直す場合は
次を使う。

```sh
python3 scripts/paper_tool.py stage _site
python3 scripts/paper_tool.py pagefind-index _site
```

その後、通常のローカルサーバーで `/search/` を開く。

```sh
python3 -m http.server 8000 --directory _site
```

## 公開

GitHub Actionsは固定バージョンのextended版を導入し、サイト生成後に主HTML版を索引して
からGitHub Pagesへ送る。索引対象は日付形式の正式URLにある
`papers/20??-??-??-??/html/index.html` に限定し、旧URL互換コピーを重複登録しない。
Pagefindの導入失敗、索引生成失敗、必須索引ファイルの欠落がある場合は公開を停止する。
