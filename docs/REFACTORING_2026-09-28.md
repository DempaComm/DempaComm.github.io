# 2026-09-28 表示と機能を維持する内部整理

開始時点は `62a9349`。従来の第0〜10段階で作った原稿保護、型付きカタログ、
隔離生成、公開先の一括置換を維持し、機能追加で処理が集中した箇所を整理した。

## 現在の責務

| 対象 | 編集する場所 | 境界 |
| --- | --- | --- |
| CLI入口 | `scripts/paper_tool.py`、`dempa_site/cli.py` | 引数解析とエラー表示。コマンド名・引数・終了コードを維持する |
| CLI処理 | `dempa_site/commands/` | 検査、カタログ、変換、原稿編集、取り込み、保守に分ける。対象リポジトリは `CommandContext` で渡す |
| ローカル管理 | `dempa_site/admin/` | `service.py` は操作と復旧、`views.py` は画面、`server.py` はHTTP受付・CSRF・操作の直列化 |
| カタログ書き出し | `dempa_site/catalog/writing.py` | CLIと管理画面で共通の `index.html`・`keywords.txt` 生成 |
| ページ共通部分 | `dempa_site/site/layout.py` | 共通ヘッダー・フッター。HTML断片は呼び出し側でエスケープする |
| 基本アセット | `dempa_site/site/assets.py` | ソースと公開URLの対応、CSSの結合順序を一箇所で管理する |
| CSS | `assets/styles/` | 番号順の6ファイルを既定の順序で結合する。生成先は従来の `_site/styles.css` |
| 全文検索 | `full-text-search.js`、`site/search_engine.js`、`site/search_results.js` | 操作・履歴、再試行可能な索引読込み、許可した抜粋・MathMLの描画を分離する |
| 原稿関係図 | `dempa_site/features/graph_*.js`、`relation_graph.js` | 計算モデル、URL設定、DOM部品、描画、詳細表示、操作・履歴を分ける |
| 日付・ランダム記事 | `dempa_site/site/discovery.js` | Python文字列への埋め込みを解消。生成するスクリプトは従来と同じ |

`dempa_site/local_admin.py` は既存の呼び出し元のための入口として残す。
変換コマンドの呼び出し側は `commands/conversion.py` に移したが、LaTeXMLの補正・検査・
公開判定と、独立したTypst・SATySFiパッケージの境界は維持する。

## CSSと公開ファイルの扱い

ルートの `styles.css` はソースとして使わない。`assets/styles/` を編集し、通常の
`stage` で公開先の `styles.css` を生成する。CSSのセレクター、詳細度、適用順序を
保ったまま抽出したため、今回の生成CSSは開始時点とバイト単位で一致する。
結合順序は `site/assets.py` の `STYLE_PARTS` で明示し、必要なファイルが欠ければ生成を停止する。

関係図のアセットは引き続き機能自身の `GRAPH_ASSETS` で管理し、機能専用の隔離領域で
生成する。基本サイト側へ関係図固有の依存を持ち込まない。

今回許容する公開差分は次の9パスだけである。

- 変更: `graph/graph.js`、`full-text-search.js`。
- 追加: `graph/graph-dom.js`、`graph/graph-state.js`、`graph/graph-view.js`、
  `graph/graph-inspector.js`、`search-engine.js`、`search-results.js`。
- 変更: `search/index.html` の全文検索スクリプトに `type="module"` を付ける。

ほかのHTML、原稿、CSS、関係図モデルとデータ、検索データ、画像、URLは従来のままとする。
公開物の比較基準は、上記の差分を個別に確認してから更新する。

## 検査

通常の最終検査は引き続き以下のとおり。

```sh
node --version
python3 scripts/paper_tool.py check-all
```

Node.jsをPATHへ入れると、関係図の計算・URLの往復、公開先のモジュール依存、
JavaScriptの構文も検査する。CIではNode.jsの存在を明示的に確認してからテストする。
CLIを分割したため、PDFキャッシュの判定対象にも新しいCLI実装のパスを追加した。

承認済み公開物との比較だけを後回しにする事前検査は `preflight_check_steps` に集約した。
CLIと管理画面のいずれも、原稿の承認、公開差分の確認、失敗時の停止・復旧を維持する。

ブラウザー検査は `tools/browser_check.cjs` にある。Playwright 1.62.1を開発用に用意し、
生成済みサイトをlocalhostで配信して使う。`node_modules` が別の場所にある場合は
`NODE_PATH` を指定する。`BROWSER_EXECUTABLE` で既存Chromeの実行ファイルも指定できる。
この依存は公開サイトへ含めない。

```sh
python3 -m http.server 8773 --bind 127.0.0.1 --directory _site
# 別ターミナルで実行。比較元は変更前サイトで同じコマンドを実行して保存する。
node tools/browser_check.cjs http://127.0.0.1:8773 /tmp/dempa-after /tmp/dempa-before
```

幅1280・390・320pxで、主要ページと検索・関係図の状態を撮影する。
検索の追加表示・履歴・解除、カタカナ語の本文検索と強調表示、処理中の検索解除、
定理索引、関係図のキーボード選択・拡大・履歴・周辺図・該当なしからの解除を確認する。
日付、ランダム選択、動き、外部フォントをテスト内で固定する。
画像は同じブラウザー・OSの保存画像と比較し、異なる環境の画像を自動承認しない。
関係図はSVGの内容・座標・画面寸法も完全一致させる。この条件を満たす場合に限り、
ブラウザーの合成処理で生じる最大1/255の色の丸めを許容する。それ以上の色差や
位置・要素の差は失敗扱いにする。
ブラウザーのバージョン、操作結果、エラーは出力先の `report.json` に記録する。

原稿保護のハッシュ比較、公開ファイルの比較、CLIヘルプの比較、ブラウザー検査を
実施した結果は、この文書の末尾に記録する。公開やGit操作は別途の依頼に従う。

## 検証記録

- Node.jsをPATHへ入れた `check-all`: 5項目すべて成功。自動テスト34モジュール、
  移行台帳、サイト生成・原稿保護・リンク、Pagefind索引、公開物比較を確認した。
- 保護対象: Git管理されている `papers/` 以下1,443ファイルのSHA-256が開始時点と一致。
- 公開物: 差分は上記9パスのみ。CSS、原稿HTMLの本文・MathML、関係図のデータと計算モデルは一致。
  比較基準は確認した差分だけ更新し、1,978ファイル・生成PDF8件の存在確認を通過した。
- CLI: トップレベルと全サブコマンドを合わせた25種類のヘルプが開始時点と一致。
- 管理画面: HTTP受付7関数と画面生成9関数は、移動前後で関数本体の構文木が一致。
  既存の承認・復旧・確認後の差分変更拒否テストも成功した。
- ブラウザー: Chrome 153.0.8010.54、幅1280・390・320pxで42画面、12組の操作を確認。
  最終実行の42画像はすべてバイト単位で一致し、SVG状態も一致。実行時エラーは0件。
  外部フォントを止めた同一環境での比較であり、別OS・別ブラウザーの見え方の検証ではない。
- `git diff --check`: 成功。
