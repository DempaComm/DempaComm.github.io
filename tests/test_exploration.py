from __future__ import annotations

import unittest
from pathlib import Path

from dempa_site.features.lineage import _events
from dempa_site.manifests.model import Paper


class ExplorationPrivacyTest(unittest.TestCase):
    def test_lineage_does_not_publish_internal_approval_reason(self) -> None:
        digest_a = "a" * 64
        digest_b = "b" * 64
        private_reason = "公開用コピーから本名と本名名義サイトURLを含むコメント2行を削除"
        value = {
            "schema_version": 1,
            "slug": "2026-07-27-01",
            "migration_record_id": "fixture:lineage",
            "legacy_slugs": [],
            "title": "系譜の試験",
            "published_at": "2026-07-27T12:00:00+09:00",
            "sequence": 1,
            "year": 2026,
            "kind": "単純なTeX",
            "math_section": "その他",
            "summary": "系譜の公開範囲を確認します。",
            "original_url": "",
            "order": 2026072701,
            "tags": ["数学"],
            "keywords": ["系譜"],
            "build": {"enabled": True, "engine": "lualatex", "root": "main.tex"},
            "files": [{
                "path": "main.tex",
                "role": "manuscript",
                "label": "TeX原稿",
                "public": True,
                "original_sha256": digest_a,
                "sha256": digest_b,
            }],
            "approved_changes": [{
                "approved_at": "2026-07-27T13:00:00+09:00",
                "reason": private_reason,
                "files": [{
                    "path": "main.tex",
                    "from_sha256": digest_a,
                    "to_sha256": digest_b,
                }],
            }],
            "privacy_reviews": [],
        }
        paper = Paper.from_dict(value, Path("papers/2026-07-27-01/paper.json"))
        events = _events(paper)

        self.assertNotIn(private_reason, str(events))
        self.assertEqual("公開原稿を改訂（1ファイル）", events[-1]["summary"])


if __name__ == "__main__":
    unittest.main()
