from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dempa_site.catalog.metadata import collect_metadata
from dempa_site.features import statements as statements_feature
from dempa_site.features.statements import generate_statements, indexed_statements
from dempa_site.features.paper_capabilities import paper_capabilities
from dempa_site.manifests.model import Paper


class StatementIndexTest(unittest.TestCase):
    def prepared_catalog(self, root: Path):
        paper_dir = root / "papers" / "2026-07-28-01"
        html_dir = paper_dir / "html"
        html_dir.mkdir(parents=True)
        (html_dir / "index.html").write_text(
            """<!doctype html><html><body>
<div id="Thm1" class="ltx_theorem ltx_theorem_thm"><h6 class="ltx_title ltx_title_theorem"><span>定理 1</span> (名前付き).</h6><p>本文</p></div>
<div id="Def2" class="ltx_theorem ltx_theorem_df"><h6 class="ltx_title_theorem">定義 2.</h6></div>
<div id="Prop3" class="ltx_theorem ltx_theorem_prop"><h6 class="ltx_title_theorem">命題 3.</h6></div>
<div id="Ex4" class="ltx_theorem ltx_theorem_exam"><h6 class="ltx_title_theorem">例 4.</h6></div>
<div id="Lem5" class="ltx_theorem ltx_theorem_lem"><h6 class="ltx_title_theorem">補題 5.</h6></div>
</body></html>""",
            encoding="utf-8",
        )
        value = {
            "schema_version": 2,
            "slug": "2026-07-28-01",
            "migration_record_id": "fixture:statements",
            "legacy_slugs": [],
            "title": "索引試験",
            "published_at": "2026-07-28T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "索引の試験です。",
            "original_url": "",
            "order": 2026072801,
            "tags": ["数学"],
            "keywords": ["索引"],
            "build": {"enabled": False, "engine": ""},
            "files": [],
            "approved_changes": [],
            "privacy_reviews": [],
            "html_versions": [{
                "status": "approved",
                "generator": "LaTeXML",
                "generator_version": "0.8.8",
                "generated_at": "2026-07-28T12:00:00+09:00",
                "source_path": "main.tex",
                "source_sha256": "a" * 64,
                "path": "html/index.html",
                "label": "HTML版",
                "reviewed_at": "2026-07-28T12:00:00+09:00",
            }],
            "statements": [{
                "identifier": "Ex4",
                "kind": "counterexample",
                "title": "反例 4（手動補正）",
                "anchor": "#Ex4",
            }],
        }
        manifest_path = paper_dir / "paper.json"
        manifest_path.write_text(json.dumps(value), encoding="utf-8")
        paper = Paper.from_dict(value, manifest_path)
        return collect_metadata([(manifest_path, paper)])

    def test_extracts_four_kinds_and_applies_manual_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = self.prepared_catalog(Path(temporary))
            statements = indexed_statements(catalog)

        self.assertEqual(
            {"theorem", "definition", "proposition", "counterexample"},
            {item.kind for item in statements},
        )
        self.assertEqual(4, len(statements))
        counterexample = next(item for item in statements if item.kind == "counterexample")
        self.assertEqual("manual", counterexample.source)
        self.assertEqual("反例 4（手動補正）", counterexample.title)

    def test_generates_html_and_machine_readable_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = self.prepared_catalog(root)
            output = root / "_site"
            output.mkdir()
            generate_statements(catalog, output)
            rendered = (output / "statements" / "index.html").read_text(
                encoding="utf-8"
            )
            theorem_page = (
                output / "statements" / "kinds" / "theorem" / "index.html"
            ).read_text(encoding="utf-8")
            year_page = (
                output / "statements" / "years" / "2026" / "index.html"
            ).read_text(encoding="utf-8")
            data = json.loads(
                (output / "statements" / "statements.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn("定理・定義・命題・反例索引", rendered)
        self.assertIn('href="kinds/theorem/"', rendered)
        self.assertIn('href="years/2026/"', rendered)
        self.assertNotIn('class="statement-list"', rendered)
        self.assertIn("../../../papers/2026-07-28-01/html/index.html#Thm1", theorem_page)
        self.assertIn('id="statement-filter"', theorem_page)
        self.assertIn('data-kind="theorem"', theorem_page)
        self.assertIn('data-year="2026"', year_page)
        self.assertIn('src="../../../statements.js"', year_page)
        self.assertEqual(1, data["counts"]["counterexample"])

    def test_counterexample_tag_supplies_article_level_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = self.prepared_catalog(Path(temporary))
            manifest_path, original = catalog.selected[0]
            value = original.to_dict()
            value["tags"].append("反例")
            value["statements"] = []
            paper = Paper.from_dict(value, manifest_path)
            statements = indexed_statements(
                collect_metadata([(manifest_path, paper)])
            )

        fallback = next(item for item in statements if item.kind == "counterexample")
        self.assertEqual("tag", fallback.source)
        self.assertEqual("../papers/2026-07-28-01/html/index.html", fallback.href)

    def test_shared_capabilities_summarize_html_and_statements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = self.prepared_catalog(Path(temporary))
            capability = paper_capabilities(catalog)["2026-07-28-01"]

        self.assertEqual("html/index.html", capability.html_path)
        self.assertEqual(4, capability.statement_count)
        self.assertEqual(1, capability.statement_counts["theorem"])
        self.assertEqual(0, capability.correction_count)

    def test_statement_extraction_is_shared_within_one_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = self.prepared_catalog(Path(temporary))
            indexed_statements.cache_clear()
            with patch.object(
                statements_feature,
                "_automatic_statements",
                wraps=statements_feature._automatic_statements,
            ) as extraction:
                first = indexed_statements(catalog)
                second = indexed_statements(catalog)

        self.assertIs(first, second)
        self.assertEqual(1, extraction.call_count)


if __name__ == "__main__":
    unittest.main()
