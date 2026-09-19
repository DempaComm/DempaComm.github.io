#import "../../src/dempa_typst_converter/styles/dempa-style.typ": *

#show: dempa_article.with(
  title: "変換試験",
  author: "DempaComm",
  date: [2026-08-01],
)

この文書は公開パッケージ用に新規作成した最小例である。

#definition[
  自然数 $n$ が偶数であるとは、ある整数 $k$ により $n = 2 k$ と書けることをいう。
]

#proposition[
  偶数と偶数の和は偶数である。
] <even-sum>

#proof[
  命題 #ref(<even-sum>, supplement: none) について、$a = 2 m$、$b = 2 n$ と書けば、
  $a + b = 2 (m + n)$ である。
]

#theorem[
  この例では定義・命題・定理が同じ番号列を共有する。
]

#numbered-list-start()
#numbered-item[第一の条件。] <condition-one>
#numbered-item[第二の条件。] <condition-two>

条件 #ref(<condition-one>, supplement: none) と条件 #ref(<condition-two>, supplement: none) は、
固定番号ではなく項目要素への参照である。
