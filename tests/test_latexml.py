from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.conversion.latexml import (
    _effective_warning_lines,
    _normalize_cross_row_braces,
    _normalize_math_inside_text,
    _normalize_nocite_all,
    _normalize_quotient_relation,
    run_latexml_trial,
    svg_findings,
)
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper
from dempa_site.protection.privacy import privacy_findings


class LaTeXMLTrialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        paper_dir = self.root / "papers" / "2026-07-26-01"
        paper_dir.mkdir(parents=True)
        binding_dir = self.root / "experiments" / "latexml-bindings"
        binding_dir.mkdir(parents=True)
        self.binding = binding_dir / "article.cls.ltxml"
        self.binding.write_text("LoadClass('article');\n1;\n", encoding="utf-8")
        source = paper_dir / "main.tex"
        source.write_text("\\documentclass{article}\\begin{document}test\\end{document}", encoding="utf-8")
        bibliography = paper_dir / "references.bib"
        bibliography.write_text("@book{test,title={Test}}\n", encoding="utf-8")
        digest = sha256_file(source)
        data = {
            "schema_version": 1,
            "slug": "2026-07-26-01",
            "migration_record_id": "fixture:test",
            "legacy_slugs": [],
            "title": "LaTeXML試験",
            "published_at": "2026-07-26T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "試験",
            "original_url": "",
            "order": 2026072601,
            "tags": ["数学"],
            "keywords": ["LaTeXML"],
            "build": {"enabled": True, "engine": "lualatex", "root": "main.tex"},
            "files": [{
                "path": "main.tex",
                "role": "manuscript",
                "label": "TeX原稿",
                "public": True,
                "original_sha256": digest,
                "sha256": digest,
            }, {
                "path": "references.bib",
                "role": "bibliography",
                "label": "BibTeX",
                "public": True,
                "original_sha256": sha256_file(bibliography),
                "sha256": sha256_file(bibliography),
            }],
            "approved_changes": [],
            "privacy_reviews": [],
        }
        manifest_path = paper_dir / "paper.json"
        self.paper = Paper.from_dict(data, manifest_path)
        self.papers = [(manifest_path, self.paper)]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_converter_is_a_clean_error(self) -> None:
        with patch("dempa_site.conversion.latexml.shutil.which", return_value=None):
            with self.assertRaisesRegex(PaperToolError, "brew install latexml"):
                run_latexml_trial(
                    root=self.root,
                    papers=self.papers,
                    output=self.root / "trial",
                    requested_slugs=[self.paper.slug],
                )

    def test_temporary_math_normalization_and_html_label_context(self) -> None:
        source = r"\[\text{任意の $x\in A$ について}\]"
        normalized, count = _normalize_math_inside_text(source)

        self.assertEqual(1, count)
        self.assertEqual(
            r"\[\text{任意の }x\in A\text{ について}\]", normalized
        )
        aligned = r"\begin{align*}\{&x\\&y\}\end{align*}"
        normalized_align, brace_count = _normalize_cross_row_braces(aligned)
        self.assertEqual(2, brace_count)
        self.assertEqual(
            r"\begin{align*}\text{\{}&x\\&y\text{\}}\end{align*}",
            normalized_align,
        )
        normalized_quotient, quotient_count = _normalize_quotient_relation(
            r"$Z=W/\sim$"
        )
        self.assertEqual(1, quotient_count)
        self.assertEqual(r"$Z=W/\mathord{\sim}$", normalized_quotient)
        normalized_nocite, nocite_count = _normalize_nocite_all(
            r"\nocite{*}", [self.paper.source_path.parent / "references.bib"]
        )
        self.assertEqual(1, nocite_count)
        self.assertEqual(r"\nocite{test}", normalized_nocite)
        warnings, ignored = _effective_warning_lines(
            "Warning:expected:bibkeys Missing bibkeys local\n",
            '<a class="ltx_ref">resolved</a>',
            True,
        )
        self.assertEqual([], warnings)
        self.assertEqual(1, len(ignored))
        warnings, ignored = _effective_warning_lines(
            "Warning:expected:bibkeys Missing bibkeys missing\n",
            '<span class="ltx_missing_citation">missing</span>',
            True,
        )
        self.assertEqual(1, len(warnings))
        self.assertEqual([], ignored)
        self.assertEqual([], privacy_findings("論文の著者である", "html"))
        self.assertEqual(
            ["personal-information label found: 著者"],
            privacy_findings("<dt>著者</dt><dd>実名</dd>", "html"),
        )

    def test_success_writes_derived_html_and_review_report_only(self) -> None:
        conversion_commands = []

        def fake_run(command, **_kwargs):
            if "--VERSION" in command:
                return subprocess.CompletedProcess(command, 0, "latexmlc version 0.8.8\n", "")
            conversion_commands.append(command)
            destination = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--destination=")))
            log = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--log=")))
            destination.write_text(
                '<html><body><h1>LaTeXML試験</h1><div class="ltx_dates">(today)</div></body></html>',
                encoding="utf-8",
            )
            log.write_text("conversion log", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        output = self.root / "trial"
        with patch("dempa_site.conversion.latexml.shutil.which", return_value="/test/latexmlc"), patch(
            "dempa_site.conversion.latexml.subprocess.run", side_effect=fake_run
        ):
            report = run_latexml_trial(
                root=self.root,
                papers=self.papers,
                output=output,
                requested_slugs=[self.paper.slug],
            )

        self.assertEqual("generated", report["results"][0]["status"])
        self.assertTrue(report["manual_review_required"])
        self.assertFalse(report["publishable"])
        self.assertTrue(report["results"][0]["automatic_checks_passed"])
        self.assertTrue(report["results"][0]["comments_removed"])
        self.assertTrue(report["results"][0]["html_conversion_date_visible"])
        converted_html = (output / self.paper.slug / "index.html").read_text(encoding="utf-8")
        self.assertIn("HTML変換日：", converted_html)
        self.assertNotIn("(today)", converted_html)
        self.assertEqual(digest := sha256_file(self.paper.source_path.parent / "main.tex"), report["results"][0]["source_sha256"])
        self.assertEqual(digest, self.paper.files[0].sha256)
        self.assertEqual("experiments/latexml-bindings/article.cls.ltxml", report["binding_files"][0]["path"])
        self.assertIn("--nocomments", conversion_commands[0])
        self.assertIn("--svg", conversion_commands[0])
        self.assertEqual(0, report["results"][0]["inline_svg_count"])
        self.assertEqual([], report["results"][0]["unsafe_svg_findings"])
        self.assertTrue(any(value.startswith("--path=") for value in conversion_commands[0]))
        self.assertIn(
            f"--bibliography={(self.paper.source_path.parent / 'references.bib').resolve()}",
            conversion_commands[0],
        )
        self.assertEqual("references.bib", report["results"][0]["bibliographies"][0]["source"])
        self.assertTrue((output / self.paper.slug / "index.html").is_file())
        self.assertTrue((output / "report.json").is_file())
        self.assertEqual("\\documentclass{article}\\begin{document}test\\end{document}", (self.paper.source_path.parent / "main.tex").read_text(encoding="utf-8"))

    def test_inline_svg_is_counted_and_unsafe_content_is_rejected(self) -> None:
        safe = '<svg><path d="M0 0 L1 1"></path></svg>'
        self.assertEqual((1, []), svg_findings(safe))

        unsafe = (
            '<svg onload="run()"><script>run()</script>'
            '<image href="https://example.com/a.png"></image></svg>'
        )
        count, findings = svg_findings(unsafe)
        self.assertEqual(1, count)
        self.assertEqual(
            [
                "inline SVG 1: script element",
                "inline SVG 1: event handler",
                "inline SVG 1: external resource",
            ],
            findings,
        )

    def test_warning_blocks_automatic_checks(self) -> None:
        def fake_run(command, **_kwargs):
            if "--VERSION" in command:
                return subprocess.CompletedProcess(command, 0, "latexmlc version 0.8.8\n", "")
            destination = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--destination=")))
            log = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--log=")))
            destination.write_text("<html><body>LaTeXML試験</body></html>", encoding="utf-8")
            log.write_text("Warning:test A reviewable warning\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("dempa_site.conversion.latexml.shutil.which", return_value="/test/latexmlc"), patch(
            "dempa_site.conversion.latexml.subprocess.run", side_effect=fake_run
        ):
            report = run_latexml_trial(
                root=self.root,
                papers=self.papers,
                output=self.root / "warning-trial",
                requested_slugs=[self.paper.slug],
            )

        result = report["results"][0]
        self.assertEqual("generated-with-warnings", result["status"])
        self.assertFalse(result["automatic_checks_passed"])
        self.assertEqual(["LaTeXML警告が1件あります"], result["blocking_reasons"])

    def test_pdf_pages_are_rasterized_without_changing_the_tex_source(self) -> None:
        source = self.paper.source_path.parent / "main.tex"
        tex = (
            "\\documentclass{article}\\begin{document}LaTeXML試験"
            "\\includegraphics[width=12cm,page=2]{Figures.pdf}\\end{document}"
        )
        source.write_text(tex, encoding="utf-8")
        (source.parent / "Figures.pdf").write_bytes(b"%PDF-test")
        conversion_commands = []

        def fake_which(name):
            return f"/test/{name}"

        def fake_run(command, **_kwargs):
            if "--VERSION" in command:
                return subprocess.CompletedProcess(command, 0, "latexmlc version 0.8.8\n", "")
            if command[0] == "/test/pdftoppm":
                Path(command[-1] + ".png").write_bytes(b"png")
                return subprocess.CompletedProcess(command, 0, "", "")
            conversion_commands.append(command)
            destination = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--destination=")))
            log = Path(next(value.split("=", 1)[1] for value in command if value.startswith("--log=")))
            destination.write_text(
                '<html><body><h1>LaTeXML試験</h1><div class="ltx_dates">(today)</div>'
                '<img src="" class="ltx_graphics ltx_missing ltx_missing_image"></body></html>',
                encoding="utf-8",
            )
            log.write_text("conversion log", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        output = self.root / "graphics-trial"
        with patch(
            "dempa_site.conversion.latexml.shutil.which", side_effect=fake_which
        ), patch("dempa_site.conversion.latexml.subprocess.run", side_effect=fake_run):
            report = run_latexml_trial(
                root=self.root,
                papers=self.papers,
                output=output,
                requested_slugs=[self.paper.slug],
            )

        result = report["results"][0]
        self.assertTrue(result["automatic_checks_passed"])
        self.assertEqual(0, result["missing_graphics"])
        self.assertEqual(2, result["graphics"][0]["page"])
        self.assertIn("--nographicimages", conversion_commands[0])
        converted = (output / self.paper.slug / "index.html").read_text(encoding="utf-8")
        self.assertIn('src="figure-01-page-2.png"', converted)
        self.assertIn('style="width:12cm;max-width:100%;height:auto"', converted)
        self.assertNotIn("ltx_missing_image", converted)
        self.assertTrue((output / self.paper.slug / "figure-01-page-2.png").is_file())
        self.assertEqual(tex, source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
