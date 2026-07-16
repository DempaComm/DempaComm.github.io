#!/usr/bin/env python3
"""Import, protect, catalog, and stage public LaTeX papers."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(
    os.environ.get("PAPER_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PAPERS_DIR = ROOT / "papers"
INDEX_PATH = ROOT / "index.html"
SEARCH_SCRIPT_PATH = ROOT / "search.js"
START_MARKER = "<!-- GENERATED:PAPERS:START -->"
END_MARKER = "<!-- GENERATED:PAPERS:END -->"
TAGS_START_MARKER = "<!-- GENERATED:TAGS:START -->"
TAGS_END_MARKER = "<!-- GENERATED:TAGS:END -->"
YEARS_START_MARKER = "<!-- GENERATED:YEARS:START -->"
YEARS_END_MARKER = "<!-- GENERATED:YEARS:END -->"
DEFAULT_LATEXMKRC = """$latex = 'platex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$pdf_mode = 3;
"""


class PaperToolError(RuntimeError):
    pass


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
    if manifest["schema_version"] != 1:
        raise PaperToolError(f"{path}: unsupported schema_version")
    if path.parent.name != manifest["slug"]:
        raise PaperToolError(f"{path}: slug does not match directory name")
    if not isinstance(manifest["sequence"], int) or manifest["sequence"] < 1:
        raise PaperToolError(f"{path}: sequence must be a positive integer")
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
    if not build["enabled"] and "published.pdf" not in seen:
        raise PaperToolError(f"{path}: archived papers must protect published.pdf")


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


def paper_card(manifest: dict[str, Any]) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    kind = html.escape(manifest["kind"])
    summary = html.escape(manifest["summary"])
    original_url = html.escape(manifest["original_url"], quote=True)
    published_date = str(manifest["published_at"])[:10]
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
        f'          <a class="paper-tag" href="{tag_href(tag)}">{html.escape(tag)}</a>'
        for tag in manifest["tags"]
    )
    actions = [
        f'          <a class="primary-action" href="papers/{slug}/main.pdf">PDFを読む</a>'
    ]
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        relative = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        actions.append(f'          <a href="papers/{slug}/{relative}">{label}</a>')
    actions.append(f'          <a href="papers/{slug}/keywords.txt">検索語</a>')
    actions.append(f'          <a href="{original_url}">元の記事</a>')
    actions_html = "\n".join(actions)
    aria = html.escape(f"{manifest['title']}のファイル", quote=True)
    return f"""      <article class="paper-card" id="paper-{slug}" data-search="{search_attribute}" data-tags="{tags_attribute}" data-year="{int(manifest['year'])}">
        <div class="paper-meta">
          <span>初出 {published_date}</span>
          <span>{kind}</span>
        </div>
        <h3><a href="papers/{slug}/">{title}</a></h3>
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


def rendered_year_groups(selected: list[tuple[Path, dict[str, Any]]]) -> str:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for _, manifest in selected:
        grouped.setdefault(int(manifest["year"]), []).append(manifest)

    groups: list[str] = []
    for year in sorted(grouped, reverse=True):
        papers = grouped[year]
        article_links = "\n".join(
            "          <li>"
            f'<a href="papers/{html.escape(paper["slug"], quote=True)}/">'
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


def rendered_tag_page_paper(manifest: dict[str, Any]) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    published_date = html.escape(str(manifest["published_at"])[:10])
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    kind = html.escape(manifest["kind"])
    tag_chips = "\n".join(
        f'            <a class="paper-tag" href="../{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    actions = [
        f'            <a class="primary-action" href="../../papers/{slug}/main.pdf">PDFを読む</a>'
    ]
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        path = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        actions.append(f'            <a href="../../papers/{slug}/{path}">{label}</a>')
    original_url = html.escape(manifest["original_url"], quote=True)
    actions.append(f'            <a href="{original_url}">元の記事</a>')
    return f"""        <article class="tag-page-paper">
          <div class="paper-meta"><span>初出 {published_date}</span><span>{kind}</span></div>
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
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_tag}の記事 — 数学識電脳</title>
  <meta name="description" content="電波通信のタグ「{html.escape(tag, quote=True)}」が付いた公開原稿の一覧">
  <link rel="stylesheet" href="../../styles.css">
</head>
<body class="tag-page">
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">TAG ARCHIVE</p>
      <h1>{escaped_tag}</h1>
      <p class="lead">電波通信でこのタグが付けられていた公開原稿、全{len(papers)}件。</p>
      <a class="hatena-link" href="../../#tags-title">タグ索引へ戻る</a>
    </div>
  </header>
  <main>
{year_sections}
  </main>
  <footer><p>数学識電脳 — 数学識電脳界溢出部位封神蔵収 ありあまる富</p></footer>
</body>
</html>
"""


def rendered_paper_page(manifest: dict[str, Any]) -> str:
    slug = html.escape(manifest["slug"], quote=True)
    title = html.escape(manifest["title"])
    summary = html.escape(manifest["summary"])
    published_date = html.escape(str(manifest["published_at"])[:10])
    kind = html.escape(manifest["kind"])
    tag_chips = "\n".join(
        f'          <a class="paper-tag" href="../../tags/{quote(tag, safe="")}/">'
        f"{html.escape(tag)}</a>"
        for tag in manifest["tags"]
    )
    keyword_chips = "\n".join(
        f'          <span class="keyword-chip">{html.escape(keyword)}</span>'
        for keyword in manifest["keywords"]
    )
    actions = ['          <a class="primary-action" href="main.pdf">PDFを読む</a>']
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        path = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        actions.append(f'          <a href="{path}">{label}</a>')
    actions.append('          <a href="keywords.txt">検索語テキスト</a>')
    original_url = html.escape(manifest["original_url"], quote=True)
    actions.append(f'          <a href="{original_url}">電波通信の元記事</a>')
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — 数学識電脳</title>
  <meta name="description" content="{html.escape(manifest['summary'], quote=True)}">
  <link rel="canonical" href="https://dempacomm.github.io/papers/{slug}/">
  <link rel="stylesheet" href="../../styles.css">
</head>
<body class="paper-page">
  <header class="site-header">
    <div class="header-inner">
      <p class="eyebrow">PUBLIC MANUSCRIPT</p>
      <h1>{title}</h1>
      <p class="lead">{summary}</p>
      <a class="hatena-link" href="../../#paper-{slug}">公開原稿一覧へ戻る</a>
    </div>
  </header>
  <main>
    <article class="paper-detail">
      <div class="paper-meta">
        <span>初出 {published_date}</span>
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
  <footer><p>数学識電脳 — 数学識電脳界溢出部位封神蔵収 ありあまる富</p></footer>
</body>
</html>
"""


def replace_generated(source: str, start: str, end: str, content: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise PaperToolError(f"index.html must contain exactly one marker pair: {start}")
    before, remainder = source.split(start, 1)
    _, after = remainder.split(end, 1)
    return f"{before}{start}\n{content}\n    {end}{after}"


def rendered_index() -> str:
    source = INDEX_PATH.read_text(encoding="utf-8")
    selected = manifests()
    cards = "\n\n".join(paper_card(manifest) for _, manifest in selected)
    source = replace_generated(source, START_MARKER, END_MARKER, cards)
    source = replace_generated(
        source,
        TAGS_START_MARKER,
        TAGS_END_MARKER,
        rendered_tag_index(selected),
    )
    return replace_generated(
        source,
        YEARS_START_MARKER,
        YEARS_END_MARKER,
        rendered_year_groups(selected),
    )


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
        else:
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
    print(f"STAGED {len(selected)} papers in {output}")


def resolve_source_dir(spec_path: Path, spec: dict[str, Any]) -> Path:
    raw_value = spec.get("source_dir")
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise PaperToolError("spec.source_dir is required")
    raw = Path(raw_value)
    return (raw if raw.is_absolute() else spec_path.parent / raw).resolve()


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

    manifest_files: list[dict[str, Any]] = []
    try:
        destination.mkdir(parents=True)
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
        latexmkrc = destination / ".latexmkrc"
        if build_enabled and not latexmkrc.exists():
            latexmkrc.write_text(DEFAULT_LATEXMKRC, encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "slug": slug,
            "legacy_slugs": list(spec.get("legacy_slugs", [])),
            "title": spec["title"],
            "published_at": spec["published_at"],
            "sequence": sequence,
            "year": published.year,
            "kind": spec["kind"],
            "summary": spec["summary"],
            "original_url": spec["original_url"],
            "order": int(f"{published:%Y%m%d}{sequence:02d}"),
            "tags": list(spec["tags"]),
            "keywords": list(spec["keywords"]),
            "build": (
                {"enabled": True, "root": str(spec.get("build_root", "main.tex"))}
                if build_enabled
                else {"enabled": False}
            ),
            "files": manifest_files,
            "approved_changes": [],
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

    import_parser = subparsers.add_parser(
        "import-paper", help="copy a new paper byte-for-byte from a JSON spec"
    )
    import_parser.add_argument("spec")
    import_parser.add_argument("--no-catalog", action="store_true")
    import_parser.set_defaults(func=command_import)

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
