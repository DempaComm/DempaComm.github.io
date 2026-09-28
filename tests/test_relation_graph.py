from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dempa_site.features.relation_graph import _graph_data, _tag_connections

ROOT = Path(__file__).resolve().parents[1]


def paper(index: int, tags: tuple[str, ...] = ("数学", "位相空間", "距離空間")):
    return SimpleNamespace(
        slug=f"paper-{index:02}", title=f"試験原稿 {index}", summary="公開用の概要",
        year=2026, order=index, math_section="位相・距離・幾何", tags=tags, relations=[],
    )


class RelationGraphTest(unittest.TestCase):
    def test_tag_suggestions_are_sparse_and_never_invent_tags(self):
        papers = [paper(index) for index in range(20)] + [paper(20, ("数学", "雑談"))]
        counts = Counter(tag for item in papers for tag in item.tags)
        edges = _tag_connections(papers, counts)
        degree = Counter(slug for pair in edges for slug in pair)
        self.assertTrue(edges)
        self.assertLessEqual(max(degree.values()), 4)
        self.assertNotIn("paper-20", degree)
        self.assertEqual(edges, _tag_connections(list(reversed(papers)), counts))
        for tags, affinity in edges.values():
            self.assertEqual({"位相空間", "距離空間"}, set(tags))
            self.assertGreater(affinity, 0)
            self.assertLessEqual(affinity, 1)

    def test_authored_relations_and_paths_survive_suggestion_cap(self):
        papers = [paper(index) for index in range(10)] + [paper(10, ("数学",))]
        papers[0].relations = [SimpleNamespace(target_slug=papers[10].slug, kind="prerequisite")]
        path = SimpleNamespace(slug="sample", title="試験経路", papers=[papers[9], papers[10]])
        capability = SimpleNamespace(html_path="html/index.html", statement_counts={}, statement_count=0, correction_count=0)
        catalog = SimpleNamespace(selected=[(None, item) for item in papers])
        with patch("dempa_site.features.relation_graph.paper_capabilities", return_value={item.slug: capability for item in papers}), \
             patch("dempa_site.features.relation_graph.load_reading_paths", return_value=[path]):
            graph = _graph_data(catalog)
        edges = {(edge["source"], edge["target"]): edge for edge in graph["edges"]}
        self.assertEqual(["prerequisite"], edges[(papers[0].slug, papers[10].slug)]["explicit"])
        self.assertEqual(["sample"], edges[(papers[9].slug, papers[10].slug)]["reading_paths"])
        self.assertEqual([], edges[(papers[0].slug, papers[10].slug)]["tags"])
        self.assertEqual(len(papers), len(graph["nodes"]))
        self.assertEqual("公開用の概要", graph["nodes"][0]["summary"])
        self.assertEqual([{"slug": "sample", "title": "試験経路"}], graph["nodes"][-1]["reading_paths"])

    def test_tag_selection_is_stable_across_python_hash_seeds(self):
        script = """
import json
from collections import Counter
from types import SimpleNamespace
from dempa_site.features.relation_graph import _tag_connections
papers = [SimpleNamespace(slug=str(i), tags=['数学', '位相', '距離', str(i % 3)]) for i in range(18)]
counts = Counter(tag for paper in papers for tag in paper.tags)
print(json.dumps([(key, value) for key, value in _tag_connections(papers, counts).items()]))
"""
        results = [subprocess.check_output([sys.executable, "-c", script], cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": str(seed)}) for seed in (1, 72)]
        self.assertEqual(*results)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for graph model checks")
    def test_browser_graph_filter_and_layout_contracts(self):
        result = subprocess.run(["node", str(ROOT / "tests" / "graph_model.mjs")],
            cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
