"""Record public corrections and addenda without hand-editing JSON."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, write_json
from dempa_site.manifests.loader import load_manifest
from dempa_site.manifests.model import Paper


NOTE_KINDS = {"correction": "訂正", "addendum": "追記"}


def _validate_anchor(manifest_path: Path, paper: Paper, anchor: str) -> None:
    if not anchor:
        return
    if not anchor.startswith("#") or len(anchor) == 1:
        raise PaperToolError("--anchor は # から始まるHTML内の位置を指定してください")
    version = paper.html_version
    if version is None:
        raise PaperToolError("HTML版がない原稿には --anchor を指定できません")
    html_path = manifest_path.parent / version.path
    identifier = re.escape(anchor[1:])
    source = html_path.read_text(encoding="utf-8")
    if re.search(rf"\bid\s*=\s*(['\"]){identifier}\1", source) is None:
        raise PaperToolError(
            f"主HTML版に指定した位置がありません: {anchor}"
        )


def record_note(
    manifest_path: Path,
    paper: Paper,
    *,
    kind: str,
    summary: str,
    anchor: str = "",
    recorded_at: str | None = None,
) -> dict[str, str]:
    """Append one validated note and restore the manifest if validation fails."""
    if kind not in NOTE_KINDS:
        raise PaperToolError(f"unknown correction kind: {kind}")
    summary = summary.strip()
    anchor = anchor.strip()
    if not summary:
        raise PaperToolError("--summary は空にできません")
    _validate_anchor(manifest_path, paper, anchor)
    entry = {
        "recorded_at": recorded_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": kind,
        "summary": summary,
    }
    if anchor:
        entry["anchor"] = anchor

    value = read_json(manifest_path)
    notes = value.setdefault("corrections", [])
    if any(
        item.get("kind", "correction") == kind
        and item["summary"].strip() == summary
        and item.get("anchor", "").strip() == anchor
        for item in notes
    ):
        raise PaperToolError("同じ訂正・追記がすでに登録されています")

    original = manifest_path.read_bytes()
    notes.append(entry)
    write_json(manifest_path, value)
    try:
        load_manifest(manifest_path, PaperToolError)
    except Exception:
        manifest_path.write_bytes(original)
        raise
    return entry
