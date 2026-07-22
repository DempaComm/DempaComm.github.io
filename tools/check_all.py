"""Human-friendly orchestration of existing repository checks."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO

from dempa_site.errors import PaperToolError


@dataclass(frozen=True)
class CheckStep:
    """One existing command in the complete local verification sequence."""

    key: str
    label: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CheckResult:
    """Successful result retained for summaries and callers."""

    key: str
    label: str
    elapsed_seconds: float
    notices: tuple[str, ...] = ()


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
Clock = Callable[[], float]


def complete_check_steps(
    repository: Path,
    site_output: Path,
    python_executable: str = sys.executable,
) -> tuple[CheckStep, ...]:
    """Build the ordered, fail-fast checks used by ``check-all``."""
    paper_tool = repository / "scripts" / "paper_tool.py"
    ledger_tool = repository / "scripts" / "migration_ledger.py"
    snapshot_tool = repository / "scripts" / "site_snapshot.py"
    site = str(site_output)
    return (
        CheckStep(
            "tests",
            "自動テスト",
            (python_executable, "-m", "unittest", "discover", "-s", "tests"),
        ),
        CheckStep(
            "verify",
            "保護ファイルのSHA検査",
            (python_executable, str(paper_tool), "verify"),
        ),
        CheckStep(
            "audit",
            "原稿変更履歴の監査",
            (python_executable, str(paper_tool), "audit"),
        ),
        CheckStep(
            "catalog",
            "記事カタログ検査",
            (python_executable, str(paper_tool), "catalog", "--check"),
        ),
        CheckStep(
            "ledger",
            "移行台帳検査",
            (python_executable, str(ledger_tool), "check"),
        ),
        CheckStep(
            "stage",
            "公開サイト生成",
            (python_executable, str(paper_tool), "stage", site),
        ),
        CheckStep(
            "links",
            "公開サイトのリンク検査",
            (python_executable, str(paper_tool), "check-links", site),
        ),
        CheckStep(
            "snapshot",
            "承認済み公開物との比較",
            (python_executable, str(snapshot_tool), "check", site),
        ),
    )


def _show_failure_output(
    completed: subprocess.CompletedProcess[str], output: TextIO
) -> None:
    stdout = (completed.stdout or "").rstrip()
    stderr = (completed.stderr or "").rstrip()
    if stdout:
        print("--- 標準出力 ---", file=output)
        print(stdout, file=output)
    if stderr:
        print("--- エラー出力 ---", file=output)
        print(stderr, file=output)


def _success_notices(
    completed: subprocess.CompletedProcess[str],
) -> tuple[str, ...]:
    lines = "\n".join((completed.stdout or "", completed.stderr or "")).splitlines()
    return tuple(
        line for line in lines if line.startswith(("FEATURES ", "WARN "))
    )


def run_check_suite(
    steps: Sequence[CheckStep],
    repository: Path,
    *,
    run_command: CommandRunner = subprocess.run,
    clock: Clock = time.monotonic,
    output: TextIO | None = None,
) -> tuple[CheckResult, ...]:
    """Run checks in order, hiding successful noise and stopping on failure."""
    destination = output if output is not None else sys.stdout
    results: list[CheckResult] = []
    warning_count = 0
    total = len(steps)
    for number, step in enumerate(steps, start=1):
        print(f"CHECK {number}/{total}  {step.label}", file=destination, flush=True)
        started = clock()
        try:
            completed = run_command(
                step.command,
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            elapsed = clock() - started
            print(
                f"FAIL  {step.label} ({elapsed:.1f}秒)",
                file=destination,
                flush=True,
            )
            raise PaperToolError(
                f"一括確認を「{step.label}」で停止しました: {error}"
            ) from error
        elapsed = clock() - started
        if completed.returncode != 0:
            print(
                f"FAIL  {step.label} ({elapsed:.1f}秒)",
                file=destination,
                flush=True,
            )
            _show_failure_output(completed, destination)
            destination.flush()
            raise PaperToolError(
                f"一括確認を「{step.label}」で停止しました"
                f"（終了コード {completed.returncode}）"
            )
        notices = _success_notices(completed)
        warning_count += sum(line.startswith("WARN ") for line in notices)
        print(f"OK    {step.label} ({elapsed:.1f}秒)", file=destination)
        for notice in notices:
            print(notice, file=destination)
        results.append(CheckResult(step.key, step.label, elapsed, notices))

    warning_suffix = f"（警告{warning_count}件）" if warning_count else ""
    print(
        f"ALL OK  {total}項目の確認が完了しました{warning_suffix}",
        file=destination,
    )
    return tuple(results)
