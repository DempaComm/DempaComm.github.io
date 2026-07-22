"""Date parsing and timestamp creation shared by archive tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_iso_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def local_now_seconds() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def utc_now_seconds() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def local_now_isoformat() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

