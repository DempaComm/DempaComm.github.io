from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "scripts" / "migration_ledger.py"


class MigrationLedgerTest(unittest.TestCase):
    def test_article_sync_preserves_manually_found_external_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2022" / "1__10" / "ar1" / "dummy"
            source_dir.mkdir(parents=True)
            (source_dir / "dummy.tex").write_text(
                r"\title{ダミー}", encoding="utf-8"
            )
            (root / "papers").mkdir(parents=True)
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}
            export = Path(temporary) / "hatena.export.txt"
            export.write_text(
                "\n".join(
                    [
                        "AUTHOR: example",
                        "TITLE: 外部で見つかった記事",
                        "BASENAME: 2024/01/02/120000",
                        "STATUS: Publish",
                        "DATE: 01/02/2024 12:00:00",
                        "CATEGORY: 数学",
                        "-----",
                        "BODY:",
                        '<a href="https://example.com/found.pdf">found.pdf</a>',
                        "-----",
                        "--------",
                    ]
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            sync_command = [
                sys.executable,
                str(TOOL),
                "sync-articles",
                str(export),
                "--blog-url",
                "https://example.hatenablog.com",
            ]
            subprocess.run(
                sync_command,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            csv_path = root / "ledger" / "migration-ledger.csv"
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
                fields = list(rows[0])
            article = next(
                row for row in rows if row["title"] == "外部で見つかった記事"
            )
            article.update(
                {
                    "status": "source_found",
                    "source_dir": "MyBlog/2024/found",
                    "tex_files": "found.tex",
                    "pdf_files": "found.pdf",
                    "math_section": "位相・距離・幾何",
                    "author_review": "pending",
                    "notes": "MyBlog全体の調査で確認した候補。",
                }
            )
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            subprocess.run(
                sync_command,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            article = next(
                row for row in rows if row["title"] == "外部で見つかった記事"
            )
            self.assertEqual("source_found", article["status"])
            self.assertEqual("MyBlog/2024/found", article["source_dir"])
            self.assertEqual("found.tex", article["tex_files"])
            self.assertEqual("found.pdf", article["pdf_files"])
            self.assertEqual("tex_pdf", article["local_assets"])
            self.assertEqual("linked", article["article_pdf"])
            self.assertEqual("pending", article["author_review"])
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "begin-privacy-review",
                    article["record_id"],
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            subprocess.run(
                sync_command,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            article = next(
                row for row in rows if row["title"] == "外部で見つかった記事"
            )
            self.assertEqual("privacy_review", article["status"])
            self.assertEqual("MyBlog/2024/found", article["source_dir"])
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "decide-privacy-review",
                    "--decision",
                    "approved",
                    "--reason",
                    "名義と全ページを確認済み。",
                    article["record_id"],
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            subprocess.run(
                sync_command,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            article = next(
                row for row in rows if row["title"] == "外部で見つかった記事"
            )
            self.assertEqual("ready", article["status"])
            self.assertEqual("approved", article["author_review"])
            self.assertIn("名義と全ページを確認済み。", article["notes"])

    def test_article_inventory_adds_unmigrated_article_and_asset_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2022" / "1__10" / "ar1" / "known"
            source_dir.mkdir(parents=True)
            (source_dir / "known.tex").write_text(
                r"\title{既知の記事}", encoding="utf-8"
            )
            (source_dir / "known.pdf").write_bytes(b"%PDF known")
            (root / "papers").mkdir(parents=True)
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}
            export = Path(temporary) / "hatena.export.txt"
            export.write_text(
                "\n".join(
                    [
                        "AUTHOR: example",
                        "TITLE: 既知の記事",
                        "BASENAME: 2022/01/01/120000",
                        "STATUS: Publish",
                        "DATE: 01/01/2022 12:00:00",
                        "CATEGORY: 数学",
                        "-----",
                        "BODY:",
                        '<a href="https://example.com/known.pdf">known.pdf</a>',
                        "-----",
                        "--------",
                        "AUTHOR: example",
                        "TITLE: 原稿が見つからない記事",
                        "BASENAME: 2022/01/02/120000",
                        "STATUS: Publish",
                        "DATE: 01/02/2022 12:00:00",
                        "CATEGORY: 数学",
                        "-----",
                        "BODY:",
                        '<a href="https://example.com/missing.pdf">missing.pdf</a>',
                        "-----",
                        "--------",
                    ]
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "match-metadata",
                    str(export),
                    str(myblog),
                    "--blog-url",
                    "https://example.hatenablog.com",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with (root / "ledger" / "migration-ledger.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            known = next(row for row in rows if row["source_dir"])
            missing = next(row for row in rows if row["status"] == "source_missing")
            self.assertEqual("tex_pdf", known["local_assets"])
            self.assertEqual("linked", known["article_pdf"])
            self.assertEqual("none", missing["local_assets"])
            self.assertEqual("linked", missing["article_pdf"])
            self.assertEqual("missing.pdf", missing["metadata_pdf_files"])
            with (root / "ledger" / "unmigrated-articles.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                unmigrated = list(csv.DictReader(stream))
            self.assertEqual(
                ["原稿が見つからない記事"],
                [row["title"] for row in unmigrated],
            )

    def test_scan_matches_published_source_and_preserves_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2022" / "11__20" / "ar11" / "sample"
            source_dir.mkdir(parents=True)
            tex = source_dir / "sample.tex"
            pdf = source_dir / "sample.pdf"
            tex.write_bytes(b"original tex")
            pdf.write_bytes(b"%PDF original")
            component_dir = myblog / "2022" / "11__20" / "ar11" / "component"
            component_dir.mkdir(parents=True)
            component_tex = component_dir / "component.tex"
            component_pdf = component_dir / "component.pdf"
            component_bib = component_dir / "component.bib"
            component_tex.write_bytes(b"component tex")
            component_pdf.write_bytes(b"%PDF component")
            component_bib.write_bytes(b"component bibliography")
            private_copy = myblog / "MyBlogCOPY" / "private"
            private_copy.mkdir(parents=True)
            (private_copy / "private.tex").write_bytes(b"do not list")

            paper_dir = root / "papers" / "2022-09-10-01"
            paper_dir.mkdir(parents=True)
            manifest = {
                "schema_version": 2,
                "slug": "2022-09-10-01",
                "migration_record_id": (
                    "source:"
                    + hashlib.sha256(
                        b"2022/11__20/ar11/sample"
                    ).hexdigest()[:16]
                ),
                "title": "Published title",
                "published_at": "2022-09-10T23:42:49+09:00",
                "sequence": 1,
                "original_url": "https://example.com/original",
                "tags": ["数学", "解析"],
                "math_section": "解析・測度・確率",
                "build": {"enabled": False, "engine": "platex"},
                "files": [
                    {
                        "original_sha256": hashlib.sha256(tex.read_bytes()).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(
                            component_tex.read_bytes()
                        ).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(
                            component_pdf.read_bytes()
                        ).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(
                            component_bib.read_bytes()
                        ).hexdigest()
                    },
                ],
            }
            (paper_dir / "paper.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}

            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            csv_path = root / "ledger" / "migration-ledger.csv"
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(2, len(rows))
            by_name = {Path(row["source_dir"]).name: row for row in rows}
            self.assertEqual("published", by_name["sample"]["status"])
            self.assertEqual(
                "source_found", by_name["component"]["status"]
            )
            self.assertEqual("2022-09-10-01", by_name["sample"]["target_slug"])
            self.assertEqual("sample.tex", by_name["sample"]["tex_files"])
            self.assertEqual("unique", by_name["sample"]["duplicate_status"])
            self.assertNotIn(str(Path(temporary)), by_name["sample"]["source_dir"])
            self.assertNotIn("MyBlogCOPY", by_name["sample"]["source_dir"])

            by_name["sample"]["notes"] = "manual note"
            with csv_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rescanned = list(csv.DictReader(stream))
            rescanned_by_name = {
                Path(row["source_dir"]).name: row for row in rescanned
            }
            self.assertEqual("manual note", rescanned_by_name["sample"]["notes"])

            checked = subprocess.run(
                [sys.executable, str(TOOL), "check"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("OK  migration ledger", checked.stdout)
            generated = json.loads(
                (root / "ledger" / "migration-ledger.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(2, generated["record_count"])
            self.assertEqual(1, generated["status_counts"]["published"])
            self.assertEqual(2, generated["duplicate_counts"]["unique"])

    def test_duplicate_groups_prefer_published_and_keep_versions_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}

            def add(
                relative: str,
                tex_bytes: Optional[bytes],
                pdf_bytes: Optional[bytes],
            ) -> tuple[Optional[Path], Optional[Path]]:
                directory = myblog / relative
                directory.mkdir(parents=True)
                tex_path = directory / "main.tex" if tex_bytes is not None else None
                pdf_path = directory / "main.pdf" if pdf_bytes is not None else None
                if tex_path:
                    tex_path.write_bytes(tex_bytes)
                if pdf_path:
                    pdf_path.write_bytes(pdf_bytes)
                return tex_path, pdf_path

            published_tex, published_pdf = add(
                "2020/1__10/ar1/published", b"same tex", b"same pdf"
            )
            add("2020/1__10/ar2/exact-copy", b"same tex", b"same pdf")
            add("2020/1__10/ar3/tex-a", b"shared tex", b"pdf a")
            add("2020/1__10/ar4/tex-b", b"shared tex", b"pdf b")
            add("2020/1__10/ar5/pdf-a", b"tex a", b"shared pdf")
            add("2020/1__10/ar6/pdf-b", b"tex b", b"shared pdf")
            add("2020/1__10/ar7/version-a", b"version one", b"version one pdf")
            add("2020/1__10/ar8/version-b", b"version two", b"version two pdf")

            paper_dir = root / "papers" / "2020-01-01-01"
            paper_dir.mkdir(parents=True)
            manifest = {
                "schema_version": 2,
                "slug": "2020-01-01-01",
                "title": "Published",
                "published_at": "2020-01-01T00:00:00+09:00",
                "sequence": 1,
                "original_url": "",
                "tags": ["数学"],
                "math_section": "",
                "build": {"enabled": False, "engine": "platex"},
                "files": [
                    {
                        "original_sha256": hashlib.sha256(
                            published_tex.read_bytes()
                        ).hexdigest()
                    },
                    {
                        "original_sha256": hashlib.sha256(
                            published_pdf.read_bytes()
                        ).hexdigest()
                    },
                ],
            }
            (paper_dir / "paper.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with (root / "ledger" / "migration-ledger.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            by_name = {Path(row["source_dir"]).name: row for row in rows}

            exact_pair = [by_name["published"], by_name["exact-copy"]]
            canonical = next(
                row for row in exact_pair if row["duplicate_status"] == "canonical"
            )
            duplicate = next(
                row for row in exact_pair if row["duplicate_status"] == "duplicate"
            )
            self.assertEqual("2020-01-01-01", canonical["target_slug"])
            self.assertEqual("tex+pdf", canonical["duplicate_basis"])
            self.assertEqual(
                canonical["record_id"],
                duplicate["canonical_record_id"],
            )
            self.assertEqual("tex", by_name["tex-a"]["duplicate_basis"])
            self.assertEqual("tex", by_name["tex-b"]["duplicate_basis"])
            self.assertEqual("pdf", by_name["pdf-a"]["duplicate_basis"])
            self.assertEqual("pdf", by_name["pdf-b"]["duplicate_basis"])
            self.assertEqual("unique", by_name["version-a"]["duplicate_status"])
            self.assertEqual("unique", by_name["version-b"]["duplicate_status"])

    def test_mt_metadata_matching_is_proposed_then_explicitly_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2022" / "11__20" / "ar11" / "upper"
            source_dir.mkdir(parents=True)
            (source_dir / "extupperhalf.tex").write_text(
                r"\title{$C^{\infty}$関数の鏡像拡張}", encoding="utf-8"
            )
            (source_dir / "extupperhalf.pdf").write_bytes(b"%PDF exact")
            (root / "papers").mkdir(parents=True)
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}

            export = Path(temporary) / "hatena.export.txt"
            export.write_text(
                "\n".join(
                    [
                        "AUTHOR: example",
                        "TITLE: 滑らかな関数の鏡像拡張と，境界付き多様体の座標変換",
                        "BASENAME: 2022/09/10/234249",
                        "STATUS: Publish",
                        "DATE: 09/10/2022 23:42:49",
                        "CATEGORY: 位相空間",
                        "CATEGORY: 数学",
                        "CATEGORY: 解析",
                        "CATEGORY: 断片ではないもの",
                        "-----",
                        "BODY:",
                        (
                            '<iframe title="url=https%3A%2F%2Fwww.dropbox.com'
                            '%2Fs%2Fexample%2Fextupperhalf.pdf%3Frlkey%3Dsecret">'
                            "</iframe>"
                        ),
                        "-----",
                        "--------",
                    ]
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "match-metadata",
                    str(export),
                    str(myblog),
                    "--blog-url",
                    "https://example.hatenablog.com",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            csv_path = root / "ledger" / "migration-ledger.csv"
            with csv_path.open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual("exact", row["metadata_match"])
            self.assertEqual("", row["original_url"])
            self.assertEqual(
                "https://example.hatenablog.com/entry/2022/09/10/234249",
                row["metadata_original_url"],
            )
            self.assertEqual(
                "位相空間|数学|解析|断片ではないもの", row["metadata_tags"]
            )
            self.assertEqual("extupperhalf.pdf", row["metadata_pdf_files"])
            self.assertNotIn("dropbox.com", row["metadata_pdf_files"])
            self.assertNotIn("rlkey", row["metadata_pdf_files"])
            self.assertEqual("1", row["metadata_sequence"])
            self.assertEqual("source_found", row["status"])

            review_path = root / ".privacy-review" / "metadata-review.html"
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "render-metadata-review",
                    str(review_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            review_html = review_path.read_text(encoding="utf-8")
            self.assertIn("メタデータ候補確認", review_html)
            self.assertIn(row["record_id"], review_html)
            self.assertIn("extupperhalf.pdf", review_html)
            self.assertIn("採用分の確定コマンドをコピー", review_html)
            self.assertIn("優先アーカイブのみ", review_html)
            self.assertIn('<option value="favorite">僕のお気に入り</option>', review_html)
            self.assertIn("未移行の新規記事候補", review_html)
            self.assertIn("既存記事の別版", review_html)
            self.assertIn('"priority_archive": true', review_html)
            self.assertNotIn("dropbox.com", review_html)
            self.assertNotIn("rlkey", review_html)
            self.assertNotIn(str(Path(temporary)), review_html)

            priority = subprocess.run(
                [sys.executable, str(TOOL), "archive-priority"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("1 unpublished articles tagged 断片ではないもの", priority.stdout)
            self.assertIn(row["record_id"], priority.stdout)

            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "confirm-metadata",
                    row["record_id"],
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                confirmed = next(csv.DictReader(stream))
            self.assertEqual("metadata_ready", confirmed["status"])
            self.assertEqual(
                confirmed["metadata_original_url"], confirmed["original_url"]
            )
            self.assertEqual(confirmed["metadata_title"], confirmed["title"])

    def test_metadata_can_be_confirmed_by_explicit_export_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            myblog = Path(temporary) / "Myblogstr"
            source_dir = myblog / "2017" / "1__10" / "ar2" / "source"
            source_dir.mkdir(parents=True)
            (source_dir / "source.tex").write_text(
                r"\title{候補名とは一致しない原稿}", encoding="utf-8"
            )
            (root / "papers").mkdir(parents=True)
            environment = {**os.environ, "LEDGER_REPO_ROOT": str(root)}
            export = Path(temporary) / "hatena.export.txt"
            export.write_text(
                "\n".join(
                    [
                        "AUTHOR: example",
                        "TITLE: 手動で選んだ記事",
                        "BASENAME: 2017/11/16/170409",
                        "STATUS: Publish",
                        "DATE: 11/16/2017 17:04:09",
                        "CATEGORY: 数学",
                        "-----",
                        "BODY:",
                        "本文",
                        "-----",
                        "--------",
                    ]
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(TOOL), "scan", str(myblog)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            csv_path = root / "ledger" / "migration-ledger.csv"
            with csv_path.open(encoding="utf-8", newline="") as stream:
                record_id = next(csv.DictReader(stream))["record_id"]
            article_url = (
                "https://example.hatenablog.com/entry/2017/11/16/170409"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "confirm-metadata-url",
                    str(export),
                    f"{record_id}={article_url}",
                    "--blog-url",
                    "https://example.hatenablog.com",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            with csv_path.open(encoding="utf-8", newline="") as stream:
                confirmed = next(csv.DictReader(stream))
            self.assertEqual("metadata_ready", confirmed["status"])
            self.assertEqual("手動で選んだ記事", confirmed["title"])
            self.assertEqual(article_url, confirmed["original_url"])
            self.assertEqual(
                "manually confirmed by original URL",
                confirmed["metadata_evidence"],
            )


if __name__ == "__main__":
    unittest.main()
