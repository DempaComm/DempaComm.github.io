# 数識電収 — 数学原稿アーカイブ

**数学識電脳界溢出部位封神蔵収 私と放電**

数学記事のTeX原稿と、自動生成したPDFを公開するGitHub Pagesリポジトリです。

- 公開サイト: https://dempacomm.github.io/
- 全原稿アーカイブ: https://dempacomm.github.io/archive/
- 数学記事総覧: https://dempacomm.github.io/math/
- はてなブログ: https://concious4410.hatenablog.com/
- 原稿: `papers/`
- 自動ビルド: `.github/workflows/pages.yml`

## 試験公開中の原稿

- 単純なTeX: `papers/2015-08-28-01/`
- 大規模原稿: `papers/2018-10-14-01/`
- BibTeX: `papers/2024-01-03-01/`
- 図・相互参照: `papers/2024-01-08-01/`

この4原稿に加え、年別表示・検索・タグ絞り込みのプロトタイプとして、記事が存在する2015年から2026年まで各年1記事を追加しています。年別プロトタイプは元のTeXと当時の完成PDFを無改変で保存し、自動再コンパイルの対象にはしません。

## 原稿保護と移行

各原稿は `YYYY-MM-DD-NN` で保存します。`paper.json` に電波通信のタグ、検索キーワード、原本と現在承認済みのSHA-256を記録し、`keywords.txt` とサイトの検索一覧を自動生成します。通常の移行では原稿をバイト単位でコピーし、公開TeX・PDFの個人情報検査記録を保存します。明示的な変更指示がある場合だけ承認履歴を追加します。

```sh
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py audit
python3 scripts/paper_tool.py catalog --check
python3 scripts/paper_tool.py stage _site
python3 scripts/paper_tool.py check-links _site
python3 scripts/paper_tool.py inspect-file /path/to/manuscript.tex
```

トップページには新着6件だけを表示し、全件検索・タグ索引・公開年別一覧は
`archive/` に自動生成します。`math/` は数学分野別総覧への入口となり、
各分野の記事一覧を `math/<分野>/` に生成します。RSSは `feed.xml`、
サイトマップは `sitemap.xml` で公開します。

使い方の詳細は `docs/MIGRATION.md` を参照してください。ファイル1本だけからの非常用取り込みと、一般的なAIへ渡す作業指示は、TeX版を `docs/MINIMAL_TEX_IMPORT.md`、PDF版を `docs/MINIMAL_PDF_IMPORT.md` にまとめています。

はてなブログのMT形式バックアップ原本は、このリポジトリの外で保管します。検査・変換済みの公開用データだけを配置します。
