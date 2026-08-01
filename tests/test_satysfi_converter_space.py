from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY / "packages" / "dempa-satysfi-converter"


class SatysfiConverterSpaceTest(unittest.TestCase):
    def test_converter_package_is_complete(self) -> None:
        required = (
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "docs/REQUIREMENTS.md",
            "docs/ARCHITECTURE.md",
            "docs/HANDOFF.md",
            "src/dempa_satysfi_converter/converter.py",
            "src/dempa_satysfi_converter/cli.py",
            "src/dempa_satysfi_converter/styles/dempa.satyh",
            "tests/test_converter.py",
            "examples/minimal/input.tex",
        )
        self.assertEqual([], [path for path in required if not (PACKAGE / path).is_file()])

    def test_standalone_converter_tests_pass(self) -> None:
        import os
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=PACKAGE,
            env={**os.environ, "PYTHONPATH": str(PACKAGE / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
