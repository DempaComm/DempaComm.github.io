# Pagefind本文全文検索

## 対象

既存の全原稿アーカイブは、全191記事の題名、説明、タグ、キーワード、公開年を検索する。
Pagefindはこれを置き換えず、主LaTeXML HTML版がある記事だけを本文、節見出し、定理名、
参考文献から検索する。元版などの別HTMLは重複結果を避けるため索引しない。

索引はPagefind 1.5.2 extendedで日本語用に生成し、検索処理は公開ブラウザ内だけで行う。
外部の検索サーバーへ原稿や検索語を送らない。

### 日本語の単語分割

Pagefind 1.5.2の索引生成とブラウザの `Intl.Segmenter` は別の辞書を使う。
例えば索引の「ディリクレ」が検索時に「ディリ／ク／レ」と分かれると0件になる。
`site/pagefind.py` は索引断片の単語境界からカタカナ語を集め、`site/pagefind_query.js` で
既知の一語に一致する隣接カタカナ片だけを結合する。空白、未知語、他言語の分割は維持する。
検索先へ渡す強調語は、濁点を取り除く前の語を使う。

公式の分割拡張口がないため、固定版が生成する `pagefind.js` と `pagefind-worker.js` の
対応する2箇所だけを生成後に補正する。形式が変わった場合は公開を停止するため、Pagefindの
更新時にはこの補正も確認する。補助処理は両方へ埋め込み、classic workerでも動作させる。
Node.jsとPagefindを導入した環境では、自動テストで小さな実索引を作り、単語・複合語・
引用検索、強調語の濁点、workerの構文を検査する。未導入環境ではこの結合テストだけを省略する。

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

## 該当箇所への移動

公開用HTMLの見出しに一意なIDを補い、Pagefindの節別検索結果から直接リンクする。
結果には最大3箇所の見出しを示し、本文を開いた後も検索語を強調する。
強調表示はローカル生成した `pagefind-highlight.js` を使い、MathMLの内部を除外する。
元HTMLの見出し・定理IDは維持する。
検索語を含む脚注は自動で開き、該当箇所が脚注内にある場合は脚注番号へ移動する。
数式を含む節ラベルは、見出しメタデータから許可したMathML要素・属性だけを再構成する。
LaTeXの代替ソース、注釈、入れ子リンク、イベント属性は表示しない。

仕様の参照先：
- https://pagefind.app/docs/sub-results/
- https://pagefind.app/docs/highlighting/
- https://pagefind.app/docs/highlight-config/
