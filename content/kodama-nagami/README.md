# 参考文献案内の入力

`bibliography.json`は278文献・351対応・19付記・あとがき10項目を収録する。`kodama-nagami.bib`は分冊・翻訳別の282項目を保つ。

本書の主張は`book-summaries.json`に独自の短い要約として保つ。公開JSONには`book.summary`を収録し、原文に近い`book.statement`は収録しない。元記録が変わったときはSHA-256の照合で再点検を求める。

調査チャットの元ファイルと取得日・SHA-256・加工範囲は`source-manifest.json`に記録している。元資料はGit管理外の`_experiments/kodama-nagami/source-snapshot/`に保つ。公開ページと配布データにはローカル資料のパスや取得・加工方法を載せず、原文の確認範囲と留保を保つ。

入力を更新するときは[案内の保守手順](../../docs/KODAMA_NAGAMI.md)に従う。書誌確認、個別対応、推定採用を区別し、原著の印刷頁番号を保つ。
