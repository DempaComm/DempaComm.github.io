# 原稿無改変の移行手順

## 基本方針

- 通常の移行では、TeX原稿、図版、BibTeXデータ、BSTなどをバイト単位でコピーする。
- 各ファイルの原本SHA-256と現在承認済みSHA-256を `paper.json` に分けて保存する。
- 明示的な書き換え指示がない限り、保護対象ファイルを編集しない。
- 指示によって書き換えた場合は、理由と変更前後のSHA-256を承認履歴に残す。
- 題名、分類、説明、元記事URLなど、サイト表示用の情報は `paper.json` に置く。
- 原稿名は公開日と同日内の公開順から `YYYY-MM-DD-NN` とする。
- 電波通信の既存タグは原表記のまま `tags` に保存し、追加検索語は `keywords` に分ける。
- `keywords.txt` は `paper.json` から自動生成し、手作業では編集しない。
- TeXエンジンは `paper.json` の `build.engine` に記録する。空欄または省略時は `platex` として処理する。

## 新しい原稿の取り込み

### PDFリンクのないブログ記事

電波通信の記事にPDFリンクがなく、本文をこのサイトへ複製しない場合は、記事種別
`ブログ本文のみ` として登録できる。この種別は `files` を空配列、
`build_enabled` を `false` とし、`original_url` を必須とする。個別ページ、総覧、
年別、タグ別には掲載されるが、PDF・TeXボタンの代わりに「電波通信で読む」を
主ボタンとして表示する。

```json
{
  "title": "PDFリンクのない記事",
  "published_at": "2017-01-01T12:00:00+09:00",
  "sequence": 1,
  "kind": "ブログ本文のみ",
  "summary": "電波通信で公開したブログ本文のみの記事です。",
  "original_url": "https://example.hatenablog.com/entry/2017/01/01/120000",
  "tags": ["数学"],
  "keywords": ["PDFリンクのない記事"],
  "build_enabled": false,
  "files": []
}
```

公開ファイルをコピーしないため個人情報検査は要求しない。サイト側へ保存されるのは
記事の題名、日時、タグ、検索語、説明、元記事URLのみで、ブログ本文そのものは保存しない。

TeXまたはPDFを取り込む前に、必ず個人情報検査を行う。

```sh
python3 scripts/paper_tool.py inspect-file /path/to/manuscript.tex
python3 scripts/paper_tool.py inspect-file /path/to/manuscript.pdf
```

TeXでは著者、メール、所属などの候補を報告する。PDFでは文字・メタデータの抽出を試み、全ページをPNG画像にする。フォント欠落などで文字が画像から消える可能性がある場合は検査不合格になる。自動検出には限界があるため、報告と原稿、PDFの全ページ画像を人間が確認する。確認後だけ `--privacy-reviewed` を指定できる。検査済みファイルと取り込み時のSHA-256が異なる場合は取り込みを拒否する。

検査で警告や描画失敗が出ても、別の手段ですべて確認して公開すると判断した場合は、理由を必須として強制取り込みできる。

```sh
python3 scripts/paper_tool.py import-pdf manuscript.pdf \
  --privacy-override "別のPDF閲覧環境で全ページと著者表示を確認済み"
```

検査自体を一度も実行していないファイルは強制取り込みできない。強制判断の理由、対象SHA-256、検査成否、記録日時は `paper.json` の `privacy_reviews` にファイル別で残る。

TeXファイル1本だけから、コンパイル成否に左右されない最低限の記事を作る場合は次を使う。

```sh
python3 scripts/paper_tool.py import-tex /path/to/manuscript.tex --privacy-reviewed
```

原稿はバイト単位で同一の `source.tex` として保存され、PDFのないソースのみの記事ページになる。題名は単純な `\title{...}` またはファイル名から、公開日時と同日内番号は実行時点から補う。詳しい指定方法と、一般的なAIに渡せる手順は `docs/MINIMAL_TEX_IMPORT.md` にある。

PDFファイル1本だけから最低限の記事を作る場合は次を使う。

```sh
python3 scripts/paper_tool.py import-pdf /path/to/manuscript.pdf --privacy-reviewed
```

PDFはバイト単位で同一の `published.pdf` として保存され、公開時には `main.pdf` として配置される。題名はPDFのファイル名から、公開日時と同日内番号は実行時点から補う。詳しい指定方法と、一般的なAIに渡せる手順は `docs/MINIMAL_PDF_IMPORT.md` にある。

複数ファイル、既存PDF、自動ビルド設定まで一度に登録する通常の取り込みでは、次の仕様JSONを使う。

まず、リポジトリ外に取り込み仕様JSONを作る。仕様例は `examples/paper-import.example.json` にある。

```sh
python3 scripts/paper_tool.py import-paper /path/to/import-spec.json --privacy-reviewed
```

通常取り込みでも、`files` のうち `public: true` である全TeX・PDFに対して、あらかじめ `inspect-file` を実行する必要がある。公開BibTeX、BST、図版なども取り込み前に一覧表示されるが、現在の自動検査対象はTeXとPDFである。検査済み指定はコマンドの `--privacy-reviewed` または仕様JSONの `privacy_reviewed: true` に書ける。

全対象を別環境で確認して強制する場合は、コマンドの `--privacy-override "理由"` または仕様JSONの `privacy_override` を使う。同じ理由でも、監査記録は対象ファイルごとに保存される。

この操作は次を行う。

1. 公開日時と同日内の順番から保存先 `papers/YYYY-MM-DD-NN/` を決める。
2. 指定ファイルをその保存先へコピーする。
3. コピー元とコピー先のSHA-256が一致することを確認する。
4. 原本SHA-256と現在承認済みSHA-256が同一の `paper.json` を作る。
5. 標準の `.latexmkrc` がなければ生成する。
6. `paper.json` から `keywords.txt` と `index.html` の原稿一覧を再生成する。

既存PDFを原稿と一緒に保存するだけの試験公開では、取り込み仕様の `build_enabled` を `false` にし、完成PDFを `published.pdf` として保護対象へ含める。この場合は原稿を自動コンパイルせず、保存されたPDFを公開時に `main.pdf` として配置する。`build_enabled` が `false` で `published.pdf` もない場合は、PDFリンクを出さず公開ソースへのリンクを主ボタンにする。

既存の保存先がある場合は上書きせず停止する。

取り込み仕様では `math_section` に数学記事総覧での主分類を、`build_engine` にTeXエンジンを指定できる。`math_section` が空欄または省略された原稿は総覧の「その他」に入り、`build_engine` が空欄または省略された場合は `platex` として処理する。明示的に指定できる `build_engine` は現在 `platex` のみ。

## 検証と監査

現在のファイルが承認済みハッシュと一致するか確認する。

```sh
python3 scripts/paper_tool.py verify
```

原本のままか、指示による変更が承認済みかを表示する。

```sh
python3 scripts/paper_tool.py audit
```

`original` は原本と同一、`approved-modified` は明示的な変更が記録済みであることを表す。ハッシュが承認値と一致しないファイルは、どちらの操作でもエラーになる。

## VS Codeで保護されたTeX・PDFを更新する

`paper.json` の `files` にあるTeX・PDFはSHA-256で保護されている。VS Codeで意図的に更新する場合は、本文を保存しただけでpushせず、個人情報の再検査と承認記録を作る。

以下では `2018-10-14-01` の `main.tex` を例にする。最初にリポジトリのルートへ移動し、ほかの未完了変更がないことを確認する。

```sh
cd /path/to/DempaComm.github.io
git pull --ff-only
git status
```

VS Codeで `papers/2018-10-14-01/main.tex` を編集して保存したら、変更後のファイルを検査する。

```sh
python3 scripts/paper_tool.py inspect-file papers/2018-10-14-01/main.tex
```

表示された検査報告を読み、著者名、実名、メール、所属、住所などを確認する。PDFの場合は、報告先に生成された全ページのPNG画像とPDFメタデータも確認する。

問題がなければ、変更理由、記事のslug、対象ファイルを指定して承認する。

```sh
python3 scripts/paper_tool.py approve-change 2018-10-14-01 \
  --reason "最新版へ差し替え" \
  --file main.tex \
  --privacy-reviewed
```

複数の保護ファイルを同時に変更した場合は、各TeX・PDFを個別に `inspect-file` したうえで、`--file` を繰り返す。

```sh
python3 scripts/paper_tool.py approve-change 2023-12-01-02 \
  --reason "原稿と文献データを最新版へ差し替え" \
  --file eveeve.tex \
  --file wef.bib \
  --privacy-reviewed
```

`approve-change` は原稿本文を書き換えない。変更後のSHA-256を現在の承認値として記録し、最初に取り込んだ原本SHA-256と、変更前後のSHA-256を履歴として保持する。公開TeX・PDFでは、変更後ファイルの個人情報検査記録も同時に更新する。BibTeX、BST、図版など、現在自動検査対象でない保護ファイルだけを変更した場合は `--privacy-reviewed` は不要である。

通常の検査を完了できないが、別の方法で全内容を確認して公開すると判断した場合だけ、理由付きの強制承認を使う。

```sh
python3 scripts/paper_tool.py approve-change 2018-10-14-01 \
  --reason "最新版へ差し替え" \
  --file main.tex \
  --privacy-override "別の閲覧環境で名義と全内容を確認済み"
```

`--privacy-override` でも、先に `inspect-file` を一度実行する必要がある。

承認後に、対象記事とサイト全体を検査する。

```sh
python3 scripts/paper_tool.py verify 2018-10-14-01
python3 scripts/paper_tool.py audit 2018-10-14-01
python3 scripts/paper_tool.py catalog --check
python3 scripts/migration_ledger.py check
python3 -m unittest discover -s tests
```

TeXのビルドも手元で確認する場合は、対象フォルダでGitHub Actionsと同じ形式のコマンドを実行する。

```sh
cd papers/2018-10-14-01
latexmk -pdfdvi -file-line-error -halt-on-error -interaction=nonstopmode main.tex
cd ../..
```

最後に差分を確認して、予定したファイルと `paper.json` だけをコミットする。

```sh
git status
git diff -- papers/2018-10-14-01/paper.json
git add papers/2018-10-14-01/main.tex papers/2018-10-14-01/paper.json
git commit -m "ウリゾーン原稿を更新"
git push origin main
```

ファイル名が `paper.json` の `files` に登録されていない場合、`approve-change` は停止する。これは既存ファイルの更新ではなく新しい公開ファイルの追加なので、個人情報検査後に `paper.json` へファイル情報とSHA-256を新規登録する必要がある。判断に迷う場合は、未登録ファイルを先にpushしない。

`verify` がSHA不一致で止まる場合は、未承認の変更が残っている。`paper.json` のSHAを手入力で上書きせず、意図した変更だけを `approve-change` で承認する。

## 記事一覧と公開物

`paper.json` から記事カードと各原稿の `keywords.txt` を再生成する。

```sh
python3 scripts/paper_tool.py catalog
```

一覧が最新かだけを確認する。

```sh
python3 scripts/paper_tool.py catalog --check
```

GitHub Actionsでは、公開前に `verify` と `catalog --check` を実行する。PDF生成後は次の操作で公開用ディレクトリを作る。

```sh
python3 scripts/paper_tool.py stage _site
python3 scripts/paper_tool.py check-links _site
```

トップページには新着3件と主要な入口だけを表示する。全原稿の検索欄、件数付きタグ索引、公開年別記事一覧は `archive/` に生成する。検索欄では、題名、説明、タグ、検索キーワードを横断検索でき、元タグと公開年による絞り込みもできる。タグごとの記事一覧は `tags/<タグ名>/` に公開年別で自動生成する。

公開時には `404.html`、`feed.xml`、`sitemap.xml`、`robots.txt` も生成する。`stage` とGitHub Actionsの `check-links` は、公開HTML内のローカルリンク切れを検出して公開を止める。

各原稿には `papers/<公開日-順番>/` 形式の個別ページを自動生成する。個別ページには原稿情報、公開ファイル、電波通信のタグ、検索キーワードをまとめ、トップページとタグ別ページの記事名からリンクする。

`paper.json` の `math_section` は数学記事総覧での主分類を表す。空欄または省略時は「その他」として扱う。公開時に `math/` へ分野別総覧の総合入口を生成し、`math/<分野>/` へ各分野の記事を公開年別・タグ付きで自動生成する。トップページと「数学」タグページから総合入口へ案内する。

旧形式の原稿名が `legacy_slugs` に登録されている場合、公開時には旧URLにも同じファイルを配置する。改名後も既存リンクは維持される。

新しい取り込みで生成される `paper.json` は `schema_version: 2` となり、公開TeX・PDFすべての検査記録を必須とする。GitHub Actionsの `verify` でも検査対象の不足とハッシュ不一致を検出する。既存の移行済み16原稿だけは `schema_version: 1` のまま維持され、免除対象のslugはツール内で固定されている。新規原稿に旧スキーマを指定して検査を回避することはできない。

したがって、検査済みの新しい `paper.json` を追加すれば、検索情報、記事一覧、PDF生成対象、Pagesへの配置へ自動的に反映される。
