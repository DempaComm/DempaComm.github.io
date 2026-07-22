# サイト追加機能の実装規約

## 目的

検索、原稿関係図、HTML変換などの派生機能を、基本の記事ページやCLI本体から独立して
追加するための規約である。追加機能が失敗または無効でも、PDF、TeX、記事個別ページ、
総覧などの基本サイトを維持する。

実装は `dempa_site/features/` に置く。通常公開で使う機能の登録先は
`dempa_site/features/registry.py` の `SITE_FEATURES` 一か所だけとする。

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
python3 -m unittest discover -s tests
python3 scripts/paper_tool.py verify
python3 scripts/paper_tool.py catalog --check
python3 scripts/migration_ledger.py check
python3 scripts/paper_tool.py stage _site
python3 scripts/paper_tool.py check-links _site
python3 scripts/site_snapshot.py check _site
```

公開物スナップショットが変わった場合は、新機能による意図した追加だけかを確認してから、
別の承認済み変更として基準を更新する。
