from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.config import (
    DEFAULT_BUILD_ENGINE,
    LATEXMKRC_BY_ENGINE,
    MATH_SECTIONS,
    MATH_SECTION_DETAILS,
    VALID_MATH_SECTIONS,
)
from dempa_site.dates import local_now_isoformat, parse_iso_datetime, utc_now_seconds
from dempa_site.errors import DempaSiteError, PaperToolError
from dempa_site.files import (
    json_text,
    normalize_nfc,
    normalize_nfkc_casefold,
    read_json,
    sha256_file,
    sha256_text,
    write_json,
)
from dempa_site.paths import (
    RepositoryPaths,
    is_safe_relative_path,
    safe_relative_path,
)


class SharedFoundationTest(unittest.TestCase):
    def test_repository_paths_honor_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"TEST_REPO_ROOT": temporary}):
                paths = RepositoryPaths.from_environment(
                    "TEST_REPO_ROOT", __file__
                )
            self.assertEqual(Path(temporary).resolve(), paths.root)
            self.assertEqual(paths.root / "papers", paths.papers)
            self.assertEqual(paths.root / "index.html", paths.index)
            self.assertEqual(paths.root / ".privacy-review", paths.privacy_review)

    def test_safe_relative_path_accepts_portable_japanese_path(self) -> None:
        value = "図版/上半平面.png"
        self.assertEqual(Path(value), safe_relative_path(value))
        self.assertTrue(is_safe_relative_path(value))

    def test_safe_relative_path_rejects_empty_absolute_and_parent_paths(self) -> None:
        for value in ("", "/tmp/manuscript.tex", "../secret.tex", "a/../../b"):
            with self.subTest(value=value):
                with self.assertRaises(DempaSiteError):
                    safe_relative_path(value)
                self.assertFalse(is_safe_relative_path(value))
        with self.assertRaises(PaperToolError):
            safe_relative_path("../secret.tex", PaperToolError)

    def test_hash_helpers_match_known_sha256(self) -> None:
        expected = (
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.bin"
            path.write_bytes(b"abc")
            self.assertEqual(expected, sha256_file(path))
        self.assertEqual(expected, sha256_text("abc"))

    def test_json_helpers_keep_utf8_format_and_round_trip(self) -> None:
        value = {"title": "数識電収", "items": [1, 2]}
        rendered = json_text(value)
        self.assertIn('"title": "数識電収"', rendered)
        self.assertTrue(rendered.endswith("\n"))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.json"
            write_json(path, value)
            self.assertEqual(rendered, path.read_text(encoding="utf-8"))
            self.assertEqual(value, read_json(path))

    def test_unicode_helpers_normalize_paths_and_search_text(self) -> None:
        self.assertEqual("ウリゾーン.tex", normalize_nfc("ウリゾーン.tex"))
        self.assertEqual("数学abc", normalize_nfkc_casefold("数学ＡＢＣ"))

    def test_date_helpers_preserve_offsets_and_return_second_precision(self) -> None:
        parsed = parse_iso_datetime("2026-07-22T12:34:56+09:00")
        self.assertEqual(9 * 60 * 60, int(parsed.utcoffset().total_seconds()))
        self.assertEqual(0, utc_now_seconds().microsecond)
        generated = parse_iso_datetime(local_now_isoformat())
        self.assertIsNotNone(generated.tzinfo)
        self.assertEqual(0, generated.microsecond)

    def test_math_and_tex_settings_are_internally_consistent(self) -> None:
        self.assertEqual(set(MATH_SECTIONS), set(MATH_SECTION_DETAILS))
        self.assertEqual({"", *MATH_SECTIONS}, set(VALID_MATH_SECTIONS))
        self.assertIn(DEFAULT_BUILD_ENGINE, LATEXMKRC_BY_ENGINE)
        self.assertIn("platex", LATEXMKRC_BY_ENGINE[DEFAULT_BUILD_ENGINE])


if __name__ == "__main__":
    unittest.main()
