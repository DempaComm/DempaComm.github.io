# Contributing

変更は一つの補正規則または一つのスタイル機能に限定し、人工的な最小テストを添える。

## 補正規則

- 意味が一意に決まることを説明する。
- 入力、生出力、期待結果を小さく保つ。
- 置換回数を報告する。
- 未知の構造を黙って削除しない。
- 実在の原稿本文をテストへコピーしない。

## 確認

```sh
python3 -m unittest discover -s tests -v
typst compile --root . examples/simple/main.typ /tmp/dempa-typst-example.pdf
```

Pythonコードは標準ライブラリだけで動く状態を維持する。Tylax本体のコードをコピーせず、
一般的な変換バグは上流へ最小例とともに報告する。
