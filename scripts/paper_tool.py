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


ROOT = Path(
    os.environ.get("PAPER_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PAPERS_DIR = ROOT / "papers"
INDEX_PATH = ROOT / "index.html"
START_MARKER = "<!-- GENERATED:PAPERS:START -->"
END_MARKER = "<!-- GENERATED:PAPERS:END -->"
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
        "title",
        "year",
        "kind",
        "summary",
        "original_url",
        "order",
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
    if not isinstance(manifest["files"], list) or not manifest["files"]:
        raise PaperToolError(f"{path}: files must be a non-empty array")
    build = manifest["build"]
    if not isinstance(build, dict) or "root" not in build:
        raise PaperToolError(f"{path}: build.root is required")
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
    if str(build["root"]) not in seen:
        raise PaperToolError(f"{path}: build.root must appear in files")


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
    actions = [
        f'          <a class="primary-action" href="papers/{slug}/main.pdf">PDFを読む</a>'
    ]
    for entry in manifest["files"]:
        if not entry["public"] or not entry["label"]:
            continue
        relative = html.escape(entry["path"], quote=True)
        label = html.escape(entry["label"])
        actions.append(f'          <a href="papers/{slug}/{relative}">{label}</a>')
    actions.append(f'          <a href="{original_url}">元の記事</a>')
    actions_html = "\n".join(actions)
    aria = html.escape(f"{manifest['title']}のファイル", quote=True)
    return f"""      <article class="paper-card">
        <div class="paper-meta">
          <span>初出 {int(manifest['year'])}</span>
          <span>{kind}</span>
        </div>
        <h3>{title}</h3>
        <p>{summary}</p>
        <nav class="paper-actions" aria-label="{aria}">
{actions_html}
        </nav>
      </article>"""


def rendered_index() -> str:
    source = INDEX_PATH.read_text(encoding="utf-8")
    if source.count(START_MARKER) != 1 or source.count(END_MARKER) != 1:
        raise PaperToolError("index.html must contain exactly one generated-paper marker pair")
    before, remainder = source.split(START_MARKER, 1)
    _, after = remainder.split(END_MARKER, 1)
    cards = "\n\n".join(paper_card(manifest) for _, manifest in manifests())
    return f"{before}{START_MARKER}\n{cards}\n    {END_MARKER}{after}"


def command_catalog(args: argparse.Namespace) -> None:
    rendered = rendered_index()
    current = INDEX_PATH.read_text(encoding="utf-8")
    if args.check:
        if rendered != current:
            raise PaperToolError("index.html is not synchronized with paper.json files")
        print("OK  index.html catalog")
        return
    INDEX_PATH.write_text(rendered, encoding="utf-8")
    print("WROTE index.html")


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

    output = Path(args.output).resolve()
    if output == ROOT or output in ROOT.parents:
        raise PaperToolError("stage output must not be the repository or one of its parents")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copy2(INDEX_PATH, output / "index.html")
    shutil.copy2(ROOT / "styles.css", output / "styles.css")

    for manifest_path, manifest in selected:
        source_dir = manifest_path.parent
        target_dir = output / "papers" / manifest["slug"]
        target_dir.mkdir(parents=True)
        shutil.copy2(manifest_path, target_dir / "paper.json")
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
        pdf = source_dir / "main.pdf"
        if not pdf.is_file():
            raise PaperToolError(f"generated PDF is missing: {pdf}")
        shutil.copy2(pdf, target_dir / "main.pdf")
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
        "slug",
        "title",
        "year",
        "kind",
        "summary",
        "original_url",
        "order",
        "files",
    )
    missing = [key for key in required if key not in spec]
    if missing:
        raise PaperToolError(f"import spec missing fields: {', '.join(missing)}")
    slug = str(safe_relative_path(str(spec["slug"])))
    if "/" in slug:
        raise PaperToolError("slug must be one directory name")
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
        latexmkrc = destination / ".latexmkrc"
        if not latexmkrc.exists():
            latexmkrc.write_text(DEFAULT_LATEXMKRC, encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "slug": slug,
            "title": spec["title"],
            "year": int(spec["year"]),
            "kind": spec["kind"],
            "summary": spec["summary"],
            "original_url": spec["original_url"],
            "order": int(spec["order"]),
            "build": {"root": str(spec.get("build_root", "main.tex"))},
            "files": manifest_files,
            "approved_changes": [],
        }
        manifest_path = destination / "paper.json"
        write_json(manifest_path, manifest)
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
