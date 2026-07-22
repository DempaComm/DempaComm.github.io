# 数識電収 — 数学原稿アーカイブ

**数学識電脳界溢出部位封神蔵収 私と放電**

数学記事のTeX原稿と、自動生成したPDFを公開するGitHub Pagesリポジトリです。

- 公開サイト: https://dempacomm.github.io/
- 全原稿アーカイブ: https://dempacomm.github.io/archive/
- 数学記事総覧: https://dempacomm.github.io/math/
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

自動テスト、SHA、変更履歴、カタログ、移行台帳、公開サイト生成、リンク、公開物の
基準比較を順番に確認します。VS Codeでは「ターミナル」→「タスクの実行」から
「数識電収: すべて確認」を選んでも同じ確認を実行できます。

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

トップページには新着3件だけを表示し、全件検索・タグ索引・公開年別一覧は
`archive/` に自動生成します。`math/` は数学分野別総覧への入口となり、
各分野の記事一覧を `math/<分野>/` に生成します。RSSは `feed.xml`、
サイトマップは `sitemap.xml` で公開します。

使い方の詳細は `docs/MIGRATION.md` を参照してください。VS Codeで保護されたTeX・PDFを更新するときの再検査、`approve-change`、検証、pushの手順も同書の「VS Codeで保護されたTeX・PDFを更新する」にまとめています。ファイル1本だけからの非常用取り込みと、一般的なAIへ渡す作業指示は、TeX版を `docs/MINIMAL_TEX_IMPORT.md`、PDF版を `docs/MINIMAL_PDF_IMPORT.md` にまとめています。

電波通信の記事とMyBlog原稿の対応、未移行・検査中・公開済みの状態は
`ledger/migration-ledger.csv` で管理します。使い方は
`docs/MIGRATION_LEDGER.md` にまとめています。

はてなブログのMT形式バックアップ原本は、このリポジトリの外で保管します。検査・変換済みの公開用データだけを配置します。
