# dempa-typst-converter

Tylaxが生成したTypstソースに、意味が一意に決まる補正だけを適用し、電波通信用の
共通スタイルで組版するための試験パッケージである。元のLaTeX原稿は変更しない。

このフォルダは、現在は数識電収リポジトリ内で開発する。構成とライセンスを自己完結させて
いるため、必要になった時点でフォルダ単位の独立リポジトリへ切り出せる。

作業を引き継ぐ場合は、最初に [`docs/HANDOFF.md`](docs/HANDOFF.md) を読む。

## 現在の状態

バージョン `0.3.0a0` の実験段階である。文字列・コメント外に残った
`識別子\neq識別子` に加え、対応する開始・終了マーカーを持つ定義・命題・定理・補題・系、
事実・例、先頭ラベル、変換済みラベルへの参照、明示的な終端記号を持つ証明を変換する。
Tylaxが英語の固定表示へ潰した `Fact` と `Lemma`、残存した `display`、手書き参考文献の
図扱い、数字だけのラベル、単一行境界を持つ古い証明、`\card`・`\rm dom`・`\rm cod` の
固定表示も補正する。元TeXの `\cap` 件数と一致する場合に限り、数式中へ残った `sect` を
Typstの `inter` へ補正する。
参考文献項目を復元できた場合は、末尾に残る `\nocite{*}`、BibTeX style、databaseの制御行も
表示内容ではないTylax断片として除去する。項目がない場合は推測で除去しない。
証明本文中のTypst文字列、入れ子コメント、URLは本文として保持し、それらの内部にある偽の
証明マーカーや終端断片は境界判定に使わない。
境界が欠けた環境、重複ラベル、未解決参照、未対応LaTeX命令は推測で直さず停止する。

- 生のTylax出力は書き換えない。
- 入力・補正版・報告に同じパスを指定できず、既存の出力も上書きしない。
- 補正内容と停止理由をJSONへ記録する。
- 停止対象の未対応命令、残存ラベル、未解決参照、境界マーカーについて、生のTylax入力を
  基準とする1始まりの行・列を `diagnostics` 配列とCLIへ記録する。従来の
  `blocking_findings` も互換性のため維持する。
- 証明開始マーカーが複数ある場合、補正後に残ったマーカーだけを生入力上の正確な位置へ
  対応付ける。補正前後の出現数が予期せず変わった場合は、誤った位置を推測せず停止する。
- タイトル直後のTylax由来区切りを削除した場合、その範囲内の記号を残存記号の診断へ含めない。
- Typstが導入済みなら、出力前に一時領域で実コンパイルして構文エラーを停止理由へ加える。
- 元TeXを `--latex-source` で読み取り専用の手掛かりとして渡した場合だけ、環境種別・順序・
  題名先頭がすべて一致する任意題名を本文から分離する。不一致なら停止する。
- Tylaxが任意題名をラベルの前へ移した場合も、題名の完全一致後に現れるラベルだけを復元する。
- TylaxがLaTeX `description` の項目境界を `""\` へ潰した場合、項目数と数式外の項目名断片が
  元TeXと一致するときだけ、Typstの `/ 項目: 本文` へ復元する。
- 数式中の `sect` は、元TeXの本文にある `\cap` 件数と一致する場合だけ `inter` へ変換する。
  プリアンブル、コメント、`\end{document}` 後は数えず、ヒントなし・件数不一致では停止する。
- 整形式な `enumerate[label=\textup{(\arabic*)}]` は、元TeXとTylaxのリスト数・項目数・
  ラベル順がすべて一致する場合だけ、自動番号付きの参照可能項目へ変換する。
- 元TeXに番号なし表示数式だけがある場合はTylaxの一律番号を除去し、番号方式が混在する
  場合は一意に復元できないため停止する。
- 元TeXを渡さない場合、Tylaxが失った任意題名と本文の境界は推測せず、要目視事項として
  JSONへ記録する。
- 生成結果は常に人間による確認を必要とする。
- このツール単独で公開承認は行わない。
- 未対応のCD可換図式は、内部の `@V` を参照と誤認せず専用の停止理由と入力位置を報告する。

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
├── docs/                    引き継ぎ・導入・変換・設計・公開手順
├── pyproject.toml           Pythonパッケージ定義
└── LICENSE                  Apache-2.0
```

## 最短の試し方

必要なアプリと開発環境の準備は [`docs/INSTALLATION.md`](docs/INSTALLATION.md) を参照する。

```sh
python3 -m pip install -e .
t2l input.tex -o work/tylax.raw.typ
dempa-typst-correct work/tylax.raw.typ \
  --latex-source input.tex \
  --output work/main.typ \
  --report work/correction-report.json
typst compile work/main.typ work/main.pdf
```

定理構造を変換した場合は、補正器が `main.typ` と同じ場所へ `dempa-style.typ` も作る。
未対応構造が残る場合、補正コマンドは終了コード `2` で停止し、`main.typ` を作らずに
報告だけを保存する。詳しい流れは
[`docs/CONVERSION_WORKFLOW.md`](docs/CONVERSION_WORKFLOW.md) を参照する。

## Typstスタイル

`dempa-style.typ` は、A4、日本語本文、タイトル、共通番号を使う定義・命題・定理・事実・例、
証明、番号参照できる列挙項目、参考文献表示を提供する。変換器はラベルを番号付き要素へ付け、
Tylaxの番号参照をTypstの番号参照へ変える。

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

#numbered-list-start()
#numbered-item[第一の条件。] <condition-one>
#numbered-item[第二の条件。] <condition-two>

条件 #ref(<condition-one>, supplement: none) を使う。
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
