# 数識電収 — 数学原稿アーカイブ

**数学識電脳界溢出部位封神蔵収 私と放電**

数学記事のTeX原稿と、自動生成したPDFを公開するGitHub Pagesリポジトリです。

- 公開サイト: https://dempacomm.github.io/
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

各原稿は `YYYY-MM-DD-NN` で保存します。`paper.json` に電波通信のタグ、検索キーワード、原本と現在承認済みのSHA-256を記録し、`keywords.txt` とサイトの検索一覧を自動生成します。通常の移行では原稿をバイト単位でコピーし、明示的な変更指示がある場合だけ承認履歴を追加します。

```sh
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py audit
python3 scripts/paper_tool.py catalog --check
```

使い方の詳細は `docs/MIGRATION.md` を参照してください。

はてなブログのMT形式バックアップ原本は、このリポジトリの外で保管します。検査・変換済みの公開用データだけを配置します。
