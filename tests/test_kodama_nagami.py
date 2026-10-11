from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.features.kodama_nagami import (
    generate_kodama_nagami, read_data, validate_kodama_nagami,
)


class KodamaNagamiTest(unittest.TestCase):
    def test_preserves_printed_pages_correction_and_inference_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_kodama_nagami(None, root)
            body = (root / "kodama-nagami/correspondence/index.html").read_text()
            notes = (root / "kodama-nagami/notes/index.html").read_text()
            afterword = (root / "kodama-nagami/afterword/index.html").read_text()
            self.assertIn("原本340–341頁", body)
            self.assertIn("可算密度", body)
            self.assertIn("斉次", body)
            self.assertNotIn("齐次", body)
            self.assertIn("単一の収録先が未同定", notes)
            self.assertIn("刊年・誌名・巻頁を補わない", notes)
            afterword_text = re.sub(r"<[^>]+>", "", afterword)
            self.assertIn("Topology，第1巻（1966）", afterword_text)
            self.assertIn("Topology，第2巻（1968）", afterword_text)
            self.assertEqual(len(re.findall(r"^@\w+\{", (root / "kodama-nagami/kodama-nagami.bib").read_text(), re.M)), 282)

    def test_only_emits_public_guide_data_and_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_kodama_nagami(None, root)
            paths = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
            self.assertEqual(paths, {
                "kodama-nagami/index.html", "kodama-nagami/references/index.html",
                "kodama-nagami/correspondence/index.html", "kodama-nagami/afterword/index.html",
                "kodama-nagami/notes/index.html", "kodama-nagami/bibliography.css",
                "kodama-nagami/bibliography.js", "kodama-nagami/bibliography.json",
                "kodama-nagami/kodama-nagami.bib",
            })
            for path in root.rglob("*"):
                if path.is_file():
                    text = path.read_text()
                    self.assertNotIn("/Users/", text)
                    self.assertNotIn('href="sources/', text)
                    self.assertNotIn('href="evidence/', text)
                    self.assertNotRegex(text, r"スキャン|写真|画像|OCR|レンダリング|見開き")
            data = json.loads((root / "kodama-nagami/bibliography.json").read_text())
            self.assertEqual(len(data["matches"]), 351)
            for match in data["matches"]:
                self.assertNotIn("statement", match["book"])
                self.assertTrue(1 <= len(match["book"]["summary"]) <= 140)
            correspondence = (root / "kodama-nagami/correspondence/index.html").read_text()
            self.assertNotIn("<h4>本書の記述</h4>", correspondence)
            self.assertEqual(correspondence.count("<h4>本書の主張の要約</h4>"), 351)

    def test_rejects_book_passage_in_public_data(self):
        data = copy.deepcopy(read_data())
        data["matches"][0]["book"]["statement"] = "原文の記述を復活させない"
        with patch("dempa_site.features.kodama_nagami.read_data", return_value=data):
            with self.assertRaisesRegex(ValueError, "短い要約"):
                validate_kodama_nagami(None)

    def test_summaries_preserve_countable_tightness_in_book_terms(self):
        matches = read_data()["matches"]
        for number in ("47.20", "47.21", "47.22", "47.23"):
            match = next(m for m in matches if m["book"]["number"].startswith(number))
            with self.subTest(number=number):
                self.assertIn("可算密度", match["book"]["summary"])
                self.assertNotIn("可分", match["book"]["summary"])

    def test_rejects_unresolved_reference_in_provisional_adoption(self):
        data = copy.deepcopy(read_data())
        data["inferred"][0]["selected_record_ids"] = ["missing-record"]
        with patch("dempa_site.features.kodama_nagami.read_data", return_value=data):
            with self.assertRaisesRegex(ValueError, "推定表"):
                validate_kodama_nagami(None)


if __name__ == "__main__":
    unittest.main()
