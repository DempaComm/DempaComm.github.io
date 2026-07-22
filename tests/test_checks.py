from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from dempa_site.errors import PaperToolError
from tools.check_all import CheckStep, complete_check_steps, run_check_suite


class CompleteCheckSuiteTest(unittest.TestCase):
    def test_complete_steps_cover_the_routine_publication_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            site = repository / "preview"
            steps = complete_check_steps(repository, site, "python-for-test")

        self.assertEqual(
            [
                "tests",
                "verify",
                "audit",
                "catalog",
                "ledger",
                "stage",
                "links",
                "snapshot",
            ],
            [step.key for step in steps],
        )
        self.assertEqual("python-for-test", steps[0].command[0])
        self.assertEqual(str(site), steps[-1].command[-1])

    def test_successful_checks_are_compact_and_keep_their_order(self) -> None:
        steps = (
            CheckStep("first", "最初の検査", ("first-command",)),
            CheckStep("second", "次の検査", ("second-command",)),
        )
        calls: list[tuple[str, ...]] = []

        def successful(command, **_kwargs):
            calls.append(command)
            output = (
                "very noisy output\n"
                "FEATURES generated=1 failed=1 disabled=0\n"
                "WARN feature failed: html [paper] (optional, generation): unavailable\n"
                if command == ("first-command",)
                else "more noisy output"
            )
            return subprocess.CompletedProcess(command, 0, output, "")

        times = iter((1.0, 1.25, 2.0, 2.5))
        output = io.StringIO()
        results = run_check_suite(
            steps,
            Path("/repository"),
            run_command=successful,
            clock=lambda: next(times),
            output=output,
        )

        self.assertEqual([("first-command",), ("second-command",)], calls)
        self.assertEqual(["first", "second"], [result.key for result in results])
        self.assertNotIn("very noisy output", output.getvalue())
        self.assertNotIn("more noisy output", output.getvalue())
        self.assertIn("FEATURES generated=1 failed=1 disabled=0", output.getvalue())
        self.assertIn("WARN feature failed: html", output.getvalue())
        self.assertIn("ALL OK  2項目の確認が完了しました（警告1件）", output.getvalue())

    def test_failed_check_shows_details_and_stops_following_checks(self) -> None:
        steps = (
            CheckStep("broken", "壊れた検査", ("broken-command",)),
            CheckStep("later", "後続検査", ("later-command",)),
        )
        calls: list[tuple[str, ...]] = []

        def failing(command, **_kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(
                command, 3, "failure context", "specific error"
            )

        times = iter((1.0, 1.5))
        output = io.StringIO()
        with self.assertRaisesRegex(PaperToolError, "壊れた検査"):
            run_check_suite(
                steps,
                Path("/repository"),
                run_command=failing,
                clock=lambda: next(times),
                output=output,
            )

        self.assertEqual([("broken-command",)], calls)
        self.assertIn("failure context", output.getvalue())
        self.assertIn("specific error", output.getvalue())
        self.assertNotIn("後続検査", output.getvalue())

    def test_command_start_failure_is_reported_as_a_check_error(self) -> None:
        step = CheckStep("missing", "利用不能な検査", ("missing-command",))

        def unavailable(_command, **_kwargs):
            raise FileNotFoundError("command not found")

        times = iter((1.0, 1.1))
        output = io.StringIO()
        with self.assertRaisesRegex(PaperToolError, "command not found"):
            run_check_suite(
                (step,),
                Path("/repository"),
                run_command=unavailable,
                clock=lambda: next(times),
                output=output,
            )

        self.assertIn("FAIL  利用不能な検査", output.getvalue())


if __name__ == "__main__":
    unittest.main()
