"""Small deterministic file, JSON, hashing, and Unicode helpers."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str, encoding: str = "utf-8") -> str:
    return hashlib.sha256(value.encode(encoding)).hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json_text(value), encoding="utf-8")


def normalize_nfc(value: str) -> str:
    """Use the portable Unicode form stored by Git for public paths."""
    return unicodedata.normalize("NFC", value)


def normalize_nfkc_casefold(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()

