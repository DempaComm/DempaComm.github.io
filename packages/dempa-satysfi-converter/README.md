# dempa-satysfi-converter

LaTeXをPandoc JSON AST経由でSATySFiへ保守的に変換する試作CLIである。入力原稿を一時領域へ
コピーし、AST、SATySFiソース、変換報告、コンパイルログ、PDFを指定した隔離先へ分けて保存する。
未対応のASTノードや数式命令は推測せず、安全に停止する。

## 状態

- バージョン: `0.1.0a0`
- 実装: Python 3.11以上
- 中間表現: Pandoc JSON AST
- 組版: SATySFiと同梱の `dempa.satyh`
- ライセンス: Apache-2.0
- 公開連携: なし（生成物は常に人間の確認が必要）

本文、インライン・別行立て数式、定義・命題・定理、証明、相互参照、単純な箇条書きを初期範囲と
する。引用、参考文献、図版、表、任意の独自マクロ、複雑な定理本文は未対応である。

## 実装言語の方針

当面はPython実装を維持する。SATySFi公式の
[日本語README](https://github.com/gfngfn/SATySFi/blob/master/README-ja.md) と
[概説](https://github.com/gfngfn/SATySFi/blob/master/demo/demo.saty) は、静的型つき函数型言語、
コマンド定義の可読性とカスタマイズ性、早く明確なエラー報告、局所的な処理を重視しているが、
外部変換器にもOCamlを要求してはいない。この変換器では、その思想を次の設計として取り入れる。

- Pandoc ASTからSATySFiへの変換規則を小さく局所的に保つ。
- 未対応構造を推測せず、安全停止して理由を報告する。
- SATySFi固有の組版定義を `.satyh` に分離する。
- 生成後はSATySFi自身の型検査とコンパイルを通す。

OCamlへの移行は、SATySFiのOCamlライブラリを直接利用する、OPAM/Duneで単一ツールとして配布する、
またはASTの網羅性をOCamlの型検査で保証する必要が明確になった場合に再検討する。それまでは言語を
揃えること自体を目的に書き直さず、将来変換コアだけを交換できるよう中間表現との境界を維持する。
Python版とOCaml版を同時に育てる二重実装は行わない。

## 実行

PandocとSATySFiを用意し、このフォルダで次を実行する。

```sh
PYTHONPATH=src python3 -m dempa_satysfi_converter.cli \
  examples/minimal/input.tex \
  --output-dir /tmp/dempa-satysfi-example \
  --compile
```

既存の生成ファイルがある出力先は上書きしない。`conversion-report.json` の
`manual_review_required` は常に `true`、`publishable` は常に `false` である。

インストールして使う場合は `pip install -e .` 後に `dempa-satysfi-convert` を実行できる。

## 検査

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

テストは新規作成した人工例だけを使い、決定性、上書き拒否、安全停止、数式補正、SATySFiでの
PDF生成を確認する。実原稿はテストや利用例へ収録しない。

詳細は [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) と
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) を参照する。
