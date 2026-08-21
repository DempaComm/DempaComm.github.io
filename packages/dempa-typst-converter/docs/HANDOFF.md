# Typst変換器 引き継ぎ

最終更新: 2026-08-21

この文書は、数識電収のLaTeX原稿をTylax経由でTypstへ安全に変換する試作を、次の作業者へ
引き継ぐための現状記録である。SATySFi変換器は別タスクであり、ここでは扱わない。

## 最初に読むもの

次の順で確認する。

1. リポジトリルートの [`AGENTS.md`](../../../AGENTS.md)
2. この文書
3. [`../README.md`](../README.md)
4. [`../../../docs/TYPST_TRIAL.md`](../../../docs/TYPST_TRIAL.md)
5. [`CONVERSION_WORKFLOW.md`](CONVERSION_WORKFLOW.md)
6. [`ARCHITECTURE.md`](ARCHITECTURE.md)
7. [`../../../docs/TODO.md`](../../../docs/TODO.md)

作業開始時に `git status --short --branch` を実行し、利用者の変更を消さない。引き継ぎ文書を
追加した時点の作業ブランチは `codex/typst-handoff` である。最新状態は必ずGitとGitHubで
再確認し、古いローカル `main` を前提にしない。

## 現在の到達点

パッケージは `0.3.0a0` のアルファ版である。Tylax生出力へ、意味が一意に決まる補正だけを
適用し、補正版、共通Typstスタイル、JSON報告を別ファイルとして生成する。

実装済みの主な補正は次のとおり。

- 数式中に残った単純な `\neq` と `\displaystyle` 由来の `display`
- 絶対値内の単一分数を集合のように表示する余分な波括弧
- 対応するマーカーを持つ定義、命題、定理、補題、系、事実、例
- Tylaxが固定表示へ平坦化した `Fact` と `Lemma`
- 定理等の先頭ラベル、変換済みラベルへの番号参照、共有番号
- 明示的な四角終端記号を持つ証明
- 単純な手書き参考文献
- 任意題名付き定理等の表示

`--latex-source` で元TeXを読み取り専用の手掛かりとして渡すと、環境種別、全体の出現順、
Tylax本文先頭の題名が完全一致した場合だけ題名を分離する。一致しない場合は推測せず停止する。

CLIはTypstが導入済みなら、補正版を書き出す前に一時領域で実コンパイルする。Typstがない
環境では検査省略を要目視事項としてJSONへ記録する。テストはTypstの有無に依存しないよう
模擬してあり、GitHub Actionsでも成功する。

## 確認済み事例

### 素数の無限性

- 記事: `2015-08-28-01`
- 定義、命題、定理、ラベル参照、証明を自動補正した。
- Typst 0.15.1でA4・1ページを生成した。
- 定義1、命題2・3、定理4と参照番号を全ページ目視確認した。

### 代数学の基本定理2

- 記事: `2015-09-15-02`
- 事実3件、補題1件、定理1件、証明4件、数式番号1〜6、参考文献1件を保持した。
- 任意題名4件を元TeXとの完全一致によって本文から分離した。
- 逆数の絶対値にあった余分な中括弧を除去した。
- Typst 0.15.1でA4・2ページを生成し、全ページを目視確認した。
- 元PDFはローカルPopplerの旧日本語フォント対応不足があるため、TeX本文と元PDFの数式、
  番号、ページ構成を併用して比較した。

実原稿や変換結果はパッケージのテスト・例へコピーしていない。

## 直近のGitHub記録

- PR #2: `Typst変換器の安全なTylax補正を拡張`
  - https://github.com/DempaComm/DempaComm.github.io/pull/2
  - 変換器本体のコミット: `6150919`
  - マージコミット: `bfa8f71`
- PR #3: `Typst未導入環境でも補正器テストを安定化`
  - https://github.com/DempaComm/DempaComm.github.io/pull/3
  - テスト修正コミット: `721af2c`
  - マージコミット: `bd412fc`
- PR #3マージ後のGitHub Actions:
  - https://github.com/DempaComm/DempaComm.github.io/actions/runs/32473913627
  - `build` と `deploy` はともに成功した。

この記録は2026-08-21時点である。次の作業時にはGitHub上の現状を再確認する。

## 絶対に守る境界

- `papers/*` のTeX、PDF、BibTeX、BST、図版、`paper.json` を変換都合で変更しない。
- 変換は一時領域またはGit管理外の `_experiments/` で行う。
- Tylax生出力を上書きしない。
- 入力、生出力、補正版、JSON報告へ同じパスを使わない。
- 既存の補正版や報告を自動上書きしない。
- 意味が一意でない補正、境界欠落、重複ラベル、未解決参照、未知のLaTeX命令を成功扱いしない。
- 実原稿の文章を回帰テストへコピーせず、同じ構造を持つ人工的な最小例を作る。
- コンパイル成功を内容一致や公開承認とみなさない。
- `manual_review_required: true` と `publishable: false` を維持する。
- Typstの作業へSATySFi固有処理を混在させない。
- Tylaxの恒久フォークを前提にせず、まず補正器と `dempa-style.typ` を育てる。

## 次の対象

次の練習記事は「順序数の位相的重み」 (`2015-12-21-04`) である。元TeXは
`papers/2015-12-21-04/weghit_of_ordinal.tex` にあるが、読み取り専用として扱う。

最初の目的は、すぐ補正規則を増やすことではなく、次を分類することである。

1. `\label{1}` から `\label{4}` までの数字だけのラベルが、Tylaxと先頭英字を要求する
   現在の `_LABEL` 規則でどう扱われるか。
2. `\begin{proof}` 直後から本文が始まる証明を含め、Tylax出力が現在対応する四角終端付き
   `_Proof._` 形式になるか。
3. 入れ子数式のどこがTypst構文として失敗するか。
4. `\card`、`\al`、`\dpst` などの独自命令がどの形で残るか。
5. `\end{document}` より後ろのコメント用メモがTylax出力へ混入しないか。
6. 一意に補正できるものと、人間の意味判断が必要なものを分離できるか。

未知の構造が見つかったら、まず生出力とJSON停止理由を記録する。実記事だけに合う置換を直接
追加せず、人工的な最小再現テストを先に作る。

## 次の試験手順

リポジトリルートで、Git管理外の新しい空の出力先を使う。

```sh
python3 scripts/paper_tool.py typst-trial 2015-12-21-04 \
  --output _experiments/typst-ordinal-1 \
  --timeout 60
```

生出力が得られた場合だけ、別名の補正版と報告を作る。

```sh
PYTHONPATH=packages/dempa-typst-converter/src \
python3 -m dempa_typst_converter.cli \
  _experiments/typst-ordinal-1/2015-12-21-04/tylax.typ \
  --latex-source papers/2015-12-21-04/weghit_of_ordinal.tex \
  --output _experiments/typst-ordinal-1/2015-12-21-04/main.typ \
  --report _experiments/typst-ordinal-1/2015-12-21-04/correction-report.json
```

出力先が既に存在する場合は、上書きせず `typst-ordinal-2` など新しい名前を使う。補正器が
停止した場合は、その停止を無視してPDF生成へ進まない。

## 現在のローカルツール

2026-08-21に次を確認した。

- Python 3.14.6
- Typst 0.15.1
- Tylax 0.3.7: `/Users/yoshitoishiki/.cargo/bin/t2l`
- Pandoc 3.10.1

現在のシェルでは `~/.cargo/bin` がPATHに入っていない場合がある。ただし `typst-trial` は
既知の導入場所から `t2l` を探索する。直接実行する場合は絶対パスを使うかPATHを確認する。

## 変更後の検査

パッケージ単体の確認:

```sh
cd packages/dempa-typst-converter
python3 -m unittest discover -s tests -v
```

リポジトリ全体のコミット前確認:

```sh
cd ../..
python3 scripts/paper_tool.py check-all
```

2026-08-21時点ではパッケージ単体テスト27件、リポジトリ連携テスト3件、`check-all` 全5項目が
成功している。GitHub ActionsにTypstがない場合、実コンパイル連携テスト1件が意図どおり
スキップされるが、模擬した構文失敗・Typst不在の単体テストは実行される。

コミット、push、PR作成、Draft解除、マージは、利用者が明示的に依頼した場合だけ行う。

## 未完了事項

- 「順序数の位相的重み」のTylax生出力分類と安全停止確認。
- 数字ラベル、古い証明記法、入れ子数式、独自命令の人工的な最小回帰テスト。
- 診断位置を行・列付きで報告する機能。
- 証明終端記号がない原稿の安全な構造解析。
- 複数原稿で再現した補正だけを安定APIへ昇格する判断。
- Typst派生版を正式公開するための保護、履歴、再生成規則。

次の作業者は、まず「順序数の位相的重み」を無変更で隔離変換し、停止理由の分類結果を利用者へ
報告するところから始める。補正器の変更は、その後に利用者の指示を得て行う。
