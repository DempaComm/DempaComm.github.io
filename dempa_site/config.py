"""Stable site and TeX settings shared by command-line tools."""

from __future__ import annotations


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

DEFAULT_LATEXMKRC = """$latex = 'platex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$pdf_mode = 3;
"""
LATEXMKRC_BY_ENGINE = {"platex": DEFAULT_LATEXMKRC}
DEFAULT_BUILD_ENGINE = "platex"

