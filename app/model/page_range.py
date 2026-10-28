from __future__ import annotations

import re
import unicodedata

from app.i18n import t


def parse_page_ranges(text: str, page_count: int | None = None) -> tuple[tuple[int, int], ...]:
    """Return merged, ascending, inclusive 1-based ranges; empty means all pages."""
    text = unicodedata.normalize("NFKC", text).strip()
    for separator in ("、", ";", "；"):
        text = text.replace(separator, ",")
    for dash in ("–", "—", "−"):
        text = text.replace(dash, "-")
    if not text:
        return ()
    ranges = []
    for token in text.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", token)
        if not match:
            raise ValueError(t("page_range_invalid"))
        # Bound conversion before int() to reject unreasonably long input safely.
        if any(len(part) > 9 for part in match.groups() if part is not None):
            raise ValueError(t("page_range_invalid"))
        start = int(match[1])
        end = int(match[2]) if match[2] else start
        if start < 1 or end < start:
            raise ValueError(t("page_range_invalid"))
        if page_count is not None and end > page_count:
            raise ValueError(t("page_range_out_of_bounds_fmt", page=end, total=page_count))
        ranges.append((start, end))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return tuple(merged)


def normalize_page_range(text: str, page_count: int | None = None) -> str:
    return ",".join(str(start) if start == end else f"{start}-{end}"
                    for start, end in parse_page_ranges(text, page_count))


def resolve_page_indices(text: str, page_count: int) -> list[int]:
    ranges = parse_page_ranges(text, page_count)
    if not ranges:
        return list(range(page_count))
    return [page - 1 for start, end in ranges for page in range(start, end + 1)]
