#!/usr/bin/env python3
"""Build and validate the private-working migration ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(
    os.environ.get("LEDGER_REPO_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PAPERS_DIR = ROOT / "papers"
LEDGER_DIR = ROOT / "ledger"
CSV_PATH = LEDGER_DIR / "migration-ledger.csv"
JSON_PATH = LEDGER_DIR / "migration-ledger.json"

FIELDS = (
    "record_id",
    "status",
    "published_at",
    "sequence",
    "title",
    "original_url",
    "tags",
    "source_dir",
    "tex_files",
    "pdf_files",
    "bib_files",
    "bst_files",
    "duplicate_status",
    "duplicate_group",
    "canonical_record_id",
    "duplicate_basis",
    "target_slug",
    "math_section",
    "build_engine",
    "author_review",
    "notes",
)
LEGACY_FIELDS = tuple(
    field
    for field in FIELDS
    if field
    not in {
        "duplicate_status",
        "duplicate_group",
        "canonical_record_id",
        "duplicate_basis",
    }
)
LIST_FIELDS = {"tags", "tex_files", "pdf_files", "bib_files", "bst_files"}
EDITABLE_FIELDS = {
    "status",
    "published_at",
    "sequence",
    "title",
    "original_url",
    "tags",
    "target_slug",
    "math_section",
    "build_engine",
    "author_review",
    "notes",
}
STATUSES = {
    "source_found",
    "metadata_ready",
    "privacy_review",
    "ready",
    "published",
    "skipped",
}
AUTHOR_REVIEW_STATES = {
    "pending",
    "approved",
    "blocked",
    "legacy_unrecorded",
    "not_applicable",
}
DUPLICATE_STATES = {"unique", "canonical", "duplicate"}
DUPLICATE_BASES = {"", "tex+pdf", "tex", "pdf"}
MATH_SECTIONS = {
    "",
    "代数・組合せ",
    "位相・距離・幾何",
    "解析・測度・確率",
    "その他",
}
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")


class LedgerError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def join_list(values: Iterable[str]) -> str:
    return "|".join(dict.fromkeys(value.strip() for value in values if value.strip()))


def safe_relative(value: str, field: str) -> None:
    if not value:
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise LedgerError(f"{field} must be a safe relative path: {value}")


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted(PAPERS_DIR.glob("*/paper.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LedgerError(f"cannot read {path}: {error}") from error
        slug = str(value.get("slug", "")).strip()
        if not slug:
            raise LedgerError(f"{path}: missing slug")
        manifests[slug] = value
    return manifests


def read_rows(path: Path = CSV_PATH) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = tuple(reader.fieldnames or ())
        if header not in {FIELDS, LEGACY_FIELDS}:
            raise LedgerError(
                f"{path}: unsupported header; expected the current ledger fields"
            )
        return [
            {field: str(row.get(field, "") or "").strip() for field in FIELDS}
            for row in reader
        ]


def write_rows(rows: list[dict[str, str]], path: Path = CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(
    rows: list[dict[str, str]], manifests: dict[str, dict[str, Any]]
) -> None:
    errors: list[str] = []
    record_ids: set[str] = set()
    target_slugs: dict[str, str] = {}
    original_urls: dict[str, str] = {}
    rows_by_id: dict[str, dict[str, str]] = {}
    duplicate_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line_number, row in enumerate(rows, start=2):
        label = f"row {line_number}"
        record_id = row["record_id"]
        if not record_id:
            errors.append(f"{label}: record_id is empty")
        elif record_id in record_ids:
            errors.append(f"{label}: duplicate record_id {record_id}")
        record_ids.add(record_id)
        rows_by_id[record_id] = row
        if row["status"] not in STATUSES:
            errors.append(f"{label}: invalid status {row['status']!r}")
        if row["author_review"] not in AUTHOR_REVIEW_STATES:
            errors.append(
                f"{label}: invalid author_review {row['author_review']!r}"
            )
        if row["math_section"] not in MATH_SECTIONS:
            errors.append(f"{label}: invalid math_section {row['math_section']!r}")
        if row["duplicate_status"] not in DUPLICATE_STATES:
            errors.append(
                f"{label}: invalid duplicate_status {row['duplicate_status']!r}"
            )
        if row["duplicate_basis"] not in DUPLICATE_BASES:
            errors.append(
                f"{label}: invalid duplicate_basis {row['duplicate_basis']!r}"
            )
        if row["duplicate_group"]:
            duplicate_groups[row["duplicate_group"]].append(row)
        if row["sequence"]:
            try:
                if int(row["sequence"]) < 1:
                    raise ValueError
            except ValueError:
                errors.append(f"{label}: sequence must be a positive integer")
        for field in ("source_dir", "tex_files", "pdf_files", "bib_files", "bst_files"):
            values = split_list(row[field]) if field in LIST_FIELDS else [row[field]]
            for value in values:
                try:
                    safe_relative(value, field)
                except LedgerError as error:
                    errors.append(f"{label}: {error}")
        target_slug = row["target_slug"]
        if target_slug:
            if target_slug in target_slugs:
                errors.append(
                    f"{label}: target_slug {target_slug} also used by "
                    f"{target_slugs[target_slug]}"
                )
            target_slugs[target_slug] = record_id
        original_url = row["original_url"]
        if original_url:
            if original_url in original_urls:
                errors.append(
                    f"{label}: original_url also used by {original_urls[original_url]}"
                )
            original_urls[original_url] = record_id
        if row["status"] == "published":
            if not target_slug:
                errors.append(f"{label}: published record requires target_slug")
            elif target_slug not in manifests:
                errors.append(
                    f"{label}: published target_slug has no paper.json: {target_slug}"
                )
    for line_number, row in enumerate(rows, start=2):
        label = f"row {line_number}"
        duplicate_status = row["duplicate_status"]
        canonical_id = row["canonical_record_id"]
        group = row["duplicate_group"]
        basis = row["duplicate_basis"]
        if duplicate_status == "unique":
            if canonical_id or group or basis:
                errors.append(
                    f"{label}: unique record must not have duplicate metadata"
                )
            continue
        if not canonical_id or not group or not basis:
            errors.append(
                f"{label}: {duplicate_status} record requires group, canonical, and basis"
            )
            continue
        canonical = rows_by_id.get(canonical_id)
        if not canonical:
            errors.append(f"{label}: unknown canonical_record_id {canonical_id}")
            continue
        if canonical["duplicate_status"] != "canonical":
            errors.append(f"{label}: canonical_record_id does not point to canonical")
        if canonical["canonical_record_id"] != canonical_id:
            errors.append(f"{label}: canonical record must point to itself")
        if canonical["duplicate_group"] != group:
            errors.append(f"{label}: canonical record belongs to another group")
        if canonical["duplicate_basis"] != basis:
            errors.append(f"{label}: canonical record has another duplicate_basis")
        if duplicate_status == "canonical" and canonical_id != row["record_id"]:
            errors.append(f"{label}: canonical record must point to itself")
        if duplicate_status == "duplicate" and canonical_id == row["record_id"]:
            errors.append(f"{label}: duplicate record cannot point to itself")
    for group, members in duplicate_groups.items():
        if len(members) < 2:
            errors.append(f"duplicate group {group} has fewer than two records")
        canonical_count = sum(
            member["duplicate_status"] == "canonical" for member in members
        )
        if canonical_count != 1:
            errors.append(
                f"duplicate group {group} must have exactly one canonical record"
            )
    missing = sorted(set(manifests) - set(target_slugs))
    if missing:
        errors.append(
            "published manifests missing from ledger: " + ", ".join(missing)
        )
    if errors:
        raise LedgerError("\n".join(errors))


def json_value(rows: list[dict[str, str]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for field in FIELDS:
            value = row[field]
            if field in LIST_FIELDS:
                record[field] = split_list(value)
            elif field == "sequence":
                record[field] = int(value) if value else None
            else:
                record[field] = value
        records.append(record)
    counts = Counter(row["status"] for row in rows)
    return {
        "schema_version": 2,
        "source_root_label": "MyBlog/Myblogstr",
        "record_count": len(records),
        "status_counts": {key: counts.get(key, 0) for key in sorted(STATUSES)},
        "duplicate_counts": {
            key: sum(row["duplicate_status"] == key for row in rows)
            for key in sorted(DUPLICATE_STATES)
        },
        "duplicate_group_count": len(
            {
                row["duplicate_group"]
                for row in rows
                if row["duplicate_status"] == "canonical"
            }
        ),
        "records": records,
    }


def rendered_json(rows: list[dict[str, str]]) -> str:
    return json.dumps(json_value(rows), ensure_ascii=False, indent=2) + "\n"


def write_json(rows: list[dict[str, str]]) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(rendered_json(rows), encoding="utf-8")


def source_record_id(source_dir: str) -> str:
    digest = hashlib.sha256(source_dir.encode("utf-8")).hexdigest()[:16]
    return f"source:{digest}"


def candidate_title(source_dir: str) -> str:
    name = Path(source_dir).name
    return name if name not in {"", ".", "source"} else source_dir


def scan_candidates(
    myblog_root: Path, include_non_year: bool = False
) -> tuple[
    list[dict[str, str]],
    dict[str, set[str]],
    dict[str, dict[str, tuple[str, ...]]],
]:
    if not myblog_root.is_dir():
        raise LedgerError(f"Myblogstr root does not exist: {myblog_root}")
    supported = {".tex", ".pdf", ".bib", ".bst"}
    grouped: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {"tex": [], "pdf": [], "bib": [], "bst": []}
    )
    hashes: dict[str, set[str]] = defaultdict(set)
    fingerprints: dict[str, dict[str, tuple[str, ...]]] = {}
    for path in sorted(myblog_root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in supported:
            continue
        relative_path = path.relative_to(myblog_root)
        if not include_non_year and (
            not relative_path.parts
            or not YEAR_PATTERN.match(relative_path.parts[0])
        ):
            continue
        directory = relative_path.parent.as_posix()
        relative_name = path.name
        extension = path.suffix.casefold().removeprefix(".")
        grouped[directory][extension].append(relative_name)
        hashes[directory].add(sha256(path))
    rows: list[dict[str, str]] = []
    for source_dir in sorted(grouped):
        files = grouped[source_dir]
        directory_path = myblog_root / source_dir
        fingerprints[source_dir] = {
            extension: tuple(
                sorted(sha256(directory_path / name) for name in files[extension])
            )
            for extension in ("tex", "pdf")
        }
        rows.append(
            {
                "record_id": source_record_id(source_dir),
                "status": "source_found",
                "published_at": "",
                "sequence": "",
                "title": candidate_title(source_dir),
                "original_url": "",
                "tags": "",
                "source_dir": source_dir,
                "tex_files": join_list(sorted(files["tex"])),
                "pdf_files": join_list(sorted(files["pdf"])),
                "bib_files": join_list(sorted(files["bib"])),
                "bst_files": join_list(sorted(files["bst"])),
                "duplicate_status": "unique",
                "duplicate_group": "",
                "canonical_record_id": "",
                "duplicate_basis": "",
                "target_slug": "",
                "math_section": "",
                "build_engine": "",
                "author_review": "pending",
                "notes": "",
            }
        )
    return rows, hashes, fingerprints


def canonical_rank(row: dict[str, str]) -> tuple[int, int, int, str]:
    return (
        0 if row["status"] == "published" else 1,
        0 if row["tex_files"] and row["pdf_files"] else 1,
        len(Path(row["source_dir"]).parts),
        row["source_dir"],
    )


def apply_duplicate_group(
    rows_by_source: dict[str, dict[str, str]],
    sources: list[str],
    basis: str,
    signature: tuple[str, ...],
) -> None:
    selected = sorted((rows_by_source[source] for source in sources), key=canonical_rank)
    canonical = selected[0]
    group_seed = basis + "\0" + "\0".join(signature)
    group = "dup:" + hashlib.sha256(group_seed.encode("ascii")).hexdigest()[:16]
    for index, row in enumerate(selected):
        row["duplicate_status"] = "canonical" if index == 0 else "duplicate"
        row["duplicate_group"] = group
        row["canonical_record_id"] = canonical["record_id"]
        row["duplicate_basis"] = basis


def classify_duplicates(
    rows: list[dict[str, str]],
    fingerprints: dict[str, dict[str, tuple[str, ...]]],
) -> None:
    rows_by_source = {row["source_dir"]: row for row in rows if row["source_dir"]}
    for row in rows_by_source.values():
        row["duplicate_status"] = "unique"
        row["duplicate_group"] = ""
        row["canonical_record_id"] = ""
        row["duplicate_basis"] = ""
    claimed: set[str] = set()

    both_groups: dict[
        tuple[tuple[str, ...], tuple[str, ...]], list[str]
    ] = defaultdict(list)
    for source_dir, value in fingerprints.items():
        if value["tex"] and value["pdf"]:
            both_groups[(value["tex"], value["pdf"])].append(source_dir)
    for (tex_signature, pdf_signature), sources in sorted(both_groups.items()):
        if len(sources) < 2:
            continue
        apply_duplicate_group(
            rows_by_source,
            sources,
            "tex+pdf",
            ("tex",) + tex_signature + ("pdf",) + pdf_signature,
        )
        claimed.update(sources)

    for basis in ("tex", "pdf"):
        groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for source_dir, value in fingerprints.items():
            if source_dir not in claimed and value[basis]:
                groups[value[basis]].append(source_dir)
        for signature, sources in sorted(groups.items()):
            if len(sources) < 2:
                continue
            apply_duplicate_group(rows_by_source, sources, basis, signature)
            claimed.update(sources)


def manifest_hashes(manifest: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("original_sha256", ""))
        for entry in manifest.get("files", [])
        if entry.get("original_sha256")
    }


def apply_manifest(row: dict[str, str], manifest: dict[str, Any]) -> None:
    row.update(
        {
            "status": "published",
            "published_at": str(manifest.get("published_at", "")),
            "sequence": str(manifest.get("sequence", "")),
            "title": str(manifest.get("title", "")),
            "original_url": str(manifest.get("original_url", "")),
            "tags": join_list(str(value) for value in manifest.get("tags", [])),
            "target_slug": str(manifest.get("slug", "")),
            "math_section": str(manifest.get("math_section", "")),
            "build_engine": str(manifest.get("build", {}).get("engine", "")),
            "author_review": (
                "approved"
                if manifest.get("schema_version") == 2
                else "legacy_unrecorded"
            ),
        }
    )


def preserve_edits(
    row: dict[str, str], old_by_source: dict[str, dict[str, str]]
) -> None:
    old = old_by_source.get(row["source_dir"])
    if not old:
        return
    for field in EDITABLE_FIELDS:
        row[field] = old[field]


def merged_scan(myblog_root: Path, include_non_year: bool = False) -> list[dict[str, str]]:
    manifests = load_manifests()
    old_rows = read_rows()
    old_by_source = {row["source_dir"]: row for row in old_rows if row["source_dir"]}
    rows, candidate_hashes, fingerprints = scan_candidates(
        myblog_root, include_non_year
    )
    for row in rows:
        preserve_edits(row, old_by_source)

    assigned_sources: set[str] = set()
    assigned_slugs: set[str] = set()
    for slug, manifest in manifests.items():
        expected = manifest_hashes(manifest)
        scored = sorted(
            (
                (len(expected & hashes), source_dir)
                for source_dir, hashes in candidate_hashes.items()
                if expected & hashes
            ),
            reverse=True,
        )
        if not scored:
            continue
        best_score, best_source = scored[0]
        if best_score < 1 or best_source in assigned_sources:
            continue
        row = next(item for item in rows if item["source_dir"] == best_source)
        apply_manifest(row, manifest)
        assigned_sources.add(best_source)
        assigned_slugs.add(slug)

    for slug, manifest in sorted(manifests.items()):
        if slug in assigned_slugs:
            continue
        row = {
            "record_id": f"published:{slug}",
            "status": "published",
            "published_at": "",
            "sequence": "",
            "title": "",
            "original_url": "",
            "tags": "",
            "source_dir": "",
            "tex_files": "",
            "pdf_files": "",
            "bib_files": "",
            "bst_files": "",
            "duplicate_status": "unique",
            "duplicate_group": "",
            "canonical_record_id": "",
            "duplicate_basis": "",
            "target_slug": "",
            "math_section": "",
            "build_engine": "",
            "author_review": "not_applicable",
            "notes": "Myblogstr内の原稿候補とはSHA-256で自動対応できませんでした。",
        }
        apply_manifest(row, manifest)
        old = next(
            (item for item in old_rows if item["target_slug"] == slug),
            None,
        )
        if old:
            for field in EDITABLE_FIELDS:
                row[field] = old[field]
        rows.append(row)

    classify_duplicates(rows, fingerprints)

    def sort_key(row: dict[str, str]) -> tuple[str, str, str]:
        year = row["published_at"][:4]
        if not YEAR_PATTERN.match(year):
            first = Path(row["source_dir"]).parts[0] if row["source_dir"] else ""
            year = first if YEAR_PATTERN.match(first) else "9999"
        return (year, row["published_at"] or "9999", row["source_dir"])

    return sorted(rows, key=sort_key)


def command_scan(args: argparse.Namespace) -> None:
    rows = merged_scan(
        Path(args.myblog_root).expanduser().resolve(),
        include_non_year=args.include_non_year,
    )
    manifests = load_manifests()
    validate_rows(rows, manifests)
    write_rows(rows)
    write_json(rows)
    print(f"WROTE {len(rows)} ledger records")


def command_build(args: argparse.Namespace) -> None:
    rows = read_rows()
    if not rows:
        raise LedgerError("ledger CSV does not exist or is empty; run scan first")
    validate_rows(rows, load_manifests())
    write_json(rows)
    print(f"WROTE {JSON_PATH.relative_to(ROOT)}")


def command_check(args: argparse.Namespace) -> None:
    rows = read_rows()
    if not rows:
        raise LedgerError("ledger CSV does not exist or is empty")
    validate_rows(rows, load_manifests())
    expected = rendered_json(rows)
    if not JSON_PATH.is_file() or JSON_PATH.read_text(encoding="utf-8") != expected:
        raise LedgerError("migration-ledger.json is stale; run ledger build")
    print(f"OK  migration ledger ({len(rows)} records)")


def command_stats(args: argparse.Namespace) -> None:
    rows = read_rows()
    validate_rows(rows, load_manifests())
    counts = Counter(row["status"] for row in rows)
    print(f"records: {len(rows)}")
    for status in sorted(STATUSES):
        print(f"{status}: {counts.get(status, 0)}")
    with_tex = sum(bool(row["tex_files"]) for row in rows)
    with_pdf = sum(bool(row["pdf_files"]) for row in rows)
    duplicate_counts = Counter(row["duplicate_status"] for row in rows)
    group_count = sum(row["duplicate_status"] == "canonical" for row in rows)
    print(f"with_tex: {with_tex}")
    print(f"with_pdf: {with_pdf}")
    print(f"canonical: {duplicate_counts.get('canonical', 0)}")
    print(f"duplicate: {duplicate_counts.get('duplicate', 0)}")
    print(f"unique: {duplicate_counts.get('unique', 0)}")
    print(f"duplicate_groups: {group_count}")
    print(f"review_candidates: {len(rows) - duplicate_counts.get('duplicate', 0)}")


def command_duplicates(args: argparse.Namespace) -> None:
    rows = read_rows()
    validate_rows(rows, load_manifests())
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["duplicate_group"]:
            groups[row["duplicate_group"]].append(row)
    for group in sorted(groups):
        members = groups[group]
        canonical = next(
            row for row in members if row["duplicate_status"] == "canonical"
        )
        print(
            f"{group} {canonical['duplicate_basis']} "
            f"{len(members)} records; canonical={canonical['record_id']}"
        )
        for row in sorted(
            members,
            key=lambda value: (
                value["duplicate_status"] != "canonical",
                value["source_dir"],
            ),
        ):
            marker = "C" if row["duplicate_status"] == "canonical" else "D"
            published = f" [{row['target_slug']}]" if row["target_slug"] else ""
            print(f"  {marker} {row['source_dir'] or '(source unmatched)'}{published}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Scan Myblogstr and maintain the migration ledger."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan", help="scan Myblogstr, preserve manual fields, and rebuild the ledger"
    )
    scan.add_argument("myblog_root")
    scan.add_argument(
        "--include-non-year",
        action="store_true",
        help="also scan non-year top-level directories such as backup trees",
    )
    scan.set_defaults(func=command_scan)

    build = subparsers.add_parser(
        "build", help="regenerate JSON from the hand-editable CSV"
    )
    build.set_defaults(func=command_build)

    check = subparsers.add_parser(
        "check", help="validate the CSV, JSON, and published-paper coverage"
    )
    check.set_defaults(func=command_check)

    stats = subparsers.add_parser("stats", help="show migration progress counts")
    stats.set_defaults(func=command_stats)

    duplicates = subparsers.add_parser(
        "duplicates", help="list duplicate groups and their canonical candidates"
    )
    duplicates.set_defaults(func=command_duplicates)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except LedgerError as error:
        print(f"migration-ledger: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
