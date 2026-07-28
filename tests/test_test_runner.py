from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.run_tests import discovered_test_modules


class ParallelTestRunnerTest(unittest.TestCase):
    def test_discovers_only_sorted_test_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_zeta.py").write_text("", encoding="utf-8")
            (tests / "helper.py").write_text("", encoding="utf-8")
            (tests / "test_alpha.py").write_text("", encoding="utf-8")

            modules = discovered_test_modules(root)

        self.assertEqual(("tests.test_alpha", "tests.test_zeta"), modules)


if __name__ == "__main__":
    unittest.main()
