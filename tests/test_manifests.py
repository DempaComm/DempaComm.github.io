from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from dempa_site.errors import DempaSiteError
from dempa_site.files import write_json
from dempa_site.manifests.loader import load_manifest, load_manifest_directory
from dempa_site.manifests.model import (
    ApprovedChange,
    BuildSettings,
    Correction,
    HistoryEvent,
    Paper,
    PaperFile,
    PaperRelation,
    PrivacyReview,
    Statement,
)


HASH_A = "a" * 64


def blog_manifest(slug: str = "2026-07-22-01") -> dict:
    return {
        "schema_version": 2,
        "slug": slug,
        "migration_record_id": "fixture:manifest",
        "legacy_slugs": [],
        "title": "型付きmanifest",
        "published_at": f"{slug[:10]}T12:00:00+09:00",
        "sequence": int(slug[-2:]),
        "year": int(slug[:4]),
        "kind": "ブログ本文のみ",
        "math_section": "その他",
        "summary": "型と検査を確認するテストです。",
        "original_url": "https://example.hatenablog.com/entry/fixture",
        "order": int(slug[:10].replace("-", "") + slug[-2:]),
        "tags": ["数学"],
        "keywords": ["型付きmanifest"],
        "build": {"enabled": False, "engine": ""},
        "files": [],
        "approved_changes": [],
        "privacy_reviews": [],
    }


def tex_manifest() -> dict:
    value = blog_manifest()
    value.update(
        {
            "kind": "TeX原稿",
            "original_url": "",
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": "source.tex",
                    "role": "manuscript",
                    "label": "TeX原稿",
                    "public": True,
                    "original_sha256": HASH_A,
                    "sha256": HASH_A,
                }
            ],
            "privacy_reviews": [
                {
                    "path": "source.tex",
                    "status": "reviewed",
                    "reason": "",
                    "source_sha256": HASH_A,
                    "inspection_status": "completed",
                    "recorded_at": "2026-07-22T03:00:00+00:00",
                }
            ],
        }
    )
    return value


class ManifestModelTest(unittest.TestCase):
    def write_manifest(self, root: Path, value: dict) -> Path:
        path = root / "papers" / value["slug"] / "paper.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, value)
        return path

    def test_valid_manifest_becomes_typed_immutable_view(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            value = tex_manifest()
            value["approved_changes"] = [
                {
                    "approved_at": "2026-07-22T04:00:00+00:00",
                    "reason": "検査用の承認履歴",
                    "files": [
                        {
                            "path": "source.tex",
                            "from_sha256": HASH_A,
                            "to_sha256": HASH_A,
                        }
                    ],
                }
            ]
            path = self.write_manifest(Path(temporary), value)
            paper = load_manifest(path)
            self.assertIsInstance(paper, Paper)
            self.assertIsInstance(paper.build, BuildSettings)
            self.assertIsInstance(paper.files[0], PaperFile)
            self.assertIsInstance(paper.privacy_reviews[0], PrivacyReview)
            self.assertIsInstance(paper.approved_changes[0], ApprovedChange)
            self.assertEqual("platex", paper.build.effective_engine)
            self.assertEqual("source.tex", paper.files[0].path)

            legacy_tags = paper["tags"]
            legacy_tags.append("変更")
            self.assertEqual(("数学",), paper.tags)
            self.assertEqual(["数学"], paper.to_dict()["tags"])

    def test_json_schema_rejects_missing_wrong_and_unknown_fields(self) -> None:
        cases = []
        missing = blog_manifest()
        del missing["title"]
        cases.append((missing, "is missing: title"))
        wrong = blog_manifest()
        wrong["sequence"] = "1"
        cases.append((wrong, "sequence must be integer"))
        unknown = blog_manifest()
        unknown["titel"] = "typo"
        cases.append((unknown, "unknown fields: titel"))

        for value, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                path = self.write_manifest(Path(temporary), value)
                with self.assertRaisesRegex(DempaSiteError, expected):
                    load_manifest(path)

    def test_published_date_slug_year_and_order_must_agree(self) -> None:
        for field, replacement, expected in (
            ("slug", "2026-07-23-01", "slug must match published date"),
            ("year", 2025, "year must match published date"),
            ("order", 2026072202, "order must match published date"),
        ):
            value = blog_manifest()
            value[field] = replacement
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / "papers" / str(value["slug"]) / "paper.json"
                path.parent.mkdir(parents=True)
                write_json(path, value)
                with self.assertRaisesRegex(DempaSiteError, expected):
                    load_manifest(path)

    def test_blog_only_paper_cannot_build_or_contain_files(self) -> None:
        value = blog_manifest()
        value["build"] = {"enabled": True, "engine": "", "root": "main.tex"}
        value["files"] = [
            {
                "path": "main.tex",
                "role": "manuscript",
                "label": "TeX原稿",
                "public": False,
                "original_sha256": HASH_A,
                "sha256": HASH_A,
            }
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_manifest(Path(temporary), value)
            with self.assertRaisesRegex(DempaSiteError, "cannot enable a TeX build"):
                load_manifest(path)

    def test_build_root_and_source_only_rules_are_semantic(self) -> None:
        missing_root = tex_manifest()
        missing_root["build"] = {
            "enabled": True,
            "engine": "platex",
            "root": "missing.tex",
        }
        source_main = tex_manifest()
        source_main["files"][0]["path"] = "main.tex"
        source_main["privacy_reviews"][0]["path"] = "main.tex"
        for value, expected in (
            (missing_root, "build.root must appear in files"),
            (source_main, "source-only papers must not use main.tex"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                path = self.write_manifest(Path(temporary), value)
                with self.assertRaisesRegex(DempaSiteError, expected):
                    load_manifest(path)

    def test_supported_build_engines_are_validated(self) -> None:
        for engine in ("platex", "uplatex", "pdflatex", "lualatex", "xelatex"):
            value = tex_manifest()
            value["build"] = {
                "enabled": True,
                "engine": engine,
                "root": "source.tex",
            }
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temporary:
                paper = load_manifest(self.write_manifest(Path(temporary), value))
                self.assertEqual(engine, paper.build.effective_engine)

        value = tex_manifest()
        value["build"] = {
            "enabled": True,
            "engine": "unknowntex",
            "root": "source.tex",
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_manifest(Path(temporary), value)
            with self.assertRaisesRegex(DempaSiteError, "build.engine must be one of"):
                load_manifest(path)

    def test_privacy_review_must_cover_current_public_tex_hash(self) -> None:
        value = tex_manifest()
        value["privacy_reviews"][0]["source_sha256"] = "b" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_manifest(Path(temporary), value)
            with self.assertRaisesRegex(DempaSiteError, "invalid privacy review coverage"):
                load_manifest(path)

    def test_optional_future_records_have_types_without_rewriting_old_json(self) -> None:
        value = blog_manifest()
        value.update(
            {
                "history": [
                    {
                        "recorded_at": "2026-07-22T03:00:00+00:00",
                        "kind": "publication",
                        "summary": "公開",
                    }
                ],
                "corrections": [
                    {
                        "recorded_at": "2026-07-22T04:00:00+00:00",
                        "summary": "誤字訂正",
                    }
                ],
                "statements": [
                    {
                        "identifier": "theorem-1",
                        "kind": "theorem",
                        "title": "定理1",
                        "anchor": "#theorem-1",
                    }
                ],
                "relations": [
                    {"target_slug": value["slug"], "kind": "self", "label": "自身"}
                ],
                "license": "未指定",
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_manifest(Path(temporary), value)
            paper = load_manifest(path)
            self.assertIsInstance(paper.history[0], HistoryEvent)
            self.assertIsInstance(paper.corrections[0], Correction)
            self.assertIsInstance(paper.statements[0], Statement)
            self.assertIsInstance(paper.relations[0], PaperRelation)
            self.assertNotIn("history", blog_manifest())

    def test_html_versions_reads_new_and_legacy_metadata(self) -> None:
        version = {
            "status": "approved",
            "generator": "LaTeXML",
            "generator_version": "0.8.8",
            "generated_at": "2026-07-26T12:00:00+09:00",
            "source_path": "source.tex",
            "source_sha256": HASH_A,
            "path": "html/index.html",
            "label": "HTML版を読む",
            "reviewed_at": "2026-07-26T13:00:00+09:00",
        }
        alternate = {
            **version,
            "path": "html-original/index.html",
            "label": "元版HTMLを読む",
        }
        new_value = tex_manifest()
        new_value["files"].extend(
            [
                {
                    "path": version["path"],
                    "role": "derived-html",
                    "label": version["label"],
                    "public": True,
                    "original_sha256": HASH_A,
                    "sha256": HASH_A,
                },
                {
                    "path": alternate["path"],
                    "role": "derived-html",
                    "label": alternate["label"],
                    "public": True,
                    "original_sha256": HASH_A,
                    "sha256": HASH_A,
                },
            ]
        )
        new_value["html_versions"] = [version, alternate]
        legacy_value = deepcopy(new_value)
        legacy_value.pop("html_versions")
        legacy_value["html_version"] = version
        legacy_value["alternate_html_versions"] = [alternate]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            new = load_manifest(self.write_manifest(root / "new", new_value))
            legacy = load_manifest(
                self.write_manifest(root / "legacy", legacy_value)
            )

            self.assertEqual(new.html_versions, legacy.html_versions)
            self.assertEqual(version["path"], legacy.html_version.path)
            self.assertEqual(
                alternate["path"], legacy.alternate_html_versions[0].path
            )

    def test_new_and_legacy_html_fields_cannot_be_combined(self) -> None:
        value = tex_manifest()
        version = {
            "status": "approved",
            "generator": "LaTeXML",
            "generator_version": "0.8.8",
            "generated_at": "2026-07-26T12:00:00+09:00",
            "source_path": "source.tex",
            "source_sha256": HASH_A,
            "path": "html/index.html",
            "label": "HTML版を読む",
            "reviewed_at": "2026-07-26T13:00:00+09:00",
        }
        value["html_versions"] = [version]
        value["html_version"] = version
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_manifest(Path(temporary), value)
            with self.assertRaisesRegex(
                DempaSiteError, "cannot be combined with legacy"
            ):
                load_manifest(path)

    def test_relation_target_must_exist_in_loaded_collection(self) -> None:
        value = blog_manifest()
        value["relations"] = [
            {"target_slug": "2026-07-21-01", "kind": "previous", "label": "前の記事"}
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_manifest(root, value)
            with self.assertRaisesRegex(DempaSiteError, "unknown paper slugs"):
                load_manifest_directory(root / "papers")


if __name__ == "__main__":
    unittest.main()
