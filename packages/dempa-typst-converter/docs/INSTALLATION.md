# 導入手順

## 必要なアプリ

- Python 3.11以降
- Typst 0.15以降
- RustとCargo
- Tylax 0.3.7以降（実行ファイル名は `t2l`）

PandocはTylaxとの比較試験を行う場合だけ必要であり、このパッケージ単体の必須依存ではない。

macOSでは次のように導入できる。

```sh
brew install typst rust
cargo install tylax
```

バージョンを確認する。

```sh
python3 --version
typst --version
t2l --version
```

Cargoが `t2l` を導入済みでもシェルから見つからない場合は、`$HOME/.cargo/bin` をPATHへ
追加する。このパッケージの開発環境を作る場合は、リポジトリのルートで次を実行する。

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

インストール確認は次で行う。

```sh
dempa-typst-correct --help
python3 -m unittest discover -s tests -v
```
