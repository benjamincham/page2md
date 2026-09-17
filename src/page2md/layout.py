"""Deterministic layout heuristics: font statistics, heading levels, boilerplate.

Zero tokens, zero models — pure rules over span geometry and repeated text.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_NBSP_RE = re.compile(r"[\u00a0\u202f\u2009\u200a]")


def normalize_text(text: str) -> str:
    """NFKC-normalize and clean typographic junk from extracted text.

    Fixes ligatures (\ufb01nd), non-breaking/thin spaces, and drops
    zero-width characters entirely.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _NBSP_RE.sub(" ", text)
    return _ZERO_WIDTH_RE.sub("", text)


# Heading thresholds: font-size ratio relative to the detected body size.
H1_MIN_RATIO = 1.8
H2_MIN_RATIO = 1.5
H3_MIN_RATIO = 1.3
H4_MIN_RATIO = 1.15
H5_BOLD_MIN_RATIO = 1.02  # bold-only headings: must also be bold
_PAGE_NUMBER_RE = re.compile(r"^(?:page\s+)?\d+(?:\s*(?:/|of)\s*\d+)?$", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_DIGIT_RE = re.compile(r"\d")
# Shared list-marker pattern (bullet or numbered); used by parse + markdown.
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•‣·]|\d+[.)])\s+")


def _span_size(span: dict[str, object]) -> float:
    return float(span.get("size", 0.0))  # type: ignore[arg-type]


def _span_is_bold(span: dict[str, object]) -> bool:
    flags_obj = span.get("flags", 0)
    flags = int(flags_obj) if isinstance(flags_obj, (int, float)) else 0
    font = str(span.get("font", "")).lower()
    return bool(flags & 16) or "bold" in font


def _span_text(span: dict[str, object]) -> str:
    return str(span.get("text", ""))


def body_font_size(spans: Iterable[dict[str, object]]) -> float:
    """Most common span size, weighted by characters (not span count).

    `spans` is an iterable of fitz span dicts. Returns 0.0 when there is no text.
    """
    weights: dict[float, int] = {}
    for span in spans:
        size = round(_span_size(span), 1)
        n = len(_span_text(span).strip())
        if n:
            weights[size] = weights.get(size, 0) + n
    if not weights:
        return 0.0
    return max(weights.items(), key=lambda kv: kv[1])[0]


def infer_heading_level(size: float, body: float, bold: bool) -> int | None:
    """Classify a span size relative to the body size. None = not a heading."""
    if body <= 0 or size <= 0:
        return None
    ratio = size / body
    if ratio >= H1_MIN_RATIO:
        return 1
    if ratio >= H2_MIN_RATIO:
        return 2
    if ratio >= H3_MIN_RATIO:
        return 3
    if ratio >= H4_MIN_RATIO:
        return 4
    if ratio >= H5_BOLD_MIN_RATIO and bold:
        return 5
    return None


def normalize_line(line: str) -> str:
    """Casefold + collapse whitespace + map digits to '#' (boilerplate key)."""
    line = _DIGIT_RE.sub("#", line)
    return _WS_RE.sub(" ", line).strip().casefold()


def boilerplate_lines(
    pages: list[list[str]], *, min_pages: int = 3, ratio: float = 0.6
) -> set[str]:
    """Normalised lines that repeat on >= `ratio` of pages (running heads/footers).

    Never returns a line that is the sole content of a page — stripping it
    would empty the page entirely.
    """
    if len(pages) < min_pages:
        return set()

    threshold = max(1, round(len(pages) * ratio))
    count: dict[str, int] = {}
    sole_content: set[str] = set()

    for page_lines in pages:
        normalized = {normalize_line(ln) for ln in page_lines}
        normalized.discard("")
        for line in normalized:
            count[line] = count.get(line, 0) + 1
        if len(normalized) == 1:
            sole_content.add(next(iter(normalized)))

    return {line for line, n in count.items() if n >= threshold and line not in sole_content}


def is_page_number(text: str) -> bool:
    """True for '3', 'Page 12', '3/10', '3 of 10', ..."""
    return bool(_PAGE_NUMBER_RE.match(text.strip()))
