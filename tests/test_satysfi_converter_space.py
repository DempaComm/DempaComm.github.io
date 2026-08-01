from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY / "packages" / "dempa-satysfi-converter"


class SatysfiConverterSpaceTest(unittest.TestCase):
    def test_handoff_space_is_complete_but_contains_no_implementation(self) -> None:
        required = (
            "README.md",
            "docs/REQUIREMENTS.md",
            "docs/ARCHITECTURE.md",
            "docs/HANDOFF.md",
            "src/README.md",
            "styles/README.md",
            "tests/README.md",
            "examples/minimal/README.md",
        )
        self.assertEqual([], [path for path in required if not (PACKAGE / path).is_file()])
        implementation_files = [
            path
            for directory in ("src", "styles")
            for path in (PACKAGE / directory).rglob("*")
            if path.is_file() and path.name != "README.md"
        ]
        self.assertEqual([], implementation_files)


if __name__ == "__main__":
    unittest.main()
