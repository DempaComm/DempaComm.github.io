# Packages

将来、独立リポジトリまたは配布パッケージへ切り出せる自己完結したツールを置く。

- [`dempa-typst-converter`](dempa-typst-converter/README.md): Tylax出力の安全な補正と
  電波通信用Typstスタイルの実験パッケージ
- [`dempa-satysfi-converter`](dempa-satysfi-converter/README.md): 別スレッドでSATySFi変換器を
  開発するための予約領域と安全要件

サイト本体の必須処理はここへ依存させない。各パッケージは独自のREADME、ライセンス、
テスト、人工的な例を持ち、実原稿や非公開データを含めない。
