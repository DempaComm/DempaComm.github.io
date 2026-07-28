"""Validated, hand-curated reading paths through archived papers."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dempa_site.catalog.metadata import SiteCatalog
from dempa_site.features.exploration_common import (
    rendered_exploration_page,
    repository_root,
)
from dempa_site.features.paper_capabilities import PaperCapabilities, paper_capabilities
from dempa_site.files import read_json, write_json
from dempa_site.manifests.model import Paper
from dempa_site.manifests.schema import validate_json_schema


@dataclass(frozen=True)
class ReadingStep:
    slug: str
    guide: str
    paper: Paper


@dataclass(frozen=True)
class ReadingPath:
    slug: str
    title: str
    description: str
    prerequisites: tuple[str, ...]
    papers: tuple[ReadingStep, ...]


@lru_cache(maxsize=8)
def load_reading_paths(catalog: SiteCatalog) -> tuple[ReadingPath, ...]:
    root = repository_root(catalog)
    papers = {paper.slug: paper for _, paper in catalog.selected}
    paths: list[ReadingPath] = []
    collection_dir = root / "collections"
    if not collection_dir.is_dir():
        return ()
    schema = read_json(root / "schemas" / "reading-path.schema.json")
    for source in sorted(collection_dir.glob("*.json")):
        value = read_json(source)
        validate_json_schema(value, schema, source, ValueError)
        slug = value["slug"]
        if source.stem != slug or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"{source}: slugは英小文字・数字・ハイフンで記述してください")
        step_slugs = [item["slug"] for item in value["papers"]]
        if len(step_slugs) != len(set(step_slugs)):
            raise ValueError(f"{source}: 同じ原稿が読書経路内で重複しています")
        missing = sorted(set(step_slugs) - set(papers))
        if missing:
            raise ValueError(f"{source}: 未登録の原稿番号: {', '.join(missing)}")
        paths.append(
            ReadingPath(
                slug=slug,
                title=value["title"],
                description=value["description"],
                prerequisites=tuple(value["prerequisites"]),
                papers=tuple(
                    ReadingStep(item["slug"], item["guide"], papers[item["slug"]])
                    for item in value["papers"]
                ),
            )
        )
    _validate_path_graph(paths)
    return tuple(paths)


def _validate_path_graph(paths: tuple[ReadingPath, ...] | list[ReadingPath]) -> None:
    by_slug = {path.slug: path for path in paths}
    if len(by_slug) != len(paths):
        raise ValueError("読書経路のslugが重複しています")
    for path in paths:
        missing = sorted(set(path.prerequisites) - set(by_slug))
        if missing:
            raise ValueError(f"{path.slug}: 未登録の前提経路: {', '.join(missing)}")
        if path.slug in path.prerequisites:
            raise ValueError(f"{path.slug}: 自分自身を前提経路にはできません")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(slug: str) -> None:
        if slug in visiting:
            raise ValueError(f"読書経路の前提関係が循環しています: {slug}")
        if slug in visited:
            return
        visiting.add(slug)
        for prerequisite in by_slug[slug].prerequisites:
            visit(prerequisite)
        visiting.remove(slug)
        visited.add(slug)

    for slug in by_slug:
        visit(slug)


def validate_reading_paths(catalog: SiteCatalog) -> None:
    load_reading_paths(catalog)


def _path_card(path: ReadingPath) -> str:
    prerequisites = "前提経路あり" if path.prerequisites else "前提経路なし"
    return f"""      <a class="explore-card" href="{path.slug}/">
        <span class="section-number">{len(path.papers)} PAPERS</span>
        <strong>{html.escape(path.title)}</strong>
        <span>{html.escape(path.description)}</span>
        <small>{prerequisites}</small>
      </a>"""


def _step_actions(step: ReadingStep, capability: PaperCapabilities) -> str:
    links = [
        f'<a href="../../papers/{html.escape(step.slug, quote=True)}/">原稿ページ</a>'
    ]
    if capability.html_path:
        links.append(
            f'<a href="../../papers/{html.escape(step.slug, quote=True)}/'
            f'{html.escape(capability.html_path, quote=True)}">HTML本文を読む</a>'
        )
        if capability.statement_count:
            links.append(
                f'<a href="../../statements/?paper={html.escape(step.slug, quote=True)}">'
                f'定理等{capability.statement_count}件</a>'
            )
    return '<nav class="reading-step-actions" aria-label="本文への入口">' + "".join(links) + "</nav>"


def _rendered_path_page(
    path: ReadingPath,
    all_paths: dict[str, ReadingPath],
    capabilities: Mapping[str, PaperCapabilities],
) -> str:
    prerequisite_links = ""
    if path.prerequisites:
        links = "、".join(
            f'<a href="../{html.escape(slug, quote=True)}/">{html.escape(all_paths[slug].title)}</a>'
            for slug in path.prerequisites
        )
        prerequisite_links = f'<p class="path-prerequisites"><strong>先に読む経路：</strong>{links}</p>'
    steps = []
    for index, step in enumerate(path.papers, 1):
        previous = path.papers[index - 2] if index > 1 else None
        following = path.papers[index] if index < len(path.papers) else None
        navigation = []
        if previous:
            navigation.append(
                f'<a href="#step-{index - 1}">← {html.escape(previous.paper.title)}</a>'
            )
        if following:
            navigation.append(
                f'<a href="#step-{index + 1}">{html.escape(following.paper.title)} →</a>'
            )
        steps.append(
            f"""      <li class="reading-step" id="step-{index}">
        <p class="section-number">STEP {index:02d}</p>
        <h2><a href="../../papers/{html.escape(step.slug, quote=True)}/">{html.escape(step.paper.title)}</a></h2>
        <p>{html.escape(step.guide)}</p>
        <div class="reading-step-meta"><span>{step.paper.published_at:%Y-%m-%d}</span><span>{html.escape(step.paper.math_section or 'その他')}</span></div>
        {_step_actions(step, capabilities[step.slug])}
        <nav aria-label="経路内の前後の記事">{' '.join(navigation)}</nav>
      </li>"""
        )
    intro = (
        f'<section class="reading-path-intro">{prerequisite_links}</section>'
        if prerequisite_links
        else ""
    )
    body = f"""    <p class="directory-back"><a href="../">← 読書経路一覧へ</a></p>
    {intro}
    <ol class="reading-path-steps">
{chr(10).join(steps)}
    </ol>"""
    return rendered_exploration_page(
        title=path.title,
        eyebrow="READING PATH",
        description=path.description,
        canonical_path=f"/reading-paths/{path.slug}/",
        body=body,
        prefix="../../",
        body_class="reading-path-page",
    )


def generate_reading_paths(catalog: SiteCatalog, output: Path) -> None:
    paths = load_reading_paths(catalog)
    capabilities = paper_capabilities(catalog)
    target = output / "reading-paths"
    target.mkdir(parents=True)
    cards = "\n".join(_path_card(path) for path in paths)
    body = f"""    <section aria-labelledby="paths-title">
      <div class="section-heading">
        <h2 id="paths-title">用意した経路</h2>
        <p>順番は固定された正解ではなく、原稿群を歩くための案内です。</p>
      </div>
      <div class="explore-grid">
{cards or '        <p>読書経路はまだ登録されていません。</p>'}
      </div>
    </section>"""
    (target / "index.html").write_text(
        rendered_exploration_page(
            title="読書経路",
            eyebrow="CURATED ROUTES",
            description="テーマごとに原稿を読む順番と、各段階で見るべき点をまとめています。",
            canonical_path="/reading-paths/",
            body=body,
        ),
        encoding="utf-8",
    )
    by_slug = {path.slug: path for path in paths}
    for path in paths:
        path_dir = target / path.slug
        path_dir.mkdir()
        (path_dir / "index.html").write_text(
            _rendered_path_page(path, by_slug, capabilities), encoding="utf-8"
        )
    write_json(
        target / "reading-paths.json",
        {
            "schema_version": 1,
            "paths": [
                {
                    "slug": path.slug,
                    "title": path.title,
                    "description": path.description,
                    "prerequisites": list(path.prerequisites),
                    "papers": [
                        {
                            "slug": step.slug,
                            "guide": step.guide,
                            "html_path": capabilities[step.slug].html_path,
                            "statement_count": capabilities[step.slug].statement_count,
                        }
                        for step in path.papers
                    ],
                }
                for path in paths
            ],
        },
    )


def paths_for_paper(catalog: SiteCatalog) -> dict[str, tuple[ReadingPath, ...]]:
    result: dict[str, list[ReadingPath]] = {}
    for path in load_reading_paths(catalog):
        for step in path.papers:
            result.setdefault(step.slug, []).append(path)
    return {slug: tuple(paths) for slug, paths in result.items()}
