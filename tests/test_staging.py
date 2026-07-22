from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dempa_site.catalog.metadata import collect_metadata, rendered_keywords
from dempa_site.errors import PaperToolError
from dempa_site.files import sha256_file, write_json
from dempa_site.manifests.model import Paper
from dempa_site.paths import RepositoryPaths
from dempa_site.site.links import local_link_errors
from dempa_site.site.rendering import rendered_home_page
from dempa_site.site.staging import (
    StageContext,
    StageFeature,
    check_generated_links,
    copy_public_files,
    generate_discovery_files,
    generate_static_pages,
    stage_site,
    validate_stage_sources,
)


class StagingPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paths = RepositoryPaths(self.root)
        paper_dir = self.root / "papers" / "2026-07-22-01"
        paper_dir.mkdir(parents=True)
        source = paper_dir / "source.tex"
        source.write_bytes(b"\\documentclass{article}\n")
        digest = sha256_file(source)
        manifest_data = {
            "schema_version": 1,
            "slug": "2026-07-22-01",
            "migration_record_id": "fixture:0000000000000001",
            "legacy_slugs": [],
            "title": "公開処理の試験原稿",
            "published_at": "2026-07-22T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "公開処理を段階別に検査する原稿です。",
            "original_url": "",
            "order": 2026072201,
            "tags": ["数学", "試験"],
            "keywords": ["公開処理"],
            "build": {"enabled": False, "engine": "", "root": None},
            "files": [
                {
                    "path": "source.tex",
                    "role": "manuscript",
                    "label": "TeX原稿",
                    "public": True,
                    "original_sha256": digest,
                    "sha256": digest,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [],
        }
        manifest_path = paper_dir / "paper.json"
        write_json(manifest_path, manifest_data)
        self.paper = Paper.from_dict(manifest_data, manifest_path)
        self.selected = [(manifest_path, self.paper)]
        self.paths.index.write_text(
            rendered_home_page(self.selected), encoding="utf-8"
        )
        (paper_dir / "keywords.txt").write_text(
            rendered_keywords(self.paper), encoding="utf-8"
        )
        (self.root / "styles.css").write_text("/* fixture */\n", encoding="utf-8")
        (self.root / "search.js").write_text("// fixture\n", encoding="utf-8")
        for asset in (
            "favicon.ico",
            "favicon-16.png",
            "favicon-32.png",
            "apple-touch-icon.png",
            "icon-192.png",
            "icon-512.png",
            "og-image.png",
        ):
            (self.root / asset).write_bytes(b"fixture")
        (self.root / "site.webmanifest").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_publication_stages_can_be_run_and_checked_independently(self) -> None:
        validate_stage_sources(self.paths, self.selected)
        catalog = collect_metadata(self.selected)
        self.assertEqual([self.paper], catalog.tags["試験"])
        self.assertEqual([self.paper], catalog.math_sections["その他"])

        working = self.root / "working"
        working.mkdir()
        context = StageContext(
            self.paths, self.root / "_site", working, catalog
        )
        generate_static_pages(context)
        self.assertTrue((working / "archive" / "index.html").is_file())
        self.assertTrue(
            (working / "papers" / self.paper.slug / "index.html").is_file()
        )
        self.assertFalse((working / "styles.css").exists())
        self.assertFalse((working / "feed.xml").exists())

        copy_public_files(context)
        self.assertTrue((working / "styles.css").is_file())
        self.assertTrue(
            (working / "papers" / self.paper.slug / "source.tex").is_file()
        )
        self.assertFalse((working / "feed.xml").exists())

        generate_discovery_files(context)
        self.assertTrue((working / "feed.xml").is_file())
        self.assertTrue((working / "sitemap.xml").is_file())
        check_generated_links(context)
        self.assertEqual([], local_link_errors(working))

    def test_optional_feature_failure_keeps_the_basic_site(self) -> None:
        destination = self.root / "_site"
        destination.mkdir()
        (destination / "old-site.txt").write_text("old", encoding="utf-8")

        def failing_optional(catalog, output: Path) -> None:
            self.assertEqual(1, len(catalog.selected))
            (output / "derived").mkdir()
            (output / "derived" / "partial.html").write_text(
                "partial", encoding="utf-8"
            )
            raise RuntimeError("converter unavailable")

        report = stage_site(
            self.paths,
            self.selected,
            destination,
            [
                StageFeature(
                    "html-conversion",
                    failing_optional,
                    paper_slug=self.paper.slug,
                )
            ],
        )

        self.assertFalse((destination / "old-site.txt").exists())
        self.assertTrue(
            (destination / "papers" / self.paper.slug / "index.html").is_file()
        )
        self.assertFalse((destination / "derived").exists())
        self.assertEqual("failed", report.feature_results[0].status)
        self.assertEqual(self.paper.slug, report.feature_results[0].paper_slug)
        self.assertIn("converter unavailable", report.feature_results[0].error)

    def test_required_feature_failure_does_not_replace_existing_site(self) -> None:
        destination = self.root / "_site"
        destination.mkdir()
        marker = destination / "published-site.txt"
        marker.write_text("still published", encoding="utf-8")

        def failing_required(_catalog, output: Path) -> None:
            (output / "partial.html").write_text("partial", encoding="utf-8")
            raise RuntimeError("required generator failed")

        with self.assertRaisesRegex(PaperToolError, "required site feature failed"):
            stage_site(
                self.paths,
                self.selected,
                destination,
                [StageFeature("required-index", failing_required, required=True)],
            )

        self.assertEqual("still published", marker.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            list(self.root.glob("._site.stage-*")),
            "failed working directories must be removed",
        )
        self.assertEqual(
            [],
            list(self.root.glob("._site.required-index-*")),
            "failed feature directories must be removed",
        )


if __name__ == "__main__":
    unittest.main()
