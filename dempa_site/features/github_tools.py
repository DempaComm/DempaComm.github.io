"""A source-backed introduction to DempaComm's public skills and tools."""

from __future__ import annotations

from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page


def generate_github_tools(_catalog: SiteCatalog, output: Path) -> None:
    target = output / "tools"
    target.mkdir(parents=True)
    body = Path(__file__).with_suffix(".html").read_text(encoding="utf-8")
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="GitHubのskills・ツール",
            eyebrow="WRITING, READING & PUBLISHING",
            description="数学の文章を書く、用例を調べる、原稿を公開する。DempaCommがGitHubで公開しているskillsとツールを紹介します。",
            canonical_path="/tools/",
            body=body,
            body_class="github-tools-page",
            current_navigation="",
            extra_head='  <link rel="stylesheet" href="tools.css">\n',
        ),
        encoding="utf-8",
    )
    (target / "tools.css").write_bytes(
        Path(__file__).with_suffix(".css").read_bytes()
    )
