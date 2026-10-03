"""Regression tests for reuse of local LuaLaTeX build results."""

from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import build_lualatex


class LuaLaTeXBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "papers/example/原稿.tex"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("Synthetic TeX fixture", encoding="utf-8")
        self.output = self.root / "_experiments/lualatex-migration"
        self.output.mkdir(parents=True)
        self.report_path = self.output / "build-report.json"
        self.write_products(self.source)
        self.write_report([self.record(self.source)])

    def product(self, source, suffix):
        return source.parent / "build" / (source.stem + suffix)

    def write_products(self, source):
        self.product(source, ".pdf").parent.mkdir(exist_ok=True)
        self.product(source, ".pdf").write_bytes(b"Synthetic PDF fixture")
        self.product(source, ".synctex.gz").write_bytes(b"Synthetic SyncTeX fixture")

    def record(self, source):
        pdf = self.product(source, ".pdf")
        synctex = self.product(source, ".synctex.gz")
        return {
            "source": source.relative_to(self.root).as_posix(),
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
            "status": "passed",
            "pdf": pdf.relative_to(self.root).as_posix(),
            "pdf_sha256": sha256(pdf.read_bytes()).hexdigest(),
            "synctex": synctex.relative_to(self.root).as_posix(),
        }

    def write_report(self, records):
        self.report_path.write_text(json.dumps({"documents": records}), encoding="utf-8")

    def run_cli(self, *arguments, fail=False):
        def rebuild(source, *_args):
            self.write_products(source)
            record = self.record(source)
            if fail:
                record["status"] = "failed"
            return record

        with patch.object(build_lualatex, "ROOT", self.root), \
                patch("sys.argv", ["build_lualatex.py", *arguments]), \
                patch.object(build_lualatex.shutil, "which", return_value="/fake/latexmk"), \
                patch.object(build_lualatex, "build", side_effect=rebuild) as build, \
                redirect_stdout(io.StringIO()):
            result = build_lualatex.main()
        return result, build, json.loads(self.report_path.read_text())["documents"]

    def test_intact_success_is_reused(self):
        result, build, records = self.run_cli("--failed-only")
        self.assertEqual(0, result)
        build.assert_not_called()
        self.assertEqual("passed", records[0]["status"])

    def test_missing_or_empty_products_are_rebuilt(self):
        for suffix in (".pdf", ".synctex.gz"):
            for empty in (False, True):
                with self.subTest(suffix=suffix, empty=empty):
                    product = self.product(self.source, suffix)
                    if empty:
                        product.write_bytes(b"")
                    else:
                        product.unlink()
                    result, build, records = self.run_cli("--failed-only")
                    self.assertEqual(0, result)
                    build.assert_called_once()
                    self.assertEqual(self.source, build.call_args.args[0])
                    self.assertTrue(build.call_args.args[-1], "latexmk must be forced to regenerate outputs")
                    self.assertGreater(product.stat().st_size, 0)
                    self.assertEqual("passed", records[0]["status"])

    def test_changed_source_or_pdf_is_rebuilt(self):
        for changed in (self.source, self.product(self.source, ".pdf")):
            with self.subTest(path=changed):
                changed.write_bytes(b"Changed fixture")
                result, build, records = self.run_cli("--failed-only")
                self.assertEqual(0, result)
                build.assert_called_once()
                self.assertTrue(build.call_args.args[-1])
                self.assertEqual("passed", records[0]["status"])

    def test_failed_rebuild_replaces_old_success(self):
        self.product(self.source, ".pdf").unlink()
        result, build, records = self.run_cli("--failed-only", fail=True)
        self.assertEqual(1, result)
        build.assert_called_once()
        self.assertEqual("failed", records[0]["status"])

    def test_missing_or_failed_record_is_rebuilt(self):
        for records in ([], [{**self.record(self.source), "status": "failed"}]):
            with self.subTest(records=records):
                self.write_report(records)
                result, build, _ = self.run_cli("--failed-only")
                self.assertEqual(0, result)
                build.assert_called_once()

    def test_unselected_stale_result_is_not_reported_as_success(self):
        other = self.source.with_name("other.tex")
        other.write_text("Another synthetic fixture", encoding="utf-8")
        self.write_products(other)
        self.write_report([self.record(self.source), self.record(other)])
        self.product(other, ".synctex.gz").unlink()
        result, build, records = self.run_cli("--failed-only", str(self.source))
        self.assertEqual(1, result)
        build.assert_not_called()
        self.assertEqual(1, sum(record["status"] == "stale" for record in records))

    def test_deleted_source_is_removed_from_report(self):
        self.source.unlink()
        result, build, records = self.run_cli("--failed-only")
        self.assertEqual(0, result)
        build.assert_not_called()
        self.assertEqual([], records)

    def test_zero_exit_without_complete_products_is_failed(self):
        for suffix in (".pdf", ".synctex.gz"):
            for empty in (False, True):
                with self.subTest(suffix=suffix, empty=empty):
                    self.write_products(self.source)
                    product = self.product(self.source, suffix)
                    if empty:
                        product.write_bytes(b"")
                    else:
                        product.unlink()
                    process = Mock(returncode=0)
                    process.communicate.return_value = ("latexmk exited successfully", None)
                    with patch.object(build_lualatex, "ROOT", self.root), \
                            patch.object(build_lualatex.subprocess, "Popen", return_value=process) as popen:
                        record = build_lualatex.build(self.source, "/fake/latexmk", self.output, 10, False)
                    self.assertEqual("failed", record["status"])
                    self.assertIn("-g", popen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
