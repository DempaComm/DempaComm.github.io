#!/usr/bin/env python3
"""Build every archived TeX root with its local LuaLaTeX/latexmk settings."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]


def is_nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def cached_success_is_current(source: Path, record: dict) -> bool:
    """Reuse success only while its source and build products still match."""
    pdf = source.parent / "build" / (source.stem + ".pdf")
    synctex = source.parent / "build" / (source.stem + ".synctex.gz")
    return (
        record.get("status") == "passed"
        and record.get("source_sha256") == sha256(source.read_bytes()).hexdigest()
        and is_nonempty_file(pdf)
        and is_nonempty_file(synctex)
        and record.get("pdf_sha256") == sha256(pdf.read_bytes()).hexdigest()
    )


def build(source: Path, executable: str, output: Path, timeout: int, force: bool) -> dict:
    started = time.monotonic()
    relative = source.relative_to(ROOT).as_posix()
    environment = os.environ.copy()
    environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
    environment.setdefault("TEXMFVAR", str(ROOT / "_experiments/lualatex-migration/texmf-var"))
    command = [executable, "-cd", "-lualatex", "-synctex=1", "-file-line-error",
               "-halt-on-error", "-interaction=nonstopmode", "-outdir=build", str(source)]
    pdf = source.parent / "build" / (source.stem + ".pdf")
    synctex = source.parent / "build" / (source.stem + ".synctex.gz")
    if force or not is_nonempty_file(pdf) or not is_nonempty_file(synctex):
        command.insert(1, "-g")
    process = subprocess.Popen(command, cwd=source.parent, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors="replace", start_new_session=True)
    timed_out = False
    try:
        transcript, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            transcript, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            transcript, _ = process.communicate()
    transcript_path = output / "logs" / Path(relative).with_suffix(".txt")
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(transcript, encoding="utf-8")
    log_path = source.parent / "build" / (source.stem + ".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else transcript
    warnings = list(dict.fromkeys(re.findall(
        r"(?m)^.*(?:Missing character:|LaTeX Warning:|Package [\w-]+ Warning:|Overfull \\[hv]box).*$", log)))
    missing_glyphs = [warning for warning in warnings if "Missing character:" in warning]
    pages = re.search(r"Output written on .*?\((\d+) p\s*a\s*g\s*e\s*s?", log, re.DOTALL)
    return {
        "source": relative,
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "status": "passed" if not timed_out and process.returncode == 0 and is_nonempty_file(pdf) and is_nonempty_file(synctex) and not missing_glyphs else "failed",
        "returncode": process.returncode,
        "timed_out": timed_out,
        "seconds": round(time.monotonic() - started, 2),
        "pdf": str(pdf.relative_to(ROOT)) if pdf.is_file() else None,
        "pdf_sha256": sha256(pdf.read_bytes()).hexdigest() if pdf.is_file() else None,
        "synctex": str(synctex.relative_to(ROOT)) if synctex.is_file() else None,
        "pages": int(pages[1]) if pages else None,
        "warnings": warnings,
        "missing_glyphs": missing_glyphs,
        "transcript": str(transcript_path.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--failed-only", action="store_true",
                        help="rebuild failed, changed, or missing-output documents")
    parser.add_argument("--force", action="store_true", help="force latexmk to rerun all processing rules")
    parser.add_argument("sources", nargs="*", type=Path)
    arguments = parser.parse_args()
    if arguments.jobs < 1 or arguments.timeout < 1:
        parser.error("jobs and timeout must be positive")
    executable = shutil.which("latexmk")
    if not executable and Path("/Library/TeX/texbin/latexmk").is_file():
        executable = "/Library/TeX/texbin/latexmk"
    if not executable:
        parser.error("latexmk が見つかりません。TeX LiveまたはMacTeXが必要です。")
    output = ROOT / "_experiments/lualatex-migration"
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "build-report.json"
    records = {}
    if (arguments.failed_only or arguments.sources) and report_path.is_file():
        records = {item["source"]: item for item in json.loads(report_path.read_text())["documents"]}
    sources = sorted(p for p in (ROOT / "papers").rglob("*.tex") if "build" not in p.relative_to(ROOT).parts)
    current_sources = {p.relative_to(ROOT).as_posix(): p for p in sources}
    records = {name: record for name, record in records.items() if name in current_sources}
    for name, record in records.items():
        if record.get("status") == "passed" and not cached_success_is_current(current_sources[name], record):
            record["status"] = "stale"
    if arguments.sources:
        chosen = {p.resolve() for p in arguments.sources}
        if not chosen.issubset(sources):
            parser.error("sources must be TeX files inside this repository's papers folder")
        sources = [p for p in sources if p in chosen]
    if arguments.failed_only:
        sources = [p for p in sources
                   if records.get(p.relative_to(ROOT).as_posix(), {}).get("status") != "passed"]

    def save() -> None:
        data = {"generated_at": datetime.now().astimezone().isoformat(),
                "documents": [records[key] for key in sorted(records)]}
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(report_path)

    with ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
        # Invalid cached outputs must be regenerated even if latexmk's own
        # dependency database still considers them up to date.
        pending = [pool.submit(build, source, executable, output, arguments.timeout,
                               arguments.force or arguments.failed_only
                               or records.get(source.relative_to(ROOT).as_posix(), {}).get("status") == "stale")
                   for source in sources]
        for number, future in enumerate(as_completed(pending), 1):
            result = future.result()
            records[result["source"]] = result
            save()
            print(f"{number}/{len(sources)} {result['status'].upper()} {result['source']}", flush=True)
    save()
    failures = [item for item in records.values() if item["status"] != "passed"]
    print(f"LuaLaTeX: {len(records) - len(failures)}/{len(records)} passed; report: {report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
