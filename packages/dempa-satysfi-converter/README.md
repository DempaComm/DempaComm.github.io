# dempa-satysfi-converter

LaTeX原稿からSATySFi派生物を作る変換器を、別スレッドで開発するための予約領域である。
このフォルダには現時点で変換器の実装を入れていない。

数識電収のサイト本体から独立させ、将来はこのフォルダだけを別リポジトリへ切り出せる構成を
目指す。元TeXを変更せず、生成物を隔離し、未知の構造を推測変換しない方針はTypst試験と共通である。

## 現在の状態

- 状態: 設計待ち・実装未着手
- 変換器: なし
- SATySFi: ローカル導入済み
- Pandoc: ローカル導入済み
- 公開機能: なし
- GitHubリポジトリ: 未作成
- ライセンス: 実装開始時に決定する

## 予定するフォルダ

```text
dempa-satysfi-converter/
├── src/                 変換器本体
├── styles/              電波通信用SATySFiクラス・ヘッダ
├── tests/               人工的な最小入力と回帰テスト
├── examples/minimal/    実原稿を含まない利用例
├── docs/
│   ├── REQUIREMENTS.md  必須要件と安全条件
│   ├── ARCHITECTURE.md  構成案と責務境界
│   └── HANDOFF.md       別スレッドへの引き継ぎ
└── README.md
```

実装担当は最初に [`docs/HANDOFF.md`](docs/HANDOFF.md) と
[`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) を読むこと。推奨経路はLaTeXを直接正規表現で
変換する方法ではなく、Pandoc JSON AST等の構造化された中間表現を調査する方法である。

## やらないこと

- この予約タスク内で変換器を実装しない。
- `papers/*` の実原稿を例やテストへコピーしない。
- 元TeX、PDF、BibTeX、図版、`paper.json` を変更しない。
- 変換成功だけでSATySFi版を公開しない。
- Typst補正器へSATySFi固有処理を混在させない。
