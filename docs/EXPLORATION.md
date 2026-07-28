# 原稿探索機能の管理

`/explore/` は、全原稿一覧とは別の四つの入口をまとめる。

- `/reading-paths/`: 人が順番と案内文を決めた読書経路
- `/lineage/`: 初出、移行、改訂、派生版生成の系譜
- `/graph/`: 電波通信のタグと明示関係を使った原稿関係図
- `/statements/`: 定理、定義、命題、反例から原稿本文へ入る索引

いずれも `python3 scripts/paper_tool.py stage _site` で静的に生成され、外部CDNへ依存しない。
定理等の索引と訂正・追記の登録方法は `STATEMENTS_AND_CORRECTIONS.md` に記載する。

## 読書経路を追加する

`collections/` に英小文字・数字・ハイフンの名前でJSONを追加する。既存の
`metric-spaces.json` などをコピーし、次を変更する。

- `slug`: ファイル名から `.json` を除いた値
- `title`, `description`: 公開ページに表示する案内
- `prerequisites`: 先に読む別の経路のslug。なければ空配列
- `papers`: 原稿番号と、その段階で読む理由

JSON Schemaは `schemas/reading-path.schema.json` にある。公開時に次を拒否する。

- 存在しない原稿番号
- 同じ経路内の原稿重複
- 存在しない前提経路
- 前提経路の循環

## 原稿の系譜を追記する

自動的に、`published_at` を初出、`migration_record_id` を移行台帳、
`approved_changes` を改訂として表示する。ただし、承認理由には個人情報除去などの内部事情が
含まれ得るため、公開ページと `lineage.json` には理由の原文を出さず、改訂した事実と
ファイル数だけを表示する。その他の公開してよい出来事は各 `paper.json` の `history` に記録する。

```json
{
  "recorded_at": "2026-07-26T12:00:00+09:00",
  "kind": "html",
  "summary": "LaTeXMLによるHTML版を確認して公開"
}
```

古い移行日のように根拠がない日付は推測せず、画面上では「日付未記録」とする。

## 原稿関係図の線

`paper-graph.json` は公開時に自動生成する。線は次から作る。

1. 共通する電波通信タグが2個以上ある。
2. 共有タグが1個でも、そのタグを持つ原稿が8件以下である。
3. `paper.json` の `relations` に明示関係がある。

「数学」「すべて」「雑談」「僕のお気に入り」「論文メモ」は広すぎるため線の計算から除外する。
画面ではタグと公開年で絞り込める。最大60件を表示し、表示中の記事はHTML一覧でも確認できる。

明示関係は次の形で記録する。対象原稿番号の存在は通常のmanifest検査で確認される。

```json
{
  "target_slug": "2026-06-28-01",
  "kind": "prerequisite",
  "label": "被覆次元と埋め込み"
}
```
