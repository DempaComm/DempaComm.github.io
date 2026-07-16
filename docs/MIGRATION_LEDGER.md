# 移行台帳

電波通信の記事とMyBlog内の原稿を対応付け、移行状況を管理するための台帳です。

## ファイル

- `ledger/migration-ledger.csv`: 人が編集する正本
- `ledger/migration-ledger.json`: CSVから生成する機械処理用データ

台帳に保存するMyBlogの場所は、`MyBlog/Myblogstr` からの相対パスです。利用者名を
含む絶対パスは保存しません。台帳ファイルはGitHub Pagesの公開物には含めませんが、
公開GitHubリポジトリのソースとしては閲覧できます。`notes` に本名、メールアドレス、
非公開URLなどを書かないでください。

## 最初の走査と再走査

```sh
python3 scripts/migration_ledger.py scan /path/to/MyBlog/Myblogstr
```

TeX、PDF、BibTeX、BSTが存在するディレクトリを原稿候補として登録します。既存の
`papers/*/paper.json` に記録された原本SHA-256と一致する候補は、自動的に
`published` として対応付けます。

同じ原稿が複数の年別フォルダにある場合は、SHA-256が一致するものだけを重複として
まとめます。公開済みの候補を最優先し、次にTeXとPDFの両方がある候補、浅い場所に
ある候補の順で正本候補を自動選定します。ファイル名が同じでも内容が異なる改訂版は
重複扱いしません。

標準では `2015`、`2016` のような年フォルダだけを走査します。`MyBlogCOPY` などの
バックアップ枝は台帳へ載せません。非年フォルダも意図的に調べる場合だけ
`--include-non-year` を指定します。

再走査しても、CSVで手入力した次の項目は維持されます。

- `status`
- `published_at`
- `sequence`
- `title`
- `original_url`
- `tags`
- `target_slug`
- `math_section`
- `build_engine`
- `author_review`
- `notes`

## 編集後の生成と検査

CSVを編集したらJSONを再生成します。

```sh
python3 scripts/migration_ledger.py build
```

整合性を検査します。

```sh
python3 scripts/migration_ledger.py check
python3 scripts/migration_ledger.py stats
python3 scripts/migration_ledger.py duplicates
```

`check` は、重複した原稿番号・元記事URL、不正な状態、公開済み原稿の台帳漏れ、
重複グループの不整合、古いJSONを検出します。GitHub Actionsでも公開前に実行します。

## 重複情報

- `duplicate_status`: `unique`、`canonical`、`duplicate` のいずれか
- `duplicate_group`: 同一内容をまとめる安定したグループ番号
- `canonical_record_id`: 採用する正本候補の台帳番号
- `duplicate_basis`: `tex+pdf`、`tex`、`pdf` のいずれが一致したか

`tex+pdf` はTeX群とPDF群がともに完全一致、`tex` と `pdf` はそれぞれ片方だけの
完全一致です。一部一致やファイル名だけの一致は自動的に統合しません。
`duplicates` コマンドでは、各グループの正本候補を `C`、複製候補を `D` として
一覧表示します。

## 状態

- `source_found`: MyBlog内で原稿候補を発見
- `metadata_ready`: 公開日時、記事名、元URL、タグの確認済み
- `privacy_review`: 著者名などの公開可否を検査中
- `ready`: 必要情報と検査が揃い、取り込み可能
- `published`: GitHub Pagesへ移行済み
- `skipped`: 移行しないと判断

## 著者情報の確認状態

- `pending`: 未確認
- `approved`: 公開可能と確認済み
- `blocked`: 公開不可の情報を含む
- `legacy_unrecorded`: 旧移行原稿のため個別記録なし
- `not_applicable`: 対応するMyBlog候補を自動特定できていない

`tags` と各ファイル欄で複数値を記入する場合は、半角の縦棒 `|` で区切ります。
