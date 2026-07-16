#!/usr/bin/env python3
"""Import, protect, catalog, and stage public LaTeX papers."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(
    os.environ.get("PAPER_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PAPERS_DIR = ROOT / "papers"
INDEX_PATH = ROOT / "index.html"
SEARCH_SCRIPT_PATH = ROOT / "search.js"
PRIVACY_REVIEW_DIR = Path(
    os.environ.get("PAPER_PRIVACY_REVIEW_DIR", ROOT / ".privacy-review")
).resolve()
START_MARKER = "<!-- GENERATED:PAPERS:START -->"
END_MARKER = "<!-- GENERATED:PAPERS:END -->"
DEFAULT_LATEXMKRC = """$latex = 'platex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$pdf_mode = 3;
"""
LATEXMKRC_BY_ENGINE = {"platex": DEFAULT_LATEXMKRC}
DEFAULT_BUILD_ENGINE = "platex"
MATH_SECTIONS = (
    "代数・組合せ",
    "位相・距離・幾何",
    "解析・測度・確率",
    "その他",
)
MATH_SECTION_DETAILS = {
    "代数・組合せ": {
        "slug": "algebra-combinatorics",
        "description": "代数、数論、有限体、組合せ論などの記事をまとめています。",
    },
    "位相・距離・幾何": {
        "slug": "topology-geometry",
        "description": "位相空間、距離空間、幾何、代数的トポロジーなどの記事をまとめています。",
    },
    "解析・測度・確率": {
        "slug": "analysis-probability",
        "description": "解析、複素解析、測度論、確率論などの記事をまとめています。",
    },
    "その他": {
        "slug": "other",
        "description": "上の三分野に収まらない数学記事をまとめています。",
    },
}
SITE_TITLE_TOP = "数識電収"
SITE_TITLE_FORMAL = "数学識電脳界溢出部位封神蔵収"
SITE_TITLE_ATTRIBUTE = "私と放電"
SITE_URL = "https://dempacomm.github.io"
HOME_PAPER_LIMIT = 3
LEGACY_PRIVACY_EXEMPT_SLUGS = {
    "2015-08-28-01",
    "2015-09-01-01",
    "2016-01-09-01",
    "2017-08-01-01",
    "2018-03-29-01",
    "2018-10-14-01",
    "2019-11-29-01",
    "2020-01-30-01",
    "2021-01-28-01",
    "2022-01-03-01",
    "2023-06-20-01",
    "2024-01-03-01",
    "2024-01-08-01",
    "2024-01-13-01",
    "2025-12-28-01",
    "2026-04-21-01",
}


class PaperToolError(RuntimeError):
    pass


PRIVACY_TEX_COMMANDS = (
    "author",
    "email",
    "affiliation",
    "institute",
    "address",
    "thanks",
)
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise PaperToolError(f"unsafe relative path: {value}")
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PaperToolError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise PaperToolError(f"JSON root must be an object: {path}")
    return value


def validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    required = (
        "schema_version",
        "slug",
        "legacy_slugs",
        "title",
        "published_at",
        "sequence",
        "year",
        "kind",
        "summary",
        "original_url",
        "order",
        "tags",
        "keywords",
        "build",
        "files",
        "approved_changes",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise PaperToolError(f"{path}: missing fields: {', '.join(missing)}")
    if manifest["schema_version"] not in {1, 2}:
        raise PaperToolError(f"{path}: unsupported schema_version")
    if (
        manifest["schema_version"] == 1
        and manifest.get("slug") not in LEGACY_PRIVACY_EXEMPT_SLUGS
    ):
        raise PaperToolError(
            f"{path}: schema 1 privacy exemption is limited to migrated legacy papers"
        )
    if path.parent.name != manifest["slug"]:
        raise PaperToolError(f"{path}: slug does not match directory name")
    if not isinstance(manifest["sequence"], int) or manifest["sequence"] < 1:
        raise PaperToolError(f"{path}: sequence must be a positive integer")
    math_section = manifest.get("math_section", "")
    if not isinstance(math_section, str):
        raise PaperToolError(f"{path}: math_section must be a string")
    if math_section.strip() and math_section.strip() not in MATH_SECTIONS:
        raise PaperToolError(
            f"{path}: math_section must be one of: {', '.join(MATH_SECTIONS)}"
        )
    try:
        published = datetime.fromisoformat(str(manifest["published_at"]))
    except ValueError as error:
        raise PaperToolError(f"{path}: published_at must be ISO 8601") from error
    expected_slug = f"{published:%Y-%m-%d}-{manifest['sequence']:02d}"
    if manifest["slug"] != expected_slug:
        raise PaperToolError(
            f"{path}: slug must match published date and sequence ({expected_slug})"
        )
    for field in ("legacy_slugs", "tags", "keywords"):
        values = manifest[field]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise PaperToolError(f"{path}: {field} must be an array of non-empty strings")
        if len(values) != len(set(values)):
            raise PaperToolError(f"{path}: {field} contains duplicates")
    for legacy_slug in manifest["legacy_slugs"]:
        if str(safe_relative_path(legacy_slug)) != legacy_slug or "/" in legacy_slug:
            raise PaperToolError(f"{path}: invalid legacy slug: {legacy_slug}")
    if not isinstance(manifest["files"], list) or not manifest["files"]:
        raise PaperToolError(f"{path}: files must be a non-empty array")
    build = manifest["build"]
    if not isinstance(build, dict) or not isinstance(build.get("enabled"), bool):
        raise PaperToolError(f"{path}: build.enabled is required")
    engine = build.get("engine", "")
    if not isinstance(engine, str):
        raise PaperToolError(f"{path}: build.engine must be a string")
    if engine.strip() and engine.strip() not in LATEXMKRC_BY_ENGINE:
        raise PaperToolError(
            f"{path}: build.engine must be one of: "
            + ", ".join(sorted(LATEXMKRC_BY_ENGINE))
        )
    if build["enabled"] and "root" not in build:
        raise PaperToolError(f"{path}: build.root is required when build is enabled")
    if build["enabled"]:
        safe_relative_path(str(build["root"]))
    seen: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise PaperToolError(f"{path}: every files entry must be an object")
        for key in ("path", "role", "label", "public", "original_sha256", "sha256"):
            if key not in entry:
                raise PaperToolError(f"{path}: file entry missing {key}")
        relative = str(safe_relative_path(str(entry["path"])))
        if relative in seen:
            raise PaperToolError(f"{path}: duplicate file entry: {relative}")
        seen.add(relative)
        for key in ("original_sha256", "sha256"):
            value = entry[key]
            if not isinstance(value, str) or len(value) != 64:
                raise PaperToolError(f"{path}: invalid {key} for {relative}")
    if build["enabled"] and str(build["root"]) not in seen:
        raise PaperToolError(f"{path}: build.root must appear in files")
    if not build["enabled"] and "published.pdf" not in seen and "main.tex" in seen:
        raise PaperToolError(
            f"{path}: source-only papers must not use main.tex; use source.tex"
        )
    if manifest["schema_version"] == 2:
        reviews = manifest.get("privacy_reviews")
        if not isinstance(reviews, list):
            raise PaperToolError(f"{path}: schema 2 requires privacy_reviews")
        expected = {
            entry["path"]: entry["sha256"]
            for entry in manifest["files"]
            if entry["public"] and Path(str(entry["path"])).suffix.casefold() in {".tex", ".pdf"}
        }
        reviewed: dict[str, str] = {}
        for review in reviews:
            if not isinstance(review, dict):
                raise PaperToolError(f"{path}: privacy review must be an object")
            for key in (
                "path",
                "status",
                "reason",
                "source_sha256",
                "inspection_status",
                "recorded_at",
            ):
                if key not in review:
                    raise PaperToolError(f"{path}: privacy review missing {key}")
            relative = str(safe_relative_path(str(review["path"])))
            if relative in reviewed:
                raise PaperToolError(f"{path}: duplicate privacy review for {relative}")
            if review["status"] not in {"reviewed", "overridden"}:
                raise PaperToolError(f"{path}: invalid privacy status for {relative}")
            if review["status"] == "overridden" and not str(review["reason"]).strip():
                raise PaperToolError(f"{path}: privacy override reason is empty for {relative}")
            source_hash = review["source_sha256"]
            if not isinstance(source_hash, str) or len(source_hash) != 64:
                raise PaperToolError(f"{path}: invalid privacy hash for {relative}")
            reviewed[relative] = source_hash
        if reviewed != expected:
            missing_reviews = sorted(set(expected) - set(reviewed))
            extra_reviews = sorted(set(reviewed) - set(expected))
            mismatched = sorted(
                relative
                for relative in set(expected) & set(reviewed)
                if expected[relative] != reviewed[relative]
            )
            details = []
            if missing_reviews:
                details.append("missing: " + ", ".join(missing_reviews))
            if extra_reviews:
                details.append("extra: " + ", ".join(extra_reviews))
            if mismatched:
                details.append("hash mismatch: " + ", ".join(mismatched))
            raise PaperToolError(f"{path}: invalid privacy review coverage ({'; '.join(details)})")


def has_pdf(manifest: dict[str, Any]) -> bool:
    """Return whether staging will provide main.pdf for this paper."""
    if manifest["build"]["enabled"]:
        return True
    return any(entry["path"] == "published.pdf" for entry in manifest["files"])


def public_file_actions(
    manifest: dict[str, Any], prefix: str, indent: str
) -> list[str]:
    """Render PDF/source actions, making a source primary when no PDF exists."""
    actions: list[str] = []
    pdf_available = has_pdf(manifest)
    if pdf_available:
        actions.append(
            f'{indent}<a class="primary-action" href="{prefix}main.pdf">PDFを読む</a>'
        )
    primary_source_added = False
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        relative = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        primary = ""
        if not pdf_available and not primary_source_added and entry["role"] == "manuscript":
            primary = ' class="primary-action"'
            primary_source_added = True
        actions.append(f'{indent}<a{primary} href="{prefix}{relative}">{label}</a>')
    return actions


def manifests(slugs: Iterable[str] | None = None) -> list[tuple[Path, dict[str, Any]]]:
    wanted = set(slugs or [])
    found: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in sorted(PAPERS_DIR.glob("*/paper.json")):
        manifest = load_json(manifest_path)
        validate_manifest(manifest, manifest_path)
        if wanted and manifest["slug"] not in wanted:
            continue
        found.append((manifest_path, manifest))
    if wanted:
        missing = wanted - {manifest["slug"] for _, manifest in found}
        if missing:
            raise PaperToolError(f"unknown paper slug(s): {', '.join(sorted(missing))}")
    if not found:
        raise PaperToolError("no paper manifests found")
    return sorted(found, key=lambda item: (item[1]["order"], item[1]["slug"]))


def verify_one(manifest_path: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    paper_dir = manifest_path.parent
    for entry in manifest["files"]:
        relative = safe_relative_path(entry["path"])
        target = paper_dir / relative
        if not target.is_file():
            errors.append(f"{manifest['slug']}/{relative}: missing")
            continue
        actual = sha256(target)
        if actual != entry["sha256"]:
            errors.append(
                f"{manifest['slug']}/{relative}: SHA-256 mismatch "
                f"(expected {entry['sha256']}, got {actual})"
            )
    return errors


def command_verify(args: argparse.Namespace) -> None:
    errors: list[str] = []
    selected = manifests(args.slugs)
    for manifest_path, manifest in selected:
        paper_errors = verify_one(manifest_path, manifest)
        errors.extend(paper_errors)
        if not paper_errors:
            print(f"OK  {manifest['slug']}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"verification failed with {len(errors)} error(s)")


def command_audit(args: argparse.Namespace) -> None:
    selected = manifests(args.slugs)
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(verify_one(manifest_path, manifest))
        for entry in manifest["files"]:
            state = (
                "original"
                if entry["sha256"] == entry["original_sha256"]
                else "approved-modified"
            )
            print(f"{state:17} {manifest['slug']}/{entry['path']}")
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"audit failed with {len(errors)} error(s)")


def site_navigation(prefix: str, current: str = "") -> str:
    home_href = prefix or "./"
    links = (
        ("home", home_href, "トップ"),
        ("archive", f"{prefix}archive/", "全原稿"),
        ("math", f"{prefix}math/", "数学記事総覧"),
        ("tags", f"{prefix}archive/#tags-title", "タグ索引"),
    )
    rendered = []
    for key, href, label in links:
        current_attribute = ' aria-current="page"' if key == current else ""
        rendered.append(
            f'        <a href="{href}"{current_attribute}>{label}</a>'
        )
    rendered.append(
        '        <a href="https://concious4410.hatenablog.com/">'
        'はてなブログ <span aria-hidden="true">↗</span></a>'
    )
    return "\n".join(rendered)


def page_head(
    title: str,
    description: str,
    canonical_path: str,
    stylesheet: str,
) -> str:
    escaped_title = html.escape(title, quote=True)
    escaped_description = html.escape(description, quote=True)
    canonical = f"{SITE_URL}{canonical_path}"
    return f"""  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <meta name="description" content="{escaped_description}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_TITLE_TOP}">
  <meta property="og:title" content="{escaped_title}">
  <meta property="og:description" content="{escaped_description}">
  <meta property="og:url" content="{canonical}">
  <meta name="twitter:card" content="summary">
  <link rel="alternate" type="application/rss+xml" title="{SITE_TITLE_TOP} RSS" href="{SITE_URL}/feed.xml">
  <link rel="stylesheet" href="{stylesheet}">"""


def paper_card(manifest: dict[str, Any], prefix: str = "") -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    kind = html.escape(manifest["kind"])
    summary = html.escape(manifest["summary"])
    published_date = str(manifest["published_at"])[:10]
    year = int(manifest["year"])
    search_terms = " ".join(
        [
            manifest["title"],
            manifest["summary"],
            manifest["kind"],
            published_date,
            *manifest["tags"],
            *manifest["keywords"],
        ]
    )
    search_attribute = html.escape(search_terms.casefold(), quote=True)
    tags_attribute = html.escape(
        json.dumps(manifest["tags"], ensure_ascii=False), quote=True
    )
    tag_chips = "\n".join(
        f'          <a class="paper-tag" href="{tag_href(tag, prefix)}">{html.escape(tag)}</a>'
        for tag in manifest["tags"]
    )
    actions = public_file_actions(
        manifest, f"{prefix}papers/{slug}/", "          "
    )
    actions.append(
        f'          <a href="{prefix}papers/{slug}/keywords.txt">検索語</a>'
    )
    if manifest["original_url"]:
        original_url = html.escape(manifest["original_url"], quote=True)
        actions.append(f'          <a href="{original_url}">元の記事</a>')
    actions_html = "\n".join(actions)
    aria = html.escape(f"{manifest['title']}のファイル", quote=True)
    year_href = f"#year-{year}" if prefix else f"archive/#year-{year}"
    return f"""      <article class="paper-card" id="paper-{slug}" data-search="{search_attribute}" data-tags="{tags_attribute}" data-year="{year}">
        <div class="paper-meta">
          <span>初出 <a class="paper-year-link" href="{year_href}" aria-label="{year}年の記事一覧">{published_date}</a></span>
          <span>{kind}</span>
        </div>
        <h3><a href="{prefix}papers/{slug}/">{title}</a></h3>
        <p>{summary}</p>
        <div class="paper-tags" aria-label="電波通信のタグ">
{tag_chips}
        </div>
        <nav class="paper-actions" aria-label="{aria}">
{actions_html}
        </nav>
      </article>"""


def grouped_tags(
    selected: list[tuple[Path, dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for _, manifest in selected:
        for tag in manifest["tags"]:
            grouped.setdefault(tag, []).append(manifest)
    return grouped


def tag_href(tag: str, prefix: str = "") -> str:
    return f"{prefix}tags/{quote(tag, safe='')}/"


def rendered_tag_index(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    grouped = grouped_tags(selected)
    return "\n".join(
        f'      <a class="tag-index-item" href="{tag_href(tag)}">'
        f"<span>{html.escape(tag)}</span><span>{len(papers)}件</span></a>"
        for tag, papers in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    )


def rendered_year_groups(
    selected: list[tuple[Path, dict[str, Any]]], prefix: str = ""
) -> str:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for _, manifest in selected:
        grouped.setdefault(int(manifest["year"]), []).append(manifest)

    groups: list[str] = []
    for year in sorted(grouped, reverse=True):
        papers = grouped[year]
        article_links = "\n".join(
            "          <li>"
            f'<a href="{prefix}papers/{html.escape(paper["slug"], quote=True)}/">'
            f'<time datetime="{html.escape(str(paper["published_at"])[:10], quote=True)}">'
            f'{html.escape(str(paper["published_at"])[:10])}</time> '
            f'{html.escape(paper["title"])}</a></li>'
            for paper in papers
        )
        groups.append(
            f"""      <details class="year-group" id="year-{year}">
        <summary><span>{year}年</span><span>{len(papers)}件</span></summary>
        <ul>
{article_links}
        </ul>
      </details>"""
        )
    return "\n\n".join(groups)


def rendered_home_page(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    newest = [manifest for _, manifest in selected[-HOME_PAPER_LIMIT:]][::-1]
    cards = "\n\n".join(paper_card(manifest) for manifest in newest)
    description = (
        f"『{SITE_TITLE_TOP}』の数学原稿、PDF、TeXソースを保存・公開する"
        "数学記事アーカイブです。"
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{SITE_TITLE_TOP} — 数学原稿アーカイブ", description, "/", "styles.css")}
</head>
<body>
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS ARCHIVE</p>
      <h1>{SITE_TITLE_TOP}</h1>
      <p class="subtitle"><span>{SITE_TITLE_FORMAL}</span><span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p>
      <p class="lead">数学記事の原稿と、原稿から生成したPDFを保存・公開するアーカイブです。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("", "home")}
      </nav>
    </div>
  </header>

  <main id="main-content">
    <section class="portal-grid" aria-label="記事を探す">
      <a class="portal-card portal-card-primary" href="archive/">
        <span class="section-number">ALL PAPERS</span>
        <strong>全原稿を検索</strong>
        <span>{len(selected)}件の原稿を、語句・タグ・公開年から探せます。</span>
      </a>
      <a class="portal-card" href="math/">
        <span class="section-number">MATHEMATICS</span>
        <strong>数学記事総覧</strong>
        <span>数学分野ごとの独立した総覧へ案内します。</span>
      </a>
      <a class="portal-card" href="archive/#years-title">
        <span class="section-number">YEARS</span>
        <strong>公開年から探す</strong>
        <span>記事を初出年ごとにたどれます。</span>
      </a>
      <a class="portal-card" href="archive/#tags-title">
        <span class="section-number">TAGS</span>
        <strong>タグから探す</strong>
        <span>電波通信の元タグを引き継いだ索引です。</span>
      </a>
    </section>

    <section class="latest-papers" aria-labelledby="papers-title">
      <div class="section-heading">
        <div>
          <p class="section-number">LATEST</p>
          <h2 id="papers-title">新着原稿</h2>
        </div>
        <p>公開日の新しいものから{len(newest)}件を表示しています。<a href="archive/">全{len(selected)}件を見る</a></p>
      </div>
      <div class="paper-list">
{START_MARKER}
{cards}
    {END_MARKER}
      </div>
    </section>

    <section class="archive-note" aria-labelledby="archive-note-title">
      <p class="section-number">ABOUT</p>
      <h2 id="archive-note-title">このアーカイブについて</h2>
      <p>記事本文への入口に加えて、公開可能なTeX原稿、PDF、BibTeX、図版などを原稿単位で保存しています。元記事は引き続き、はてなブログ「電波通信」から参照できます。</p>
    </section>
  </main>

  <footer>
    <p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p>
  </footer>
</body>
</html>
"""


def rendered_archive_page(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    cards = "\n\n".join(
        paper_card(manifest, "../") for _, manifest in reversed(selected)
    )
    description = (
        f"{SITE_TITLE_TOP}で公開している全{len(selected)}原稿を検索し、"
        "タグと公開年から絞り込める総合アーカイブです。"
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"全原稿アーカイブ — {SITE_TITLE_TOP}", description, "/archive/", "../styles.css")}
</head>
<body class="archive-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">COMPLETE ARCHIVE</p>
      <h1>全原稿アーカイブ</h1>
      <p class="lead">{SITE_TITLE_TOP}で公開している全{len(selected)}原稿を横断検索できます。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "archive")}
      </nav>
    </div>
  </header>

  <main id="main-content">
    <section aria-labelledby="papers-title">
      <div class="section-heading">
        <div>
          <p class="section-number">01</p>
          <h2 id="papers-title">公開原稿を検索</h2>
        </div>
        <p>題名、説明、タグ、検索キーワード、公開年を横断検索します。</p>
      </div>

      <form class="paper-search" role="search" aria-label="公開原稿を絞り込む" onsubmit="return false">
        <label for="paper-query">原稿を検索</label>
        <div class="paper-search-controls">
          <input id="paper-query" type="search" placeholder="タイトル・タグ・キーワード" autocomplete="off">
          <select id="paper-tag" aria-label="電波通信のタグで絞り込む">
            <option value="">すべてのタグ</option>
          </select>
          <select id="paper-year" aria-label="公開年で絞り込む">
            <option value="">すべての年</option>
          </select>
          <button id="paper-reset" type="button">絞り込みを解除</button>
        </div>
        <p id="paper-count" class="paper-count" aria-live="polite"></p>
        <div id="paper-empty" class="paper-empty" hidden>
          <p>条件に一致する原稿はありません。</p>
          <button type="button" data-reset-papers>絞り込みを解除</button>
        </div>
      </form>

      <div class="paper-list">
{cards}
      </div>
    </section>

    <section class="year-directory" aria-labelledby="years-title">
      <div class="section-heading">
        <div>
          <p class="section-number">02</p>
          <h2 id="years-title">公開年別記事一覧</h2>
        </div>
        <p>公開年ごとに原稿をまとめています。</p>
      </div>
      <div class="year-groups">
{rendered_year_groups(selected, "../")}
      </div>
    </section>

    <section class="tag-directory" aria-labelledby="tags-title">
      <div class="section-heading">
        <div>
          <p class="section-number">03</p>
          <h2 id="tags-title">タグ索引</h2>
        </div>
        <p>タグを選ぶと、公開年ごとにまとめた専用ページへ移動します。</p>
      </div>
      <nav class="tag-index" aria-label="タグ索引">
{rendered_tag_index(selected).replace('href="tags/', 'href="../tags/')}
      </nav>
    </section>
  </main>

  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
  <script src="../search.js"></script>
</body>
</html>
"""


def rendered_tag_page_paper(manifest: dict[str, Any]) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    published_date = html.escape(str(manifest["published_at"])[:10])
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    kind = html.escape(manifest["kind"])
    year = int(manifest["year"])
    tag_chips = "\n".join(
        f'            <a class="paper-tag" href="../{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    actions = public_file_actions(
        manifest, f"../../papers/{slug}/", "            "
    )
    if manifest["original_url"]:
        original_url = html.escape(manifest["original_url"], quote=True)
        actions.append(f'            <a href="{original_url}">元の記事</a>')
    return f"""        <article class="tag-page-paper">
          <div class="paper-meta"><span>初出 <a class="paper-year-link" href="../../archive/#year-{year}" aria-label="{year}年の記事一覧">{published_date}</a></span><span>{kind}</span></div>
          <h3><a href="../../papers/{slug}/">{title}</a></h3>
          <p>{summary}</p>
          <div class="paper-tags" aria-label="電波通信のタグ">
{tag_chips}
          </div>
          <nav class="paper-actions" aria-label="{html.escape(manifest['title'], quote=True)}のファイル">
{chr(10).join(actions)}
          </nav>
        </article>"""


def rendered_tag_page(tag: str, papers: list[dict[str, Any]]) -> str:
    by_year: dict[int, list[dict[str, Any]]] = {}
    for paper in papers:
        by_year.setdefault(int(paper["year"]), []).append(paper)
    year_sections = "\n".join(
        f"""      <section class="tag-year-section" aria-labelledby="year-{year}">
        <h2 id="year-{year}">{year}年 <span>{len(year_papers)}件</span></h2>
        <div class="tag-page-papers">
{chr(10).join(rendered_tag_page_paper(paper) for paper in year_papers)}
        </div>
      </section>"""
        for year, year_papers in sorted(by_year.items(), reverse=True)
    )
    escaped_tag = html.escape(tag)
    description = f"電波通信のタグ「{tag}」が付いた公開原稿の一覧です。"
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{tag}の記事 — {SITE_TITLE_TOP}", description, f"/tags/{quote(tag, safe='')}/", "../../styles.css")}
</head>
<body class="tag-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">TAG ARCHIVE</p>
      <h1>{escaped_tag}</h1>
      <p class="lead">電波通信でこのタグが付けられていた公開原稿、全{len(papers)}件。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../", "tags")}
      </nav>
    </div>
  </header>
  <main id="main-content">
{year_sections}
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_math_index_item(
    manifest: dict[str, Any], prefix: str = "../"
) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = html.escape(str(manifest["published_at"])[:10])
    file_links = (
        [f'<a href="{prefix}papers/{slug}/main.pdf">PDF</a>']
        if has_pdf(manifest)
        else []
    )
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        path = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        file_links.append(f'<a href="{prefix}papers/{slug}/{path}">{label}</a>')
    tag_links = "\n".join(
        f'              <a class="paper-tag" href="{prefix}tags/{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    return f"""          <li class="math-index-item">
            <h3><a href="{prefix}papers/{slug}/">{title}</a></h3>
            <p>{summary}</p>
            <div class="math-index-meta">
              <time datetime="{published_date}">{published_date}</time>
              <span>{' · '.join(file_links)}</span>
            </div>
            <div class="math-index-tags" aria-label="電波通信のタグ">
{tag_links}
            </div>
          </li>"""


def grouped_math_sections(
    selected: list[tuple[Path, dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {section: [] for section in MATH_SECTIONS}
    for _, manifest in selected:
        section = str(manifest.get("math_section", "")).strip() or "その他"
        grouped[section].append(manifest)
    return grouped


def representative_math_tags(papers: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for paper in papers:
        for tag in paper["tags"]:
            if tag == "数学":
                continue
            counts[tag] = counts.get(tag, 0) + 1
    return [
        tag
        for tag, _ in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]


def rendered_math_page(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    grouped = grouped_math_sections(selected)
    directory_cards = "\n".join(
        f"""      <a class="math-directory-card" href="{MATH_SECTION_DETAILS[section]['slug']}/">
        <span class="section-number">{index:02d}</span>
        <strong>{html.escape(section)}</strong>
        <span>{html.escape(MATH_SECTION_DETAILS[section]['description'])}</span>
        <span class="math-directory-count">{len(grouped[section])}件</span>
        <span class="math-directory-tags">{
            " · ".join(html.escape(tag) for tag in representative_math_tags(grouped[section]))
            or "記事の追加待ち"
        }</span>
      </a>"""
        for index, section in enumerate(MATH_SECTIONS, start=1)
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"数学記事総覧 — {SITE_TITLE_TOP}", f"{SITE_TITLE_TOP}の数学記事を分野別総覧へ案内する総合目次です。", "/math/", "../styles.css")}
</head>
<body class="math-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS DIRECTORY</p>
      <h1>数学記事総覧</h1>
      <p class="lead">分野別総覧への入口です。現在公開している全{len(selected)}原稿を、四つの主分類からたどれます。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../", "math")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <nav class="math-directory-grid" aria-label="数学分野別総覧">
{directory_cards}
    </nav>
    <section class="archive-note" aria-labelledby="math-guide-title">
      <p class="section-number">GUIDE</p>
      <h2 id="math-guide-title">分類について</h2>
      <p>各原稿は主分類を一つ持ちます。分野別ページでは公開年ごとの一覧と、電波通信から引き継いだタグを併記しています。</p>
    </section>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_math_section_page(
    section: str, papers: list[dict[str, Any]]
) -> str:
    details = MATH_SECTION_DETAILS[section]
    by_year: dict[int, list[dict[str, Any]]] = {}
    for paper in papers:
        by_year.setdefault(int(paper["year"]), []).append(paper)
    if by_year:
        year_sections = "\n".join(
            f"""      <section class="math-index-section" aria-labelledby="year-{year}">
        <div class="math-index-heading">
          <h2 id="year-{year}">{year}年</h2>
          <span>{len(year_papers)}件</span>
        </div>
        <ul class="math-index-list">
{chr(10).join(rendered_math_index_item(paper, "../../") for paper in reversed(year_papers))}
        </ul>
      </section>"""
            for year, year_papers in sorted(by_year.items(), reverse=True)
        )
    else:
        year_sections = """      <section class="math-empty">
        <p>この分野には、まだ公開原稿がありません。</p>
        <a href="../../archive/">全原稿アーカイブを見る</a>
      </section>"""
    description = str(details["description"])
    slug = str(details["slug"])
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{section}の記事総覧 — {SITE_TITLE_TOP}", description, f"/math/{slug}/", "../../styles.css")}
</head>
<body class="math-page math-section-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">MATHEMATICS SECTION</p>
      <h1>{html.escape(section)}</h1>
      <p class="lead">{html.escape(description)} 現在{len(papers)}件です。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../", "math")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <p class="directory-back"><a href="../">数学記事総覧へ戻る</a></p>
{year_sections}
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_paper_page(manifest: dict[str, Any]) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = html.escape(str(manifest["published_at"])[:10])
    kind = html.escape(manifest["kind"])
    year = int(manifest["year"])
    tag_chips = "\n".join(
        f'          <a class="paper-tag" href="../../tags/{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    keyword_chips = "\n".join(
        f'          <span class="keyword-chip">{html.escape(keyword)}</span>'
        for keyword in manifest["keywords"]
    )
    actions = public_file_actions(manifest, "", "          ")
    actions.append('          <a href="keywords.txt">検索語テキスト</a>')
    if manifest["original_url"]:
        original_url = html.escape(manifest["original_url"], quote=True)
        actions.append(f'          <a href="{original_url}">電波通信の元記事</a>')
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"{manifest['title']} — {SITE_TITLE_TOP}", manifest["summary"], f"/papers/{slug}/", "../../styles.css")}
</head>
<body class="paper-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">PUBLIC MANUSCRIPT</p>
      <h1>{title}</h1>
      <p class="lead">{summary}</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("../../")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <article class="paper-detail">
      <div class="paper-meta">
        <span>初出 <a class="paper-year-link" href="../../archive/#year-{year}" aria-label="{year}年の記事一覧">{published_date}</a></span>
        <span>{kind}</span>
        <span>原稿番号 {slug}</span>
      </div>
      <section aria-labelledby="files-title">
        <p class="section-number">FILES</p>
        <h2 id="files-title">公開ファイル</h2>
        <nav class="paper-actions" aria-label="{html.escape(manifest['title'], quote=True)}の公開ファイル">
{chr(10).join(actions)}
        </nav>
      </section>
      <section aria-labelledby="paper-tags-title">
        <p class="section-number">TAGS</p>
        <h2 id="paper-tags-title">電波通信のタグ</h2>
        <div class="paper-tags">
{tag_chips}
        </div>
      </section>
      <section aria-labelledby="keywords-title">
        <p class="section-number">KEYWORDS</p>
        <h2 id="keywords-title">検索キーワード</h2>
        <div class="keyword-list">
{keyword_chips}
        </div>
      </section>
    </article>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_index() -> str:
    return rendered_home_page(manifests())


def command_catalog(args: argparse.Namespace) -> None:
    rendered = rendered_index()
    current = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        stale_keywords: list[str] = []
        for manifest_path, manifest in manifests():
            target = manifest_path.parent / "keywords.txt"
            if not target.is_file() or target.read_text(encoding="utf-8") != rendered_keywords(manifest):
                stale_keywords.append(manifest["slug"])
        if rendered != current:
            raise PaperToolError("index.html is not synchronized with paper.json files")
        if stale_keywords:
            raise PaperToolError(
                "keywords.txt is not synchronized for: " + ", ".join(stale_keywords)
            )
        print("OK  index.html catalog")
        return
    INDEX_PATH.write_text(rendered, encoding="utf-8")
    for manifest_path, manifest in manifests():
        (manifest_path.parent / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
    print("WROTE index.html and keywords.txt files")


def rendered_keywords(manifest: dict[str, Any]) -> str:
    lines = [
        "# タイトル",
        manifest["title"],
        "",
        "# 電波通信のタグ",
        *manifest["tags"],
        "",
        "# 検索キーワード",
        *manifest["keywords"],
        "",
    ]
    return "\n".join(lines)


def rendered_not_found_page() -> str:
    description = "指定されたページは見つかりませんでした。数識電収の各索引から原稿を探せます。"
    return f"""<!doctype html>
<html lang="ja">
<head>
{page_head(f"ページが見つかりません — {SITE_TITLE_TOP}", description, "/404.html", "/styles.css")}
  <meta name="robots" content="noindex">
</head>
<body class="not-found-page">
  <a class="skip-link" href="#main-content">本文へ移動</a>
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">404 NOT FOUND</p>
      <h1>ページが見つかりません</h1>
      <p class="lead">URLが変更されたか、原稿がまだ公開されていないようです。別の入口から探してみてください。</p>
      <nav class="site-navigation" aria-label="主要ページ">
{site_navigation("/", "")}
      </nav>
    </div>
  </header>
  <main id="main-content">
    <section class="not-found-guide">
      <p class="section-number">WAYFINDER</p>
      <h2>原稿への入口</h2>
      <p>題名やキーワードが分かる場合は全原稿検索、数学分野からたどる場合は数学記事総覧が便利です。</p>
      <nav class="paper-actions" aria-label="ページが見つからないときの案内">
        <a class="primary-action" href="/archive/">全原稿を検索</a>
        <a href="/">トップへ戻る</a>
        <a href="/math/">数学記事総覧</a>
        <a href="/archive/#tags-title">タグ索引</a>
      </nav>
    </section>
  </main>
  <footer><p>{SITE_TITLE_TOP} — {SITE_TITLE_FORMAL} <span class="title-attribute">{SITE_TITLE_ATTRIBUTE}</span></p></footer>
</body>
</html>
"""


def rendered_feed(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    items = []
    for _, manifest in reversed(selected):
        published = datetime.fromisoformat(str(manifest["published_at"]))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        slug = quote(str(manifest["slug"]), safe="")
        url = f"{SITE_URL}/papers/{slug}/"
        items.append(
            f"""    <item>
      <title>{xml_escape(str(manifest["title"]))}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{format_datetime(published)}</pubDate>
      <description>{xml_escape(str(manifest["summary"]))}</description>
    </item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{SITE_TITLE_TOP}</title>
    <link>{SITE_URL}/</link>
    <description>{SITE_TITLE_TOP}で公開する数学原稿とPDFの更新情報</description>
    <language>ja</language>
{chr(10).join(items)}
  </channel>
</rss>
"""


def rendered_sitemap(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    urls: list[tuple[str, str | None]] = [
        (f"{SITE_URL}/", None),
        (f"{SITE_URL}/archive/", None),
        (f"{SITE_URL}/math/", None),
    ]
    for section in MATH_SECTIONS:
        section_slug = MATH_SECTION_DETAILS[section]["slug"]
        urls.append((f"{SITE_URL}/math/{section_slug}/", None))
    for tag in grouped_tags(selected):
        urls.append((f"{SITE_URL}/tags/{quote(tag, safe='')}/", None))
    for _, manifest in selected:
        urls.append(
            (
                f"{SITE_URL}/papers/{quote(str(manifest['slug']), safe='')}/",
                str(manifest["published_at"])[:10],
            )
        )
    entries = []
    for location, last_modified in urls:
        lastmod = f"\n    <lastmod>{last_modified}</lastmod>" if last_modified else ""
        entries.append(
            f"""  <url>
    <loc>{xml_escape(location)}</loc>{lastmod}
  </url>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(entries)}
</urlset>
"""


class LocalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)
        attribute = "href" if tag in {"a", "link"} else "src" if tag == "script" else ""
        if not attribute:
            return
        for key, value in attrs:
            if key == attribute and value:
                self.links.append(value)


def local_link_errors(site_root: Path) -> list[str]:
    errors: list[str] = []
    page_ids: dict[Path, set[str]] = {}
    for page in sorted(site_root.rglob("*.html")):
        parser = LocalLinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        page_ids[page.resolve()] = parser.ids
        for raw_link in parser.links:
            parsed = urlsplit(raw_link)
            if parsed.scheme or parsed.netloc or raw_link.startswith(("mailto:", "tel:")):
                continue
            decoded_path = unquote(parsed.path)
            if not decoded_path:
                target = page
            elif decoded_path.startswith("/"):
                target = site_root / decoded_path.lstrip("/")
            else:
                target = page.parent / decoded_path
            if decoded_path.endswith("/"):
                target /= "index.html"
            target = target.resolve()
            try:
                target.relative_to(site_root.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(site_root)}: unsafe link {raw_link}")
                continue
            if not target.is_file():
                errors.append(
                    f"{page.relative_to(site_root)}: missing target {raw_link}"
                )
                continue
            if parsed.fragment and target.suffix.casefold() == ".html":
                target_ids = page_ids.get(target)
                if target_ids is None:
                    target_parser = LocalLinkParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                    target_ids = target_parser.ids
                    page_ids[target] = target_ids
                fragment = unquote(parsed.fragment)
                if fragment not in target_ids:
                    errors.append(
                        f"{page.relative_to(site_root)}: missing fragment {raw_link}"
                    )
    return errors


def command_check_links(args: argparse.Namespace) -> None:
    site_root = Path(args.site).resolve()
    if not site_root.is_dir():
        raise PaperToolError(f"site directory does not exist: {site_root}")
    errors = local_link_errors(site_root)
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(f"link check failed with {len(errors)} error(s)")
    print(f"OK  links in {site_root}")


def command_stage(args: argparse.Namespace) -> None:
    selected = manifests()
    errors: list[str] = []
    for manifest_path, manifest in selected:
        errors.extend(verify_one(manifest_path, manifest))
    if errors:
        for error in errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError("refusing to stage files that failed verification")
    if rendered_index() != INDEX_PATH.read_text(encoding="utf-8"):
        raise PaperToolError("refusing to stage a stale index.html")
    for manifest_path, manifest in selected:
        keyword_path = manifest_path.parent / "keywords.txt"
        if (
            not keyword_path.is_file()
            or keyword_path.read_text(encoding="utf-8") != rendered_keywords(manifest)
        ):
            raise PaperToolError(
                f"refusing to stage stale keywords.txt for {manifest['slug']}"
            )

    output = Path(args.output).resolve()
    if output == ROOT or output in ROOT.parents:
        raise PaperToolError("stage output must not be the repository or one of its parents")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copy2(INDEX_PATH, output / "index.html")
    shutil.copy2(ROOT / "styles.css", output / "styles.css")
    shutil.copy2(SEARCH_SCRIPT_PATH, output / "search.js")
    archive_dir = output / "archive"
    archive_dir.mkdir()
    (archive_dir / "index.html").write_text(
        rendered_archive_page(selected), encoding="utf-8"
    )
    (output / "404.html").write_text(
        rendered_not_found_page(), encoding="utf-8"
    )
    (output / "feed.xml").write_text(
        rendered_feed(selected), encoding="utf-8"
    )
    (output / "sitemap.xml").write_text(
        rendered_sitemap(selected), encoding="utf-8"
    )
    (output / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )

    for manifest_path, manifest in selected:
        source_dir = manifest_path.parent
        target_dir = output / "papers" / manifest["slug"]
        target_dir.mkdir(parents=True)
        shutil.copy2(manifest_path, target_dir / "paper.json")
        shutil.copy2(source_dir / "keywords.txt", target_dir / "keywords.txt")
        readme = source_dir / "README.md"
        if readme.is_file():
            shutil.copy2(readme, target_dir / "README.md")
        for entry in manifest["files"]:
            if not entry["public"]:
                continue
            relative = safe_relative_path(entry["path"])
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / relative, target)
        if manifest["build"]["enabled"]:
            pdf = source_dir / "main.pdf"
            if not pdf.is_file():
                raise PaperToolError(f"generated PDF is missing: {pdf}")
            shutil.copy2(pdf, target_dir / "main.pdf")
        elif has_pdf(manifest):
            shutil.copy2(source_dir / "published.pdf", target_dir / "main.pdf")
        (target_dir / "index.html").write_text(
            rendered_paper_page(manifest), encoding="utf-8"
        )
        for legacy_slug in manifest["legacy_slugs"]:
            legacy_dir = output / "papers" / legacy_slug
            if legacy_dir.exists():
                raise PaperToolError(f"legacy slug collision: {legacy_slug}")
            shutil.copytree(target_dir, legacy_dir)

    for tag, papers in grouped_tags(selected).items():
        if tag in {".", ".."} or "/" in tag or "\0" in tag:
            raise PaperToolError(f"tag cannot be used as a page path: {tag!r}")
        tag_dir = output / "tags" / tag
        tag_dir.mkdir(parents=True)
        (tag_dir / "index.html").write_text(
            rendered_tag_page(tag, papers), encoding="utf-8"
        )
    math_dir = output / "math"
    math_dir.mkdir()
    (math_dir / "index.html").write_text(
        rendered_math_page(selected), encoding="utf-8"
    )
    for section, papers in grouped_math_sections(selected).items():
        section_dir = math_dir / str(MATH_SECTION_DETAILS[section]["slug"])
        section_dir.mkdir()
        (section_dir / "index.html").write_text(
            rendered_math_section_page(section, papers), encoding="utf-8"
        )
    link_errors = local_link_errors(output)
    if link_errors:
        for error in link_errors:
            print(f"ERR {error}", file=sys.stderr)
        raise PaperToolError(
            f"refusing to publish a site with {len(link_errors)} broken link(s)"
        )
    print(f"STAGED {len(selected)} papers in {output}")


def resolve_source_dir(spec_path: Path, spec: dict[str, Any]) -> Path:
    raw_value = spec.get("source_dir")
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise PaperToolError("spec.source_dir is required")
    raw = Path(raw_value)
    return (raw if raw.is_absolute() else spec_path.parent / raw).resolve()


def extracted_tex_title(source: str) -> str:
    """Extract a conservative plain-text title from a TeX title command."""
    match = re.search(r"\\title\s*\{", source)
    if not match:
        return ""
    start = match.end()
    depth = 1
    escaped = False
    end = start
    for end in range(start, len(source)):
        character = source[end]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                break
    if depth != 0:
        return ""
    title = source[start:end]
    previous = None
    while title != previous:
        previous = title
        title = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", title)
    title = re.sub(r"\\[A-Za-z@]+\*?", "", title)
    title = title.replace("~", " ").replace("{", "").replace("}", "")
    return " ".join(title.split()).strip()


def next_sequence_for_date(published: datetime) -> int:
    used: list[int] = []
    for manifest_path in sorted(PAPERS_DIR.glob("*/paper.json")):
        manifest = load_json(manifest_path)
        validate_manifest(manifest, manifest_path)
        if str(manifest["published_at"])[:10] == f"{published:%Y-%m-%d}":
            used.append(int(manifest["sequence"]))
    return max(used, default=0) + 1


def privacy_review_path(source: Path) -> Path:
    return PRIVACY_REVIEW_DIR / sha256(source)


def privacy_findings(text: str, file_type: str) -> list[str]:
    findings: list[str] = []
    for email in sorted(set(EMAIL_PATTERN.findall(text))):
        findings.append(f"email candidate: {email}")
    if file_type == "tex":
        for command in PRIVACY_TEX_COMMANDS:
            pattern = re.compile(rf"\\{command}\s*\{{([^{{}}]*)\}}", re.IGNORECASE)
            for value in pattern.findall(text):
                compact = " ".join(value.split())
                findings.append(f"\\{command} candidate: {compact or '(empty)'}")
    else:
        metadata_pattern = re.compile(
            r"^(Author|Creator|Subject|Keywords):\s*(.+)$", re.MULTILINE | re.IGNORECASE
        )
        for key, value in metadata_pattern.findall(text):
            findings.append(f"PDF metadata {key}: {' '.join(value.split())}")
    for label in ("氏名", "著者", "所属", "住所", "電話", "連絡先"):
        if label in text:
            findings.append(f"personal-information label found: {label}")
    return list(dict.fromkeys(findings))


def optional_pdf_text(source: Path) -> tuple[str, list[str]]:
    notes: list[str] = []
    collected: list[str] = []
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        completed = subprocess.run(
            [pdfinfo, str(source)],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if completed.returncode == 0:
            collected.append(completed.stdout)
        else:
            notes.append("pdfinfo could not read metadata")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        completed = subprocess.run(
            [pdftotext, str(source), "-"],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if completed.returncode == 0:
            collected.append(completed.stdout)
            return "\n".join(collected), notes
        notes.append("pdftotext could not extract text")
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(source)
        metadata = reader.metadata or {}
        metadata_text = "\n".join(
            f"{key}: {value}" for key, value in metadata.items() if value
        )
        page_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        collected.extend([metadata_text, page_text])
        return "\n".join(collected), notes
    except Exception:
        if not collected:
            notes.append("PDF text and metadata extraction were unavailable")
        else:
            notes.append("PDF page text extraction was unavailable")
        return "\n".join(collected), notes


def render_pdf_review(source: Path, output: Path) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise PaperToolError(
            "PDF privacy review requires pdftoppm (Poppler) to render every page"
        )
    prefix = output / "page"
    completed = subprocess.run(
        [pdftoppm, "-png", "-r", "120", str(source), str(prefix)],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    pages = sorted(output.glob("page-*.png"))
    unsafe_render_messages = (
        "missing language pack",
        "unknown font",
        "no font in show",
        "couldn't find a font",
        "fontconfig error",
    )
    render_log = f"{completed.stdout}\n{completed.stderr}".casefold()
    if any(message in render_log for message in unsafe_render_messages):
        raise PaperToolError(
            "PDF rendering reported missing fonts; generated images may omit personal "
            "information, so privacy review cannot be approved"
        )
    if completed.returncode != 0 or not pages:
        raise PaperToolError(
            "PDF page rendering failed; the file must be reviewed visually before import"
        )
    return pages


def command_inspect_file(args: argparse.Namespace) -> None:
    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"file does not exist: {source}")
    suffix = source.suffix.casefold()
    if suffix not in {".tex", ".pdf"}:
        raise PaperToolError("inspect-file supports only .tex and .pdf files")
    output = privacy_review_path(source)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    notes: list[str] = []
    rendered_pages: list[Path] = []
    if suffix == ".tex":
        text = source.read_text(encoding="utf-8", errors="replace")
        file_type = "tex"
    else:
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PaperToolError(f"file does not have a PDF header: {source}")
        file_type = "pdf"
        text, notes = optional_pdf_text(source)
        try:
            rendered_pages = render_pdf_review(source, output)
        except PaperToolError as error:
            failure_report = {
                "schema_version": 1,
                "sha256": sha256(source),
                "source_name": source.name,
                "file_type": file_type,
                "findings": privacy_findings(text, file_type),
                "notes": notes,
                "rendered_pages": [],
                "manual_review_required": True,
                "inspection_status": "failed",
                "inspection_error": str(error),
            }
            write_json(output / "report.json", failure_report)
            (output / "extracted.txt").write_text(text, encoding="utf-8")
            (output / "report.txt").write_text(
                f"File: {source}\nSHA-256: {failure_report['sha256']}\n"
                f"Inspection failed: {error}\n"
                "Import is blocked unless --privacy-override with a reason is used.\n",
                encoding="utf-8",
            )
            raise
        (output / "extracted.txt").write_text(text, encoding="utf-8")
    findings = privacy_findings(text, file_type)
    report = {
        "schema_version": 1,
        "sha256": sha256(source),
        "source_name": source.name,
        "file_type": file_type,
        "findings": findings,
        "notes": notes,
        "rendered_pages": [page.name for page in rendered_pages],
        "manual_review_required": True,
        "inspection_status": "completed",
    }
    write_json(output / "report.json", report)
    report_lines = [
        f"File: {source}",
        f"SHA-256: {report['sha256']}",
        f"Type: {file_type}",
        "",
        "Automatic findings:",
        *(f"- {finding}" for finding in findings),
    ]
    if not findings:
        report_lines.append("- none detected (this does not prove the file is safe)")
    report_lines.extend(f"- note: {note}" for note in notes)
    report_lines.extend(
        [
            "",
            "Manual review is mandatory.",
            "For PDF, inspect every page PNG in this directory.",
            "Check author names, real names, email, affiliation, address, and metadata.",
        ]
    )
    (output / "report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"PRIVACY REVIEW FILES: {output}")
    for finding in findings:
        print(f"WARN {finding}")
    print("MANUAL REVIEW REQUIRED before using --privacy-reviewed")


def require_privacy_review(
    source: Path, acknowledged: bool, override_reason: str | None
) -> dict[str, Any]:
    review_dir = privacy_review_path(source)
    report_path = review_dir / "report.json"
    if not report_path.is_file():
        raise PaperToolError(
            f"run inspect-file first: python3 scripts/paper_tool.py inspect-file {source}"
        )
    report = load_json(report_path)
    if report.get("sha256") != sha256(source):
        raise PaperToolError("privacy review is stale; run inspect-file again")
    expected_type = source.suffix.casefold().removeprefix(".")
    if (
        report.get("schema_version") != 1
        or report.get("file_type") != expected_type
        or report.get("manual_review_required") is not True
    ):
        raise PaperToolError("privacy review report is invalid; run inspect-file again")
    reason = (override_reason or "").strip()
    if override_reason is not None and not reason:
        raise PaperToolError("--privacy-override requires a non-empty reason")
    if acknowledged and override_reason is not None:
        raise PaperToolError(
            "use either --privacy-reviewed or --privacy-override, not both"
        )
    if reason:
        return {
            "status": "overridden",
            "reason": reason,
            "source_sha256": report["sha256"],
            "inspection_status": str(report.get("inspection_status", "unknown")),
            "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
    if report.get("inspection_status") != "completed":
        raise PaperToolError(
            "privacy inspection failed; rerun in a working environment or use "
            "--privacy-override \"reason\""
        )
    if expected_type == "pdf":
        pages = report.get("rendered_pages")
        if (
            not isinstance(pages, list)
            or not pages
            or any(
                not isinstance(page, str)
                or not (review_dir / safe_relative_path(page)).is_file()
                for page in pages
            )
        ):
            raise PaperToolError(
                "PDF privacy review images are missing; run inspect-file again"
            )
    if not acknowledged:
        raise PaperToolError(
            "manual privacy review is required; after reviewing the report and every "
            "PDF page, rerun with --privacy-reviewed"
        )
    return {
        "status": "reviewed",
        "reason": "",
        "source_sha256": report["sha256"],
        "inspection_status": "completed",
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def privacy_review_for_path(review: dict[str, Any], target: Path) -> dict[str, Any]:
    return {"path": str(target), **review}


def command_import_tex(args: argparse.Namespace) -> None:
    """Create a guaranteed-publishable source-only paper from one TeX file."""
    source = Path(args.tex_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"TeX file does not exist: {source}")
    if source.suffix.casefold() != ".tex":
        raise PaperToolError(f"expected a .tex file: {source}")
    privacy_review = require_privacy_review(
        source, args.privacy_reviewed, args.privacy_override
    )
    try:
        source_text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise PaperToolError(f"cannot read TeX file: {source}: {error}") from error

    if args.published_at:
        try:
            published = datetime.fromisoformat(args.published_at)
        except ValueError as error:
            raise PaperToolError("--published-at must be ISO 8601") from error
        published_at = args.published_at
    else:
        published = datetime.now().astimezone().replace(microsecond=0)
        published_at = published.isoformat()
    sequence = args.sequence or next_sequence_for_date(published)
    if sequence < 1:
        raise PaperToolError("--sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    title = (args.title or extracted_tex_title(source_text) or source.stem).strip()
    if not title:
        title = "無題のTeX原稿"
    target_name = "source.tex"
    try:
        destination.mkdir(parents=True)
        target = destination / target_name
        shutil.copy2(source, target)
        source_hash = sha256(source)
        if sha256(target) != source_hash:
            raise PaperToolError(f"copy verification failed: {source}")
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "legacy_slugs": [],
            "title": title,
            "published_at": published_at,
            "sequence": sequence,
            "year": published.year,
            "kind": "TeX原稿",
            "math_section": "",
            "summary": "TeX原稿を公開しています。",
            "original_url": args.original_url or "",
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": ["数学"],
            "keywords": [title],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": target_name,
                    "role": "manuscript",
                    "label": "TeXソース",
                    "public": True,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [privacy_review_for_path(privacy_review, Path(target_name))],
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, manifest)
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(f"IMPORTED {slug} as a source-only paper with byte-identical TeX")


def command_import_pdf(args: argparse.Namespace) -> None:
    """Create a publishable paper from one byte-protected PDF file."""
    source = Path(args.pdf_file).expanduser().resolve()
    if not source.is_file():
        raise PaperToolError(f"PDF file does not exist: {source}")
    if source.suffix.casefold() != ".pdf":
        raise PaperToolError(f"expected a .pdf file: {source}")
    privacy_review = require_privacy_review(
        source, args.privacy_reviewed, args.privacy_override
    )
    try:
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PaperToolError(f"file does not have a PDF header: {source}")
    except OSError as error:
        raise PaperToolError(f"cannot read PDF file: {source}: {error}") from error

    if args.published_at:
        try:
            published = datetime.fromisoformat(args.published_at)
        except ValueError as error:
            raise PaperToolError("--published-at must be ISO 8601") from error
        published_at = args.published_at
    else:
        published = datetime.now().astimezone().replace(microsecond=0)
        published_at = published.isoformat()
    sequence = args.sequence or next_sequence_for_date(published)
    if sequence < 1:
        raise PaperToolError("--sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    title = (args.title or source.stem).strip() or "無題のPDF原稿"
    target_name = "published.pdf"
    try:
        destination.mkdir(parents=True)
        target = destination / target_name
        shutil.copy2(source, target)
        source_hash = sha256(source)
        if sha256(target) != source_hash:
            raise PaperToolError(f"copy verification failed: {source}")
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "legacy_slugs": [],
            "title": title,
            "published_at": published_at,
            "sequence": sequence,
            "year": published.year,
            "kind": "PDF原稿",
            "math_section": "",
            "summary": "PDF原稿を公開しています。",
            "original_url": args.original_url or "",
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": ["数学"],
            "keywords": [title],
            "build": {"enabled": False, "engine": ""},
            "files": [
                {
                    "path": target_name,
                    "role": "published-pdf",
                    "label": "",
                    "public": True,
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            ],
            "approved_changes": [],
            "privacy_reviews": [privacy_review_for_path(privacy_review, Path(target_name))],
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, manifest)
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(f"IMPORTED {slug} with a byte-identical published PDF")


def command_import(args: argparse.Namespace) -> None:
    spec_path = Path(args.spec).resolve()
    spec = load_json(spec_path)
    required = (
        "title",
        "kind",
        "summary",
        "original_url",
        "published_at",
        "sequence",
        "tags",
        "keywords",
        "files",
    )
    missing = [key for key in required if key not in spec]
    if missing:
        raise PaperToolError(f"import spec missing fields: {', '.join(missing)}")
    try:
        published = datetime.fromisoformat(str(spec["published_at"]))
    except ValueError as error:
        raise PaperToolError("spec.published_at must be ISO 8601") from error
    sequence = int(spec["sequence"])
    if sequence < 1:
        raise PaperToolError("spec.sequence must be a positive integer")
    slug = f"{published:%Y-%m-%d}-{sequence:02d}"
    source_dir = resolve_source_dir(spec_path, spec)
    if not source_dir.is_dir():
        raise PaperToolError(f"source_dir does not exist: {source_dir}")
    destination = PAPERS_DIR / slug
    if destination.exists():
        raise PaperToolError(f"destination already exists: {destination}")

    reviewed_flag = bool(args.privacy_reviewed or spec.get("privacy_reviewed", False))
    override_value = (
        args.privacy_override
        if args.privacy_override is not None
        else spec.get("privacy_override")
    )
    if override_value is not None and not isinstance(override_value, str):
        raise PaperToolError("privacy_override must be a string")
    prepared_files: list[tuple[dict[str, Any], Path, Path]] = []
    privacy_reviews: list[dict[str, Any]] = []
    print("PUBLIC FILES TO IMPORT:")
    for entry in spec["files"]:
        source_relative = safe_relative_path(str(entry["source"]))
        target_relative = safe_relative_path(str(entry["path"]))
        source = (source_dir / source_relative).resolve()
        try:
            source.relative_to(source_dir)
        except ValueError as error:
            raise PaperToolError(f"source escapes source_dir: {source}") from error
        if not source.is_file():
            raise PaperToolError(f"source file does not exist: {source}")
        is_public = bool(entry.get("public", True))
        if is_public:
            print(f"- {target_relative} ({entry.get('role', 'file')})")
        if is_public and target_relative.suffix.casefold() in {".tex", ".pdf"}:
            review = require_privacy_review(source, reviewed_flag, override_value)
            privacy_reviews.append(privacy_review_for_path(review, target_relative))
        prepared_files.append((entry, source, target_relative))

    manifest_files: list[dict[str, Any]] = []
    try:
        destination.mkdir(parents=True)
        for entry, source, target_relative in prepared_files:
            target = destination / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            source_hash = sha256(source)
            if sha256(target) != source_hash:
                raise PaperToolError(f"copy verification failed: {source}")
            manifest_files.append(
                {
                    "path": str(target_relative),
                    "role": str(entry["role"]),
                    "label": str(entry.get("label", "")),
                    "public": bool(entry.get("public", True)),
                    "original_sha256": source_hash,
                    "sha256": source_hash,
                }
            )
        build_enabled = bool(spec.get("build_enabled", True))
        build_engine = str(spec.get("build_engine", "")).strip()
        if build_engine and build_engine not in LATEXMKRC_BY_ENGINE:
            raise PaperToolError(
                "build_engine must be one of: "
                + ", ".join(sorted(LATEXMKRC_BY_ENGINE))
            )
        effective_engine = build_engine or DEFAULT_BUILD_ENGINE
        latexmkrc = destination / ".latexmkrc"
        if build_enabled and not latexmkrc.exists():
            latexmkrc.write_text(
                LATEXMKRC_BY_ENGINE[effective_engine], encoding="utf-8"
            )
        manifest = {
            "schema_version": 2,
            "slug": slug,
            "legacy_slugs": list(spec.get("legacy_slugs", [])),
            "title": spec["title"],
            "published_at": spec["published_at"],
            "sequence": sequence,
            "year": published.year,
            "kind": spec["kind"],
            "math_section": str(spec.get("math_section", "")).strip(),
            "summary": spec["summary"],
            "original_url": spec["original_url"],
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": list(spec["tags"]),
            "keywords": list(spec["keywords"]),
            "build": (
                {
                    "enabled": True,
                    "root": str(spec.get("build_root", "main.tex")),
                    "engine": build_engine,
                }
                if build_enabled
                else {"enabled": False, "engine": build_engine}
            ),
            "files": manifest_files,
            "approved_changes": [],
            "privacy_reviews": privacy_reviews,
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
        (destination / "keywords.txt").write_text(
            rendered_keywords(manifest), encoding="utf-8"
        )
        validate_manifest(manifest, manifest_path)
        errors = verify_one(manifest_path, manifest)
        if errors:
            raise PaperToolError("; ".join(errors))
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    if not args.no_catalog:
        command_catalog(argparse.Namespace(check=False))
    print(f"IMPORTED {slug} with byte-identical protected files")


def command_approve(args: argparse.Namespace) -> None:
    reason = args.reason.strip()
    if not reason:
        raise PaperToolError("approval reason must not be empty")
    selected = manifests([args.slug])
    manifest_path, manifest = selected[0]
    requested = list(dict.fromkeys(args.files))
    requested_set = set(requested)
    entries = {entry["path"]: entry for entry in manifest["files"]}
    unknown = [path for path in requested if path not in entries]
    if unknown:
        raise PaperToolError(f"files are not protected by paper.json: {', '.join(unknown)}")
    for entry in manifest["files"]:
        if entry["path"] in requested_set:
            continue
        target = manifest_path.parent / safe_relative_path(entry["path"])
        if not target.is_file() or sha256(target) != entry["sha256"]:
            raise PaperToolError(
                f"unapproved change exists outside requested files: {entry['path']}"
            )
    changes: list[dict[str, str]] = []
    for value in requested:
        relative = safe_relative_path(value)
        target = manifest_path.parent / relative
        if not target.is_file():
            raise PaperToolError(f"cannot approve missing file: {target}")
        old_hash = entries[value]["sha256"]
        new_hash = sha256(target)
        if old_hash == new_hash:
            continue
        entries[value]["sha256"] = new_hash
        changes.append({"path": value, "from_sha256": old_hash, "to_sha256": new_hash})
    if not changes:
        raise PaperToolError("no hash changes to approve")
    manifest["approved_changes"].append(
        {
            "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "reason": reason,
            "files": changes,
        }
    )
    write_json(manifest_path, manifest)
    print(f"APPROVED {len(changes)} explicitly requested change(s) for {args.slug}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Manage byte-protected LaTeX papers and the generated catalog."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="verify current approved hashes")
    verify_parser.add_argument("slugs", nargs="*")
    verify_parser.set_defaults(func=command_verify)

    audit_parser = subparsers.add_parser(
        "audit", help="show original versus explicitly approved file state"
    )
    audit_parser.add_argument("slugs", nargs="*")
    audit_parser.set_defaults(func=command_audit)

    catalog_parser = subparsers.add_parser("catalog", help="generate index.html cards")
    catalog_parser.add_argument("--check", action="store_true")
    catalog_parser.set_defaults(func=command_catalog)

    stage_parser = subparsers.add_parser("stage", help="prepare the GitHub Pages directory")
    stage_parser.add_argument("output")
    stage_parser.set_defaults(func=command_stage)

    links_parser = subparsers.add_parser(
        "check-links", help="check local links in a staged site"
    )
    links_parser.add_argument("site")
    links_parser.set_defaults(func=command_check_links)

    inspect_parser = subparsers.add_parser(
        "inspect-file", help="prepare a mandatory privacy review for a TeX or PDF file"
    )
    inspect_parser.add_argument("file")
    inspect_parser.set_defaults(func=command_inspect_file)

    import_parser = subparsers.add_parser(
        "import-paper", help="copy a new paper byte-for-byte from a JSON spec"
    )
    import_parser.add_argument("spec")
    import_parser.add_argument("--privacy-reviewed", action="store_true")
    import_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_parser.add_argument("--no-catalog", action="store_true")
    import_parser.set_defaults(func=command_import)

    import_tex_parser = subparsers.add_parser(
        "import-tex", help="create a source-only paper from one TeX file"
    )
    import_tex_parser.add_argument("tex_file")
    import_tex_parser.add_argument("--title")
    import_tex_parser.add_argument("--published-at")
    import_tex_parser.add_argument("--sequence", type=int)
    import_tex_parser.add_argument("--original-url")
    import_tex_parser.add_argument("--privacy-reviewed", action="store_true")
    import_tex_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_tex_parser.add_argument("--no-catalog", action="store_true")
    import_tex_parser.set_defaults(func=command_import_tex)

    import_pdf_parser = subparsers.add_parser(
        "import-pdf", help="create a paper from one published PDF file"
    )
    import_pdf_parser.add_argument("pdf_file")
    import_pdf_parser.add_argument("--title")
    import_pdf_parser.add_argument("--published-at")
    import_pdf_parser.add_argument("--sequence", type=int)
    import_pdf_parser.add_argument("--original-url")
    import_pdf_parser.add_argument("--privacy-reviewed", action="store_true")
    import_pdf_parser.add_argument(
        "--privacy-override", metavar="REASON", help="force import and record why"
    )
    import_pdf_parser.add_argument("--no-catalog", action="store_true")
    import_pdf_parser.set_defaults(func=command_import_pdf)

    approve_parser = subparsers.add_parser(
        "approve-change", help="record an explicitly requested source-file change"
    )
    approve_parser.add_argument("slug")
    approve_parser.add_argument("--reason", required=True)
    approve_parser.add_argument("--file", dest="files", action="append", required=True)
    approve_parser.set_defaults(func=command_approve)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except PaperToolError as error:
        print(f"paper-tool: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
