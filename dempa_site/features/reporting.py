"""Stable human-readable summaries of additional feature outcomes."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from dempa_site.features.runner import FeatureResult


def feature_result_lines(results: Iterable[FeatureResult]) -> tuple[str, ...]:
    """Render compact results while making every optional failure visible."""
    results = tuple(results)
    if not results:
        return ()
    counts = Counter(result.status for result in results)
    lines = [
        "FEATURES "
        f"generated={counts['generated']} "
        f"failed={counts['failed']} "
        f"disabled={counts['disabled']}"
    ]
    for result in results:
        target = f" [{result.paper_slug}]" if result.paper_slug else ""
        if result.status == "failed":
            requirement = "required" if result.required else "optional"
            phase = f", {result.phase}" if result.phase else ""
            lines.append(
                f"WARN feature failed: {result.name}{target} "
                f"({requirement}{phase}): {result.error}"
            )
        elif result.status == "disabled":
            lines.append(f"FEATURE disabled: {result.name}{target}")
        else:
            lines.append(f"FEATURE generated: {result.name}{target}")
    return tuple(lines)
