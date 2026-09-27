"""Reader-facing spelling aliases, derived without changing manuscript metadata."""

import re
import unicodedata


# Match only names or concepts already present in a paper's search metadata.
# Groups do not infer that a paper proves a theorem or covers a related topic.
SEARCH_ALIASES = (
    ("ブラウワー", "ブラウアー", "Brouwer"),
    ("ラドン", "Radon"),
    ("ニコディム", "Nikodym"),
    ("ワイエルストラス", "Weierstrass"),
    ("ストーン", "Stone"),
    ("バナッハ", "Banach"),
    ("クレイン", "Krein"),
    ("ミルマン", "Milman"),
    ("ハウスドルフ", "Hausdorff"),
    ("ウリゾーン", "Urysohn"),
    ("ティーツェ", "Tietze"),
    ("ボレル", "Borel"),
    ("ルベーグ", "Lebesgue"),
    ("カントール", "Cantor"),
    ("ベール", "Baire"),
    ("アスコリ", "Ascoli"),
    ("アルツェラ", "Arzela", "Arzelà"),
    ("チコノフ", "Tychonoff", "Tikhonov"),
    ("ホイットニー", "Whitney"),
    ("サード", "Sard"),
    ("クラトフスキー", "Kuratowski"),
    ("ツォルン", "Zorn"),
    ("ハーン", "Hahn"),
    ("不動点", "fixed point", "fixed-point"),
    ("領域不変性", "invariance of domain"),
    ("次元論", "dimension theory"),
)


def expanded_search_terms(terms: str) -> str:
    normalized = unicodedata.normalize("NFKC", terms).casefold()
    aliases = []
    for group in SEARCH_ALIASES:
        for term in group:
            candidate = unicodedata.normalize("NFKC", term).casefold()
            pattern = re.escape(candidate)
            if candidate.isascii():
                pattern = rf"(?<![a-z]){pattern}(?![a-z])"
            if re.search(pattern, normalized):
                aliases.extend(group)
                break
    return " ".join([terms, *dict.fromkeys(aliases)])
