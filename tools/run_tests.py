#!/usr/bin/env python3
"""Run independent unittest modules concurrently with compact output."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestModuleResult:
    module: str
    returncode: int
    elapsed_seconds: float
    stdout: str
    stderr: str


def discovered_test_modules(repository: Path) -> tuple[str, ...]:
    return tuple(
        f"tests.{path.stem}" for path in sorted((repository / "tests").glob("test_*.py"))
    )


def run_test_module(
    module: str, repository: Path, python_executable: str
) -> TestModuleResult:
    started = time.monotonic()
    completed = subprocess.run(
        [python_executable, "-m", "unittest", module],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    return TestModuleResult(
        module=module,
        returncode=completed.returncode,
        elapsed_seconds=time.monotonic() - started,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_parallel_tests(
    repository: Path, *, workers: int = 4, python_executable: str = sys.executable
) -> tuple[TestModuleResult, ...]:
    modules = discovered_test_modules(repository)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        results = tuple(
            executor.map(
                lambda module: run_test_module(module, repository, python_executable),
                modules,
            )
        )
    return results


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--workers", type=int, default=4)
    return result


def main() -> int:
    arguments = parser().parse_args()
    repository = Path(__file__).resolve().parents[1]
    started = time.monotonic()
    results = run_parallel_tests(repository, workers=arguments.workers)
    failures = [result for result in results if result.returncode]
    if failures:
        for result in failures:
            print(f"FAIL {result.module} ({result.elapsed_seconds:.1f}秒)")
            if result.stdout.strip():
                print(result.stdout.rstrip())
            if result.stderr.strip():
                print(result.stderr.rstrip(), file=sys.stderr)
        print(f"TESTS FAILED {len(failures)}/{len(results)} modules", file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started
    print(f"TESTS OK {len(results)} modules ({elapsed:.1f}秒, workers={arguments.workers})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
