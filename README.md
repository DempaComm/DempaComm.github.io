# 数識電収 — 数学原稿アーカイブ

**数学識電脳界溢出部位封神蔵収 私と放電**

数学記事のTeX原稿と、自動生成したPDFを公開するGitHub Pagesリポジトリです。
自動コンパイルはlatexmkで管理し、原稿ごとにpLaTeX、upLaTeX、pdfLaTeX、
LuaLaTeX、XeLaTeXを選択できます。既定値はpLaTeXです。

- 公開サイト: https://dempacomm.github.io/
- 全原稿アーカイブ: https://dempacomm.github.io/archive/
- 数学記事総覧: https://dempacomm.github.io/math/
- 原稿を探索: https://dempacomm.github.io/explore/
- 本文全文検索: https://dempacomm.github.io/search/
- はてなブログ: https://concious4410.hatenablog.com/
- 原稿: `papers/`
- 自動ビルド: `.github/workflows/pages.yml`

## 収録状況

現在は2015年から2026年までの191記事を収録しています。TeX・PDF付き、PDFのみ、TeXのみ、ブログ本文のみの記事が含まれます。保存している元のTeXと当時の完成PDFは無改変で維持し、再現可能な原稿だけを自動コンパイルの対象にします。`paper.json` の `kind` は取り込み方法を記録する内部管理項目で、公開ページには表示しません。

## 原稿保護と移行

各原稿は `YYYY-MM-DD-NN` で保存します。`paper.json` に電波通信のタグ、検索キーワード、原本と現在承認済みのSHA-256を記録し、`keywords.txt` とサイトの検索一覧を自動生成します。通常の移行では原稿をバイト単位でコピーし、公開TeX・PDFの個人情報検査記録を保存します。明示的な変更指示がある場合だけ承認履歴を追加します。

普段の変更確認は、リポジトリのルートで次の一つだけを実行します。

```sh
python3 scripts/paper_tool.py check-all
```

自動テスト、移行台帳、公開サイト生成兼総合検査、Pagefind日本語全文索引、公開物の基準比較を順番に確認します。
公開サイト生成の内部でSHA、カタログ、リンクも一度ずつ検査します。VS Codeでは「ターミナル」→「タスクの実行」から
「数識電収: すべて確認」を選んでも同じ確認を実行できます。
任意の追加機能だけが失敗した場合は公開を継続しますが、`WARN feature failed` と対象原稿、
失敗段階、理由を表示するため、見落とさずに後から修正できます。

個別の原因調査や特定作業では、従来の詳しいコマンドも引き続き使えます。

```sh
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py audit
python3 scripts/paper_tool.py catalog --check
python3 scripts/migration_ledger.py check
python3 scripts/migration_ledger.py metadata
python3 scripts/migration_ledger.py render-metadata-review
python3 scripts/migration_ledger.py archive-priority
python3 scripts/paper_tool.py stage _site
python3 scripts/paper_tool.py check-links _site
python3 scripts/site_snapshot.py check _site
python3 scripts/paper_tool.py inspect-file /path/to/manuscript.tex
```

一つの記事だけを素早く確認する場合は次を使います。承認済みSHA、個人情報検査記録、
`keywords.txt` を確認し、自動ビルド対象なら `latexmk` も実行します。

```sh
python3 scripts/paper_tool.py check-paper 2015-08-28-01
```

これは編集途中の補助検査です。未承認の原稿変更は停止し、`review-change` の利用を促します。
コミット前には必ず `check-all` を実行します。

ローカルの試験出力や承認済み個人情報検査を整理するときは、削除候補だけを表示する
`python3 scripts/paper_tool.py clean-local` を使います。実際の削除方法と安全範囲は
`docs/LOCAL_CLEANUP.md` にまとめています。

トップページには新着3件だけを表示し、全件検索・タグ索引・公開年別一覧は
`archive/` に自動生成します。`math/` は数学分野別総覧への入口となり、
各分野の記事一覧を `math/<分野>/` に生成します。RSSは `feed.xml`、
サイトマップは `sitemap.xml` で公開します。

`explore/` からは、テーマ別に順番を定めた読書経路、初出・移行・改訂を並べた
原稿の系譜、電波通信のタグを使った原稿関係図へ移動できます。登録方法は
`docs/EXPLORATION.md` にまとめています。

`search/` では、LaTeXMLの主HTML版がある記事を本文、節見出し、定理名、参考文献から
検索できます。最初の導入とローカル確認方法は `docs/PAGEFIND.md` にまとめています。

`statements/` では、LaTeXMLの主HTML版から抽出した定理、定義、命題、反例を種類別に
参照できます。各原稿ページには、正式な訂正・追記と報告窓口も表示します。登録方法は
`docs/STATEMENTS_AND_CORRECTIONS.md` にまとめています。

LaTeXMLによるHTML変換は通常公開から隔離した試験コマンドとして導入しています。自動検査と
PDFとの目視比較を通過した原稿は、試験HTML版として個別公開できます。全体状況を先に
確認する場合は、未変換TeXを一括処理し、自動合格版だけを「自動変換・未目視」と明示して
追加できます。手順と確認項目は `docs/LATEXML_TRIAL.md` を参照してください。

普段の原稿修正は、記事番号・ファイル名・理由の三項目だけを入れればコマンドをコピー
できる `docs/EDITING_WORKFLOW.md` を参照してください。詳しい移行と手動承認は
`docs/MIGRATION.md` にまとめています。ファイル1本だけからの非常用取り込みと、一般的な
AIへ渡す作業指示は、TeX版を `docs/MINIMAL_TEX_IMPORT.md`、PDF版を
`docs/MINIMAL_PDF_IMPORT.md` にまとめています。

TeX原稿はVS Codeで編集したまま、変更検査、HTML試験生成、公開準備、総合検査をブラウザで
行いたい場合は、`python3 scripts/paper_tool.py local-admin` でlocalhost専用の管理画面を
起動できます。使い方と安全上の境界は `docs/LOCAL_ADMIN.md` を参照してください。

電波通信の記事とMyBlog原稿の対応、未移行・検査中・公開済みの状態は
`ledger/migration-ledger.csv` で管理します。使い方は
`docs/MIGRATION_LEDGER.md` にまとめています。

はてなブログのMT形式バックアップ原本は、このリポジトリの外で保管します。検査・変換済みの公開用データだけを配置します。

## 引き継ぎ状況（2026-07-29）

基本サイトは運用可能な状態にあり、GitHub Pagesへの直近のデプロイ成功を確認済みです。
記事公開、原稿保護、移行台帳、年・タグ・数学分野別一覧、全文検索、LaTeXML HTML版、
定理等索引、訂正・追記欄、読書経路、原稿の系譜、原稿関係図、RSS、サイトマップまで
実装済みです。第0〜10段階の基盤再構成と、その後の主要な保守性改善も完了しています。

今後の中心は必須機能の穴埋めではなく、次の継続整備と実験です。

- 「自動変換・未目視」のLaTeXML HTML版を元PDFと比較し、確認済み版へ順次昇格する。
- 読書経路を増やし、ほぼ完全グラフになりやすい原稿関係図の関係線を後日再検討する。
- Typst変換は `typst-trial` と代表4分類の初回比較まで完了している。未補正出力の参照、
  入れ子数式、独自命令を安全に補正できる範囲が次の課題である。
- SATySFi変換は別のタスクで扱う。成熟したLaTeX全文変換器が見当たらないため、
  Pandoc ASTからSATySFiへ書き出す小型変換器を別リポジトリで試作する案がある。
- MathJaxは導入せず、LaTeXMLが生成するMathML表示を維持する。
- 生成済みファイルとCSSの再整理は低優先度であり、利益が明確な場合だけ行う。
- Search Consoleの状態確認と、非公開バックアップの別媒体への複製はサイト外の運用作業として残る。

詳細な優先順位は [`docs/TODO.md`](docs/TODO.md)、次のAIや作業者が最初に守る規則は
[`AGENTS.md`](AGENTS.md) を参照してください。新しい作業では、まず `git status` と該当文書を
確認し、完了済みの機能を作り直さないでください。
