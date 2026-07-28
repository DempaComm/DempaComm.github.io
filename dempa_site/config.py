"""Stable site and TeX settings shared by command-line tools."""

from __future__ import annotations

from dataclasses import dataclass


SITE_TITLE_TOP = "数識電収"
SITE_TITLE_FORMAL = "数学識電脳界溢出部位封神蔵収"
SITE_TITLE_ATTRIBUTE = "私と放電"
SITE_URL = "https://dempacomm.github.io"
HOME_PAPER_LIMIT = 3

START_MARKER = "<!-- GENERATED:PAPERS:START -->"
END_MARKER = "<!-- GENERATED:PAPERS:END -->"
BLOG_ONLY_KIND = "ブログ本文のみ"

MATH_SECTIONS = (
    "代数・組合せ",
    "位相・距離・幾何",
    "解析・測度・確率",
    "その他",
)
MATH_SECTION_DETAILS = {
    "代数・組合せ": {
        "slug": "algebra-combinatorics",
        "description": "代数、数論、有限体、組合せ論などの記事をまとめています。",
    },
    "位相・距離・幾何": {
        "slug": "topology-geometry",
        "description": "位相空間、距離空間、幾何、代数的トポロジーなどの記事をまとめています。",
    },
    "解析・測度・確率": {
        "slug": "analysis-probability",
        "description": "解析、複素解析、測度論、確率論などの記事をまとめています。",
    },
    "その他": {
        "slug": "other",
        "description": "上の三分野に収まらない数学記事をまとめています。",
    },
}
VALID_MATH_SECTIONS = frozenset(("", *MATH_SECTIONS))

# Non-exclusive topic portals derived from the original Hatena Blog tags.
# Add or adjust a portal here; paper manifests do not need another field.


@dataclass(frozen=True)
class MathTopic:
    slug: str
    title: str
    section: str
    description: str
    tags: tuple[str, ...]


MATH_TOPICS = (
    MathTopic(
        "separation-compactness", "分離・コンパクト性", "位相・距離・幾何",
        "分離公理、コンパクト性、パラコンパクト性などをたどります。",
        ("正規空間", "ウリゾーン", "コンパクトネス", "パラコンパクトネス", "固有写像", "局所コンパクト"),
    ),
    MathTopic(
        "metric-metrization", "距離空間・距離化", "位相・距離・幾何",
        "距離空間、距離化可能性、完全正則性に関する原稿です。",
        ("距離空間", "距離化可能定理", "完全正則空間"),
    ),
    MathTopic(
        "dimension-manifold-embedding", "次元・多様体・埋め込み", "位相・距離・幾何",
        "次元論、多様体、埋め込みに関する原稿をまとめます。",
        ("次元論", "多様体論", "サードの定理"),
    ),
    MathTopic(
        "algebraic-topology", "代数的トポロジー", "位相・距離・幾何",
        "代数的な道具で位相空間を調べる原稿です。", ("代数的トポロジー",),
    ),
    MathTopic(
        "counterexamples-set-theoretic-topology", "反例・集合論的位相", "位相・距離・幾何",
        "反例、可算性、実数集合や集合論に関係する位相の原稿です。",
        ("反例", "可算性", "実数に関連する集合論や位相", "集合論", "順序数"),
    ),
    MathTopic(
        "measure-probability", "測度・確率", "解析・測度・確率",
        "測度論と確率論を中心にたどります。", ("測度論", "確率論"),
    ),
    MathTopic(
        "functional-linear", "関数解析・線形空間", "解析・測度・確率",
        "関数解析と線形空間に関する原稿です。", ("関数解析", "線形空間"),
    ),
    MathTopic(
        "complex-analysis", "複素解析", "解析・測度・確率",
        "複素解析に関する原稿をまとめます。", ("複素解析",),
    ),
    MathTopic(
        "fixed-points", "不動点", "解析・測度・確率",
        "不動点定理とその周辺の原稿です。", ("不動点定理",),
    ),
)

PLATEX_LATEXMKRC = """$latex = 'platex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$pdf_mode = 3;
"""
UPLATEX_LATEXMKRC = """$latex = 'uplatex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$pdf_mode = 3;
"""
PDFLATEX_LATEXMKRC = """$pdflatex = 'pdflatex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$pdf_mode = 1;
"""
LUALATEX_LATEXMKRC = """$lualatex = 'lualatex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$pdf_mode = 4;
"""
XELATEX_LATEXMKRC = """$xelatex = 'xelatex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$pdf_mode = 5;
"""
LATEXMKRC_BY_ENGINE = {
    "platex": PLATEX_LATEXMKRC,
    "uplatex": UPLATEX_LATEXMKRC,
    "pdflatex": PDFLATEX_LATEXMKRC,
    "lualatex": LUALATEX_LATEXMKRC,
    "xelatex": XELATEX_LATEXMKRC,
}
LATEXMK_ARGS_BY_ENGINE = {
    "platex": "-pdfdvi",
    "uplatex": "-pdfdvi",
    "pdflatex": "-pdf",
    "lualatex": "-lualatex",
    "xelatex": "-xelatex",
}
DEFAULT_LATEXMKRC = PLATEX_LATEXMKRC
DEFAULT_BUILD_ENGINE = "platex"

LEGACY_PRIVACY_EXEMPT_SLUGS = frozenset(
    {
        "2015-08-28-01",
        "2015-09-01-01",
        "2016-01-09-01",
        "2017-08-01-01",
        "2018-03-29-01",
        "2018-10-14-01",
        "2019-11-29-01",
        "2020-01-30-01",
        "2021-01-28-01",
        "2022-01-03-01",
        "2023-06-20-01",
        "2024-01-03-01",
        "2024-01-08-01",
        "2024-01-13-01",
        "2025-12-28-01",
        "2026-04-21-01",
    }
)
