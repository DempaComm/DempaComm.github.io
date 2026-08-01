# dempa-typst-converter

Tylaxが生成したTypstソースに、意味が一意に決まる補正だけを適用し、電波通信用の
共通スタイルで組版するための試験パッケージである。元のLaTeX原稿は変更しない。

このフォルダは、現在は数識電収リポジトリ内で開発する。構成とライセンスを自己完結させて
いるため、必要になった時点でフォルダ単位の独立リポジトリへ切り出せる。

## 現在の状態

バージョン `0.2.0a0` の実験段階である。文字列・コメント外に残った
`識別子\neq識別子` に加え、対応する開始・終了マーカーを持つ定義・命題・定理・補題・系、
先頭ラベル、変換済みラベルへの参照、明示的な終端記号を持つ証明を変換する。境界が欠けた
環境、重複ラベル、未解決参照、未対応LaTeX命令は推測で直さず停止する。

- 生のTylax出力は書き換えない。
- 入力・補正版・報告に同じパスを指定できず、既存の出力も上書きしない。
- 補正内容と停止理由をJSONへ記録する。
- 生成結果は常に人間による確認を必要とする。
- このツール単独で公開承認は行わない。

## フォルダ構成

```text
dempa-typst-converter/
├── src/dempa_typst_converter/
│   ├── correction.py        安全な補正規則と検査
│   ├── cli.py               コマンドライン入口
│   └── styles/
│       └── dempa-style.typ  電波通信のTypst共通スタイル
├── tests/                   人工的な最小テスト
├── examples/simple/         実原稿を含まない組版例
├── docs/                    導入・変換・設計・公開手順
├── pyproject.toml           Pythonパッケージ定義
└── LICENSE                  Apache-2.0
```

## 最短の試し方

必要なアプリと開発環境の準備は [`docs/INSTALLATION.md`](docs/INSTALLATION.md) を参照する。

```sh
python3 -m pip install -e .
t2l input.tex -o work/tylax.raw.typ
dempa-typst-correct work/tylax.raw.typ \
  --output work/main.typ \
  --report work/correction-report.json
typst compile work/main.typ work/main.pdf
```

定理構造を変換した場合は、補正器が `main.typ` と同じ場所へ `dempa-style.typ` も作る。
未対応構造が残る場合、補正コマンドは終了コード `2` で停止し、`main.typ` を作らずに
報告だけを保存する。詳しい流れは
[`docs/CONVERSION_WORKFLOW.md`](docs/CONVERSION_WORKFLOW.md) を参照する。

## Typstスタイル

`dempa-style.typ` は、A4、日本語本文、タイトル、共通番号を使う定義・命題・定理、証明表示を
提供する。変換器はラベルを番号付き要素へ付け、Tylaxの番号参照をTypstの番号参照へ変える。

```typst
#import "path/to/dempa-style.typ": *

#show: dempa_article.with(
  title: "変換試験",
  author: "DempaComm",
  date: [2026-08-01],
)

#definition[定義の本文]
#proposition[命題の本文]
#proof[証明の本文]
#theorem[定理の本文]
```

## 開発時の確認

```sh
python3 -m unittest discover -s tests -v
typst compile --root . examples/simple/main.typ /tmp/dempa-typst-example.pdf
```

設計上の境界は [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)、変更方法は
[`CONTRIBUTING.md`](CONTRIBUTING.md)、独立公開前の確認事項は
[`docs/PUBLISHING.md`](docs/PUBLISHING.md) にまとめている。

## ライセンス

Apache License 2.0。Tylaxのコードは同梱せず、外部コマンドとして利用する。
