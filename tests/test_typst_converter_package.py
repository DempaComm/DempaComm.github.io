from __future__ import annotations

import subprocess
import shutil
import sys
import tempfile
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

    @unittest.skipUnless(shutil.which("typst"), "Typst is not installed")
    def test_structured_output_compiles_with_bundled_style(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.typ"
            output = root / "main.typ"
            report = root / "report.json"
            pdf = root / "main.pdf"
            raw.write_text(
                """/* Begin prop */
<sample> 人工的な命題．
/* End prop */
_Proof._ 命題 @sample を参照する． #h(1fr) $square.stroked$
""",
                encoding="utf-8",
            )
            converted = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dempa_typst_converter.cli",
                    str(raw),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=PACKAGE,
                env={"PYTHONPATH": str(PACKAGE / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, converted.returncode, converted.stdout + converted.stderr)
            compiled = subprocess.run(
                ["typst", "compile", "--root", str(root), str(output), str(pdf)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
            self.assertTrue(pdf.is_file())


if __name__ == "__main__":
    unittest.main()
