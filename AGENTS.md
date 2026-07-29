# AGENTS.md

このファイルは、このリポジトリを扱うAIと人間の作業者向けの最優先引き継ぎ事項である。
ルート以下の全ファイルに適用する。詳しい仕様はリンク先の文書を読み、推測で既存規則を
置き換えないこと。

## 1. 作業開始時

1. 日本語で、利用者が技術に詳しくないことを前提に説明する。
2. `git status --short` を確認し、利用者の未コミット変更を消去・上書きしない。
3. [`README.md`](README.md) と [`docs/TODO.md`](docs/TODO.md) を読み、完了済みの機能を
   再実装しない。
4. 作業内容に応じて、原稿修正は [`docs/EDITING_WORKFLOW.md`](docs/EDITING_WORKFLOW.md)、
   移行は [`docs/MIGRATION.md`](docs/MIGRATION.md)、サイト機能は
   [`docs/SITE_FEATURES.md`](docs/SITE_FEATURES.md) を先に読む。
5. 調査・説明だけを求められた場合は、明示的に依頼されるまでファイルを変更しない。

## 2. 絶対に守る原稿保護規則

- `papers/*` 内のTeX、PDF、BibTeX、BST、図版、その他の公開原稿を、利用者の明示的な
  指示なしに書き換えない。コンパイルエラーやLaTeXML変換エラーの解消も、原本を勝手に
  修正する理由にはならない。
- 通常の移行では原稿をバイト単位でコピーし、内容を「改善」「訂正」「整形」しない。
- 変換上の補正はLaTeXML・Typst等の変換処理側または隔離した派生物に実装し、元TeXを
  変更しない。
- `paper.json` のSHA-256を手入力でつじつま合わせしない。保護ファイルの意図的変更には
  `review-change` と `finish-change` を使用する。
- TeX・PDFの個人情報検査は自動結果だけで承認しない。利用者が報告とPDF全ページを
  目視した後だけ `--privacy-reviewed` を指定できる。
- 本名、メール、所属、住所、第三者名義、著作権上の懸念を検出した場合は公開処理を止め、
  利用者へ具体的に報告する。公開可否をAIだけで決定しない。
- はてなブログの生のMTエクスポートと非公開バックアップはリポジトリへ追加しない。

既存原稿の標準的な変更手順は次の二段階である。

```sh
python3 scripts/paper_tool.py review-change "記事番号" --file "ファイル名"
python3 scripts/paper_tool.py finish-change "記事番号" \
  --reason "修正理由" \
  --file "ファイル名" \
  --privacy-reviewed \
  --accept-public-change
```

`--privacy-reviewed` は利用者の目視確認を得た場合だけ使用する。新規ファイル追加や複数ファイル
変更では手順が異なるため、上記コマンドを機械的に流用せず関連文書を確認すること。

## 3. サイト実装の境界

- 基本サイトの生成コードは `dempa_site/`、薄いCLI入口は `scripts/paper_tool.py`、通常公開の
  機能登録は `dempa_site/features/registry.py` に置く。
- 新しい閲覧機能は [`docs/SITE_FEATURES.md`](docs/SITE_FEATURES.md) のインターフェースと
  隔離生成規則に従う。機能固有処理をCLIやサイト生成本体へ直接埋め込まない。
- 必須ナビゲーションに不可欠なものだけ `required=True` とする。外部変換器や特定原稿の
  成否に左右される実験機能は、基本のPDF・TeX公開を止めない設計にする。
- 外部CDNへ依存させない。現在の関係図もローカルのSVG・JavaScriptで動作する。
- MathJaxは導入しない。数式HTMLはLaTeXMLのMathMLを維持する。
- `paper.json` の `html_versions` がHTML版メタデータの現行形式である。旧フィールドとの
  混在は作らない。
- `_site/`、`_experiments/`、`.privacy-review/`、LaTeX中間生成物、`papers/*/main.pdf` は
  通常Gitへ追加しない。GitHub Actionsが必要なPDFと公開サイトを生成する。

## 4. 変換実験

- LaTeXML、Typst、将来のSATySFi変換は原稿公開とは別の派生処理として扱う。
- 変換時は原稿を一時領域へコピーし、元TeXと `paper.json` を変更しない。
- 実験出力は `_experiments/` に置き、自動公開しない。自動検査と人間による元PDFとの比較を
  通ったものだけ正式な公開候補にする。
- LaTeXMLの現行手順は [`docs/LATEXML_TRIAL.md`](docs/LATEXML_TRIAL.md)、Typstの現行手順は
  [`docs/TYPST_TRIAL.md`](docs/TYPST_TRIAL.md) を参照する。
- SATySFi変換器はこのリポジトリへ即座に組み込まず、別タスク・別リポジトリでの試作を
  第一案とする。公開する場合は、実原稿ではなく新規作成した小さなテスト原稿を含める。

## 5. 検査と公開

通常の変更後、コミット前の最終検査は必ず次を実行する。

```sh
python3 scripts/paper_tool.py check-all
```

- 一記事の編集中は `check-paper <記事番号>` を補助的に使えるが、最終検査の代わりにはならない。
- 公開物スナップショットの差分を、自動的または理由不明のまま承認しない。意図した公開変更だけを
  確認してから基準を更新する。
- コミットとpushは利用者が明示的に依頼した場合だけ行う。依頼された場合も、差分と検査結果を
  確認してから実施する。
- mainへのpush後はGitHub Actionsのbuildとdeployが成功したことを確認する。警告と失敗を区別し、
  deploy成功を利用者が確認した場合は同じ確認を不要に繰り返さない。

## 6. 現在の状態と次候補

2026-07-29時点で基本機能と主要リファクタリングは完了し、直近のGitHub Pagesデプロイも
成功確認済みである。緊急の必須機能はない。次候補は以下である。

1. LaTeXMLの「自動変換・未目視」版を元PDFと比較し、確認済みへ昇格する。
2. Typst初回試験で判明した参照、入れ子数式、独自命令の補正方針を小さい原稿から検証する。
3. 読書経路を増やす。
4. 原稿関係図がほぼ完全グラフになる問題を、関係の重みや明示メタデータを使って再設計する。
5. Search Consoleの確認と非公開バックアップ複製を利用者側の運用として行う。
6. SATySFi変換器の試作は別タスクで扱う。

CSS分割と生成済みファイル整理は低優先度である。見た目だけの大規模変更や、既に完了した
リファクタリングのやり直しより、既存機能を壊さない小さな改善を優先する。
