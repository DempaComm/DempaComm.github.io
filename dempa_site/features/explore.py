"""Landing page for the archive's exploration tools."""

from __future__ import annotations

from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import rendered_exploration_page


def generate_explore(catalog: SiteCatalog, output: Path) -> None:
    target = output / "explore"
    target.mkdir(parents=True)
    body = """    <section aria-labelledby="explore-title">
      <div class="section-heading">
        <h2 id="explore-title">三つの入口</h2>
        <p>読む順番、時間的な履歴、主題間の近さという異なる見方で原稿を探せます。</p>
      </div>
      <div class="explore-grid">
        <a class="explore-card" href="../reading-paths/">
          <span class="section-number">ROUTES</span>
          <strong>読書経路</strong>
          <span>テーマ別に並べた原稿を、案内文と前後リンクに沿って読みます。</span>
        </a>
        <a class="explore-card" href="../lineage/">
          <span class="section-number">HISTORY</span>
          <strong>原稿の系譜</strong>
          <span>初出、移行、改訂、派生版の生成を時間軸で確認します。</span>
        </a>
        <a class="explore-card" href="../graph/">
          <span class="section-number">RELATIONS</span>
          <strong>原稿関係図</strong>
          <span>電波通信のタグを手掛かりに、近い話題の原稿を図から探します。</span>
        </a>
      </div>
    </section>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="原稿を探索する",
            eyebrow="EXPLORE THE ARCHIVE",
            description=f"{len(catalog.selected)}件の原稿を、一覧とは違う三つの方法でたどるための入口です。",
            canonical_path="/explore/",
            body=body,
        ),
        encoding="utf-8",
    )
