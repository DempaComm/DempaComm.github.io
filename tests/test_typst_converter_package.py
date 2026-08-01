from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY / "packages" / "dempa-typst-converter"


class TypstConverterPackageTest(unittest.TestCase):
    def test_standalone_python_tests_pass(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=PACKAGE,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            msg=f"{completed.stdout}\n{completed.stderr}",
        )

    def test_public_package_documents_and_style_exist(self) -> None:
        required = (
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "docs/INSTALLATION.md",
            "docs/CONVERSION_WORKFLOW.md",
            "docs/ARCHITECTURE.md",
            "docs/PUBLISHING.md",
            "src/dempa_typst_converter/styles/dempa-style.typ",
        )
        self.assertEqual([], [path for path in required if not (PACKAGE / path).is_file()])


if __name__ == "__main__":
    unittest.main()
