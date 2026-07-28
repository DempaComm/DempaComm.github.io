# 定理等の索引と訂正・追記

## 定理・定義・命題・反例索引

公開サイト生成時に、各原稿の主LaTeXML HTML版から定理、定義、命題、反例の見出しを
自動抽出する。結果は `/statements/` と機械可読な `/statements/statements.json` に出力する。
旧URL互換コピーと別HTML版は重複を避けるため抽出対象にしない。
反例は専用の定理環境がない原稿が多いため、明示登録がなければ既存の「反例」タグを使って
原稿単位の入口を補完する。

LaTeXMLで種類を判定できない反例や、自動抽出結果を直したい項目は、該当する
`paper.json` の省略可能な `statements` に記録する。同じ `identifier` は自動抽出結果を
上書きする。

```json
"statements": [
  {
    "identifier": "Thmexample3",
    "kind": "counterexample",
    "title": "反例 3（条件を弱められない例）",
    "anchor": "#Thmexample3"
  }
]
```

`kind` は `theorem`、`definition`、`proposition`、`counterexample` のいずれかとする。
`anchor` は主HTML版内の `#` から始まる位置を指定する。

## 訂正・追記欄

全原稿ページに訂正・追記欄を表示する。記録がない原稿にも「登録なし」と、記事番号と
URLが入力済みのGitHub Issue報告リンクを表示する。正式な記録は該当する `paper.json` の
`corrections` に追加する。

```json
"corrections": [
  {
    "recorded_at": "2026-07-28T16:00:00+09:00",
    "kind": "correction",
    "summary": "定理2の仮定に正規性を追加しました。",
    "anchor": "#Thmtheorem2"
  },
  {
    "recorded_at": "2026-07-29T10:00:00+09:00",
    "kind": "addendum",
    "summary": "関連する別証明への説明を追記しました。"
  }
]
```

`kind` は訂正なら `correction`、追記なら `addendum` とする。省略時は訂正として扱う。
`anchor` は省略でき、指定する場合は主HTML版内の `#` から始まる位置とする。
原稿ファイルを同時に直す場合は、従来どおり保護ファイルの変更承認とSHA更新も行う。
