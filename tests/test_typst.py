from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.conversion.typst import run_typst_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file
from dempa_site.manifests.model import Paper


class TypstTrialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        paper_dir = self.root / "papers" / "2026-07-28-01"
        paper_dir.mkdir(parents=True)
        self.source = paper_dir / "main.tex"
        self.original = (
            "\\documentclass{article}\n"
            "\\begin{document}日本語 $x^2$\\end{document}\n"
        )
        self.source.write_text(self.original, encoding="utf-8")
        digest = sha256_file(self.source)
        data = {
            "schema_version": 2,
            "slug": "2026-07-28-01",
            "migration_record_id": "fixture:typst",
            "legacy_slugs": [],
            "title": "Typst試験",
            "published_at": "2026-07-28T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "Typst試験",
            "original_url": "",
            "order": 2026072801,
            "tags": ["数学"],
            "keywords": ["Typst"],
            "build": {
                "enabled": True,
                "engine": "lualatex",
                "root": "main.tex",
            },
            "files": [
                {
                    "path": "main.tex",
                    "role": "manuscript",
                    "label": "TeX原稿",
                    "public": True,
                    "original_sha256": digest,
                    "sha256": digest,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [],
            "html_versions": [],
            "statements": [],
            "corrections": [],
        }
        manifest_path = paper_dir / "paper.json"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        self.paper = Paper.from_dict(data, manifest_path)
        self.papers = [(manifest_path, self.paper)]
        experiment_dir = self.root / "experiments"
        experiment_dir.mkdir()
        (experiment_dir / "typst-trial.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "papers": [
                        {
                            "slug": self.paper.slug,
                            "category": "単純なTeX",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_tools_is_a_clean_error(self) -> None:
        with patch(
            "dempa_site.conversion.typst._find_executable", return_value=None
        ):
            with self.assertRaisesRegex(PaperToolError, "Typst試験ツール"):
                run_typst_trial(
                    root=self.root,
                    papers=self.papers,
                    output=self.root / "trial",
                )

    def test_compares_two_converters_without_changing_source(self) -> None:
        def fake_run(command, *, cwd, timeout):
            if Path(command[0]).name in {"t2l", "pandoc"}:
                destination = Path(command[command.index("-o") + 1])
                destination.write_text(
                    "= Typst試験\n日本語の本文 $x^2$\n",
                    encoding="utf-8",
                )
            elif Path(command[0]).name == "typst":
                Path(command[-1]).write_bytes(b"%PDF-1.7\nfixture")
            return subprocess.CompletedProcess(
                command, 0, stdout="ok\n", stderr=""
            )

        def fake_which(name):
            return f"/tools/{'t2l' if name == 't2l' else name}"

        with patch(
            "dempa_site.conversion.typst._find_executable",
            side_effect=fake_which,
        ), patch(
            "dempa_site.conversion.typst._run_command",
            side_effect=fake_run,
        ):
            output = self.root / "trial"
            report = run_typst_trial(
                root=self.root,
                papers=self.papers,
                output=output,
            )

        self.assertEqual(self.original, self.source.read_text(encoding="utf-8"))
        self.assertFalse(report["publishable"])
        self.assertTrue(report["manual_review_required"])
        converters = report["results"][0]["converters"]
        self.assertEqual(["tylax", "pandoc"], [item["converter"] for item in converters])
        self.assertEqual(["generated", "generated"], [item["status"] for item in converters])
        for converter in ("tylax", "pandoc"):
            self.assertTrue((output / self.paper.slug / f"{converter}.typ").is_file())
            self.assertTrue((output / self.paper.slug / f"{converter}.pdf").is_file())
        self.assertTrue((output / "report.json").is_file())

    def test_refuses_to_overwrite_nonempty_output(self) -> None:
        output = self.root / "trial"
        output.mkdir()
        (output / "keep.txt").write_text("keep", encoding="utf-8")
        with patch(
            "dempa_site.conversion.typst._find_executable",
            side_effect=lambda name: f"/tools/{name}",
        ):
            with self.assertRaisesRegex(PaperToolError, "空ではありません"):
                run_typst_trial(
                    root=self.root,
                    papers=self.papers,
                    output=output,
                )


if __name__ == "__main__":
    unittest.main()
