# サイト追加機能の実装規約

## 目的

検索、原稿関係図、HTML変換などの派生機能を、基本の記事ページやCLI本体から独立して
追加するための規約である。追加機能が失敗または無効でも、PDF、TeX、記事個別ページ、
総覧などの基本サイトを維持する。

読書経路、原稿の系譜、タグ関係図、探索ページ、定理等の索引はトップと各原稿から常時たどる
基本ナビゲーションである。この五つは `SITE_FEATURES` に `required=True` で登録する。
それぞれ別の一時領域で生成し、一つでも失敗した場合は公開全体を中止して以前のサイトを
保持する。これにより、機能固有の呼び出しをサイト生成本体へ直接書かず、リンク切れも
残さない。
LaTeXMLは外部コマンドと原稿ごとの互換性問題があるため、一括生成機能として通常公開には
登録せず `latexml-trial` で隔離実行する。自動検査と目視比較を通過した出力だけは
`publish-latexml` で原稿ごとの保護された公開ファイルに昇格できる。

実装は `dempa_site/features/` に置く。通常公開で使う機能の登録先は
`dempa_site/features/registry.py` の `SITE_FEATURES` 一か所だけとする。

## HTML閲覧用コピーの整形

`site/html_view.py` は `stage` のファイル配置時に、日本語の言語指定、本文検索の範囲、
数式・表のスクロール領域と、検索結果から移動するための見出しIDを公開用HTMLへ付ける。保存済みの `papers/*/html*/` や
TeX・PDFは書き換えず、MathMLの内部と本文テキストをそのまま保つ。DOM全体の
再シリアライズはせず、必要なタグと属性だけを編集する。

`paper.json` の保護ハッシュはリポジトリに保管したファイルの値であり、この整形後の
HTMLコピーの値ではない。整形後の公開HTMLは `tests/fixtures/site-baseline.json` で
別途検査する。変換版の「自動変換・未目視」という状態は変更しない。

全原稿の検索は題名・説明・タグ・キーワードを対象とし、HTMLを持たない記事も含む。
本文検索は主HTML版だけを対象とする。`data-pagefind-body` を原稿本文に付け、
著者・変換日を `data-pagefind-ignore` で除外する。検索結果には本文の `<mark>` だけを
許可して強調表示し、それ以外のHTMLを検索結果へ持ち込まない。

## 共通インターフェース

各機能は次の属性と二つのメソッドを持つ。

```python
class SiteFeature:
    name: str
    required: bool
    enabled: bool
    paper_slug: str

    def validate(self, catalog): ...
    def generate(self, catalog, output): ...
```

- `validate` は必要なメタデータや外部コマンドの前提を検査し、生成できない場合は例外を
  発生させる。ファイルは書き出さない。
- `generate` は渡された `output` 以下だけへ、完成した派生ファイルを書き出す。
- `catalog` の記事列、タグ分類、数学分類はすべて読み取り専用であり、機能から変更しない。
- `name` はログと結果記録で使う、短く安定した識別名である。
- `paper_slug` は原稿単位の変換で対象slugを記録する場合に使う。サイト全体の機能では
  空文字列にする。
- `required=False` の任意機能は失敗しても基本サイトと他の機能を公開できる。
- `required=True` の必須機能が失敗すると公開全体を中止し、以前の公開先を保持する。
- `enabled=False` の機能は検査も生成もせず、結果を `disabled` として記録する。

出力は機能ごとの一時領域で生成され、成功した場合だけサイトへ統合される。基本サイトや
先に成功した機能のファイルと同じパスを出力した機能は失敗扱いになる。途中ファイルは
公開されない。

## 小さな機能の作り方

単純な生成処理では、新しいクラスを作らず `FunctionFeature` を使う。

```python
from pathlib import Path

from dempa_site.features import FunctionFeature


def validate_example(catalog) -> None:
    if not catalog.selected:
        raise ValueError("記事がありません")


def generate_example(catalog, output: Path) -> None:
    target = output / "example" / "index.html"
    target.parent.mkdir(parents=True)
    target.write_text("example", encoding="utf-8")


EXAMPLE_FEATURE = FunctionFeature(
    name="example",
    generator=generate_example,
    validator=validate_example,
    required=False,
    enabled=True,
)
```

通常公開へ組み込むときだけ、`dempa_site/features/registry.py` でインポートして
`SITE_FEATURES` に加える。`scripts/paper_tool.py` や `site/staging.py` に機能固有の処理を
書かない。

複数の変換機能で同じライフサイクルや設定が必要になった場合は、`SiteFeature` を満たす
専用クラスへ共通化する。単独の小さな機能のために基底クラス階層を増やさない。

## 安全性と失敗時の方針

追加機能は原稿の派生物を作る場所であり、`papers/*` のTeX、PDF、BibTeX、BST、図版や
`paper.json` を書き換える場所ではない。入力は `SiteCatalog` から読み、生成先は必ず
渡された一時 `output` 以下に限定する。

外部変換器がない、特定原稿だけ変換できない、任意メタデータがない、といった理由で
PDF・TeXの通常公開まで止める機能は原則として `required=False` にする。サイトの安全性や
リンク整合性に不可欠な検査だけを `required=True` にする。

実行結果は次の状態を持つ。

- `generated`: 検査と生成に成功し、出力を統合した。
- `failed`: 検査または生成に失敗した。`phase` と `error` に段階と理由を記録する。
- `disabled`: 設定で無効化され、検査も生成もしていない。

通常の `stage` は登録機能がある場合、三状態の件数と機能ごとの結果を表示する。任意機能の
失敗は `WARN feature failed` として原稿slug、`validation` または `generation`、理由を
表示する。`check-all` は成功した個別コマンドの大量出力を隠すが、`FEATURES` とこの警告は
必ず表示する。

## 追加時の検査

最低限、次を単体テストする。

1. 正常時に予定した派生ファイルだけを生成する。
2. `validate` の失敗後に `generate` が呼ばれない。
3. 任意機能の失敗後も基本サイトと別の機能を生成できる。
4. 無効化後も基本サイトと別の機能を生成できる。
5. 基本サイトと同じパスを出力しても上書きできない。
6. 必須機能の失敗時に以前の公開先を保持する。

その後、通常の全検査を実行する。

```sh
python3 scripts/paper_tool.py check-all
```

公開物スナップショットが変わった場合は、新機能による意図した追加だけかを確認してから、
別の承認済み変更として基準を更新する。

## 閲覧点検での追加修正

- 補題・系も索引、原稿能力一覧、関係図の件数に含める。日本語と英語の見出しを認識し、
  絞り込み後は種別ごとの件数も更新する。
- 全原稿検索から本文検索へ検索語を渡す。検索用メタデータに現れる人名・用語だけを
  `catalog/search_terms.py` の別名辞書で補い、原稿・メタデータ原本は変更しない。
- 本文検索はPagefindの `sub_results` から該当する節へのリンクを作る。
  公開HTMLの `html-reader.js` が、検索語の強調と数式枠のフォーカスを担当する。
  強調表示はMathMLの内部を対象にしない。数式枠は横にあふれるものだけTab対象にし、
  リサイズとフォント読込み後に判定し直す。
- 関係図の描画は60件まで、文字の一覧は一致した全件を表示する。原稿名・タグでも検索できる。
  選択後は詳細見出しへフォーカスを移し、元の選択位置へ戻るボタンを用意する。
