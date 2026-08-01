# SATySFi変換試作

LaTeXからSATySFiへの変換は未実装である。別スレッドで変換器を開発できるよう、
[`packages/dempa-satysfi-converter/`](../packages/dempa-satysfi-converter/README.md) に予約領域、
要件、構成案、引き継ぎを用意している。

2026-08-01時点で、ローカルにはSATySFi `v0.0.11-22-gc2cbc48`、opam `2.5.2`、
Pandoc `3.10.1` が導入済みである。変換器本体、SATySFiスタイル、テスト入力、公開機能は
まだ存在しない。

## 方針

- 元TeXと公開ファイルを変更しない。
- 実験出力は隔離し、自動公開しない。
- 実原稿を公開リポジトリの例やテストへ含めない。
- Pandoc JSON AST等の構造化中間表現を第一候補として調査する。
- 未対応構造は推測せず停止する。
- 生成PDFは元PDFと全ページ比較する。

別スレッドは最初に
[`HANDOFF.md`](../packages/dempa-satysfi-converter/docs/HANDOFF.md) を読み、未決事項を確定する。
