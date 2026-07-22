from __future__ import annotations

import unittest

from dempa_site.errors import PaperToolError
from dempa_site.importing.spec import ImportSpec


def valid_spec() -> dict:
    return {
        "title": "型付き取り込み",
        "published_at": "2026-07-22T12:00:00+09:00",
        "sequence": 1,
        "kind": "単純なTeX",
        "summary": "入力をコピー前に検査します。",
        "original_url": "",
        "tags": ["数学"],
        "keywords": ["型付き"],
        "source_dir": "/incoming",
        "files": [
            {
                "source": "source.tex",
                "path": "main.tex",
                "role": "manuscript",
            }
        ],
    }


class ImportSpecTest(unittest.TestCase):
    def test_valid_input_becomes_an_immutable_typed_spec(self) -> None:
        spec = ImportSpec.from_dict(valid_spec())

        self.assertEqual("2026-07-22-01", spec.slug)
        self.assertEqual("source.tex", spec.files[0].source)
        self.assertTrue(spec.files[0].public)
        self.assertTrue(spec.build_enabled)

    def test_file_entries_are_rejected_before_copying(self) -> None:
        value = valid_spec()
        value["files"] = ["source.tex"]

        with self.assertRaisesRegex(PaperToolError, r"spec\.files\[0\].*object"):
            ImportSpec.from_dict(value)

    def test_boolean_and_sequence_fields_are_not_silently_coerced(self) -> None:
        value = valid_spec()
        value["sequence"] = "1"
        with self.assertRaisesRegex(PaperToolError, "positive integer"):
            ImportSpec.from_dict(value)

        value = valid_spec()
        value["build_enabled"] = "false"
        with self.assertRaisesRegex(PaperToolError, "true or false"):
            ImportSpec.from_dict(value)

        value = valid_spec()
        value["build_root"] = ""
        with self.assertRaisesRegex(PaperToolError, "build_root"):
            ImportSpec.from_dict(value)


if __name__ == "__main__":
    unittest.main()
