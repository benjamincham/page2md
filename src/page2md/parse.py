"""Stage 2 (default path): PDF -> structured Document via PyMuPDF.

Two extractions are reconciled per page:

- ``pymupdf4llm.to_markdown(doc, page_chunks=True)`` gives Markdown-quality
  text, in particular pipe-table Markdown we keep verbatim in `table` blocks.
- ``page.get_text("dict")`` gives span geometry (size/flags/bbox), used for
  reading order, headings and multi-column repair.

Reconciliation is deliberately loose: the dict extraction defines block order
and bboxes; the 4llm page markdown is only consulted to recognise table
regions (lines that look like pipe-table rows) so a table survives as ONE
block instead of being split across fitz blocks.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

import pymupdf as fitz
import pymupdf4llm

from .errors import ParseError
from .layout import (
    LIST_MARKER_RE,
    body_font_size,
    boilerplate_lines,
    infer_heading_level,
    is_page_number,
    normalize_line,
    normalize_text,
)
from .models import Block, Capture, Document

_PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_CODE_INDENT_RE = re.compile(r"^(?:    |\t)\S")
_HEADING_MAX_CHARS = 200
# A line that is only a section label: "1", "2.1", "2.1.", "iv.", "A."
_SECTION_LABEL_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[ivxlcdm]+\.|[A-Za-z]\.)$")
_HYPHEN_END_RE = re.compile(r"[-\u2010]$")
# Sentence-final punctuation, optionally followed by a closing bracket.
_SENTENCE_END_RE = re.compile(r"[.?!:;\"'”’][)\]]*\s*$")


def _iter_spans(page_dict: dict[str, Any]) -> Any:
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            yield from line.get("spans", [])


def _line_text(line: dict[str, Any]) -> str:
    return "".join(str(s.get("text", "")) for s in line.get("spans", []))


def _lines_text(lines: list[dict[str, Any]]) -> str:
    return "\n".join(t for t in (_line_text(ln) for ln in lines) if t.strip())


def _page_lines(page_dict: dict[str, Any]) -> list[str]:
    lines = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            txt = "".join(str(s.get("text", "")) for s in line.get("spans", []))
            if txt.strip():
                lines.append(txt)
    return lines


def _max_span_size(lines: list[dict[str, Any]]) -> tuple[float, bool]:
    """(largest span size across lines, whether that span is bold)."""
    best_size, best_bold = 0.0, False
    for line in lines:
        for span in line.get("spans", []):
            size = float(span.get("size", 0.0))
            if size > best_size:
                best_size = size
                flags = int(span.get("flags", 0))
                font = str(span.get("font", "")).lower()
                best_bold = bool(flags & 16) or "bold" in font
    return best_size, best_bold


def _page_lines_dicts(page_dict: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if _line_text(line).strip():
                out.append(line)
    return out


def _looks_two_column(lines: list[dict[str, Any]]) -> bool:
    """Two clear x-ranges with no horizontal overlap between clusters.

    Works on lines, not blocks: fitz happily merges text from two columns
    on the same baseline into a single block, so block granularity cannot
    detect columns.
    """
    if len(lines) < 6:
        return False
    xs = sorted((float(ln["bbox"][0]), float(ln["bbox"][2])) for ln in lines)
    mid = len(xs) // 2
    left, right = xs[:mid], xs[mid:]
    if not left or not right:
        return False
    gap = min(x0 for x0, _ in right) - max(x1 for _, x1 in left)
    if gap <= 30.0:
        return False
    # False-positive guard: each cluster needs >= 3 lines and the smaller
    # must be at least 25% of the larger (a wide figure caption next to a
    # narrow sidebar is not a two-column page).
    n_left = sum(1 for ln in lines if float(ln["bbox"][0]) < min(x0 for x0, _ in right))
    n_right = len(lines) - n_left
    smaller, larger = min(n_left, n_right), max(n_left, n_right)
    return smaller >= 3 and smaller >= 0.25 * larger


def _page_units(page_dict: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Reading-order list of 'units', each a list of line dicts.

    Single-column pages keep fitz block grouping (sorted by y, x). On
    two-column pages lines are re-ordered column-by-column and adjacent
    same-column lines are merged into one unit.
    """
    lines = _page_lines_dicts(page_dict)
    if not _looks_two_column(lines):
        blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]
        blocks.sort(key=lambda b: (float(b["bbox"][1]), float(b["bbox"][0])))
        return [[ln for ln in b.get("lines", []) if _line_text(ln).strip()] for b in blocks]

    xs = sorted(float(ln["bbox"][0]) for ln in lines)
    split = xs[len(xs) // 2]

    def col(ln: dict[str, Any]) -> int:
        return 0 if float(ln["bbox"][0]) < split else 1

    ordered = sorted(lines, key=lambda ln: (col(ln), float(ln["bbox"][1])))
    groups: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for ln in ordered:
        height = float(ln["bbox"][3]) - float(ln["bbox"][1])
        gap = float(ln["bbox"][1]) - float(cur[-1]["bbox"][3]) if cur else 0.0
        if cur and (col(ln) != col(cur[-1]) or gap > 1.6 * max(height, 1.0)):
            groups.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        groups.append(cur)
    return groups


def _table_markdown_ranges(md: str) -> list[tuple[str, str]]:
    """Extract pipe tables from 4llm page markdown -> (table_md, signature)."""
    tables: list[tuple[str, str]] = []
    current: list[str] = []
    for line in md.splitlines():
        if _PIPE_ROW_RE.match(line):
            current.append(line)
        else:
            if len(current) >= 2:
                tables.append(_table_entry(current))
            current = []
    if len(current) >= 2:
        tables.append(_table_entry(current))
    return tables


def _table_entry(lines: list[str]) -> tuple[str, str]:
    """(pipe-table markdown, squashed signature).

    The signature is all non-separator row text with whitespace and `|`
    removed, concatenated. fitz reports table cells as separate lines that
    rarely align with markdown row boundaries, so we match by substring on
    the squashed form rather than row-by-row.
    """
    sig = "".join(
        re.sub(r"[\s|]", "", ln).casefold()
        for ln in lines
        if not re.match(r"^\s*\|[\s:\-|]+\|\s*$", ln)
    )
    return "\n".join(lines), sig


def _squash(text: str) -> str:
    return re.sub(r"\s", "", text).casefold()


def _unit_matches_table(text: str, sig: str) -> bool:
    sq = _squash(text)
    return bool(sq) and len(sq) >= 3 and sq in sig


def _line_max_size(line: dict[str, Any]) -> float:
    return max((float(s.get("size", 0.0)) for s in line.get("spans", [])), default=0.0)


def _within_pct(a: float, b: float, pct: float = 0.05) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= pct


def _join_paragraph_lines(lines: list[str]) -> str:
    """Join soft-wrapped lines: de-hyphenate `foo-` + `bar`, else one space."""
    out = lines[0]
    for nxt in lines[1:]:
        if _HYPHEN_END_RE.search(out) and nxt[:1].islower():
            out = out[:-1] + nxt
        else:
            out += " " + nxt
    return out


def _attach_links(page: fitz.Page, page_blocks: list[Block]) -> None:
    """Attach page link annotations to the block whose bbox covers them."""
    links = page.get_links()
    if not links:
        return
    for link in links:
        uri = link.get("uri")
        rect = link.get("from")
        if not uri or rect is None:
            continue
        link_rect = fitz.Rect(rect)
        best: Block | None = None
        best_area = 0.0
        for block in page_blocks:
            inter = fitz.Rect(block.bbox) & link_rect
            area = abs(inter) if not inter.is_empty else 0.0
            if area > best_area:
                best, best_area = block, area
        if best is None:
            # no overlap: fall back to nearest block vertically
            best = min(
                page_blocks,
                key=lambda b: abs(fitz.Rect(b.bbox).y0 - link_rect.y0),
                default=None,
            )
        if best is None:
            continue
        text = page.get_text("text", clip=link_rect).strip() or str(uri)
        best.links = [*best.links, {"text": text, "uri": str(uri)}]


def parse_pdf(
    pdf_path: Path | str, *, capture: Capture | None = None, deep: bool = False
) -> Document:
    """Parse a captured PDF into a structured Document."""
    pdf_path = Path(pdf_path)
    if deep:
        from . import deep as deep_mod

        return deep_mod.parse_deep(pdf_path, capture=capture)
    if not pdf_path.exists():
        raise ParseError(f"PDF not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ParseError(f"Could not open {pdf_path}: {exc}") from exc

    if doc.page_count == 0:
        raise ParseError(f"{pdf_path} has no pages")

    try:
        md_pages = pymupdf4llm.to_markdown(doc, page_chunks=True)
    except Exception as exc:
        warnings.warn(f"pymupdf4llm failed on {pdf_path}: {exc}", stacklevel=2)
        md_pages = []
    md_by_page = {}
    for i, chunk in enumerate(md_pages):
        if not isinstance(chunk, dict):
            continue
        # pymupdf4llm keys pages by `metadata.page_number`, 1-based.
        pn = chunk.get("metadata", {}).get("page_number")
        page_idx = int(pn) - 1 if pn is not None else i
        md_by_page[page_idx] = str(chunk.get("text", ""))

    page_dicts = [doc.load_page(i).get_text("dict") for i in range(doc.page_count)]
    all_spans: list[dict[str, Any]] = []
    for pd in page_dicts:
        all_spans.extend(_iter_spans(pd))
    body = body_font_size(all_spans)

    boilerplate = boilerplate_lines([_page_lines(pd) for pd in page_dicts])

    blocks: list[Block] = []
    next_id = 0
    for page_idx in range(doc.page_count):
        page: fitz.Page = doc.load_page(page_idx)
        page_dict = page_dicts[page_idx]
        tables = _table_markdown_ranges(md_by_page.get(page_idx, ""))
        consumed_tables: set[int] = set()

        units = _page_units(page_dict)

        page_blocks: list[Block] = []
        i = 0
        while i < len(units):
            unit = units[i]
            i += 1
            kept = [
                (ln, _line_text(ln).strip())
                for ln in unit
                if _line_text(ln).strip() and normalize_line(_line_text(ln)) not in boilerplate
            ]
            if not kept:
                continue
            line_texts = [t for _, t in kept]
            line_sizes = [_line_max_size(ln) for ln, _ in kept]

            # Merge a leading section-label line ("2.1", "A.") into the next
            # line when both share the same font size — numbered headings are
            # commonly split across lines by PDF generators.
            if (
                len(line_texts) >= 2
                and _SECTION_LABEL_RE.match(line_texts[0])
                and _within_pct(line_sizes[0], line_sizes[1])
            ):
                line_texts = [f"{line_texts[0]} {line_texts[1]}", *line_texts[2:]]
                line_sizes = [max(line_sizes[0], line_sizes[1]), *line_sizes[2:]]

            raw_text = "\n".join(line_texts)
            if is_page_number(raw_text) and len(raw_text) < 20:
                continue

            bbox = _lines_bbox([ln for ln, _ in kept])

            emitted_table = False
            for ti, (t_md, t_sig) in enumerate(tables):
                if ti in consumed_tables or not _unit_matches_table(raw_text, t_sig):
                    continue
                # Merge following units that also belong to this table, then
                # emit ONE table block with the verbatim pipe-table markdown.
                j = i
                merged_bbox = fitz.Rect(bbox)
                while j < len(units):
                    nxt = _lines_text(units[j]).strip()
                    if nxt and _unit_matches_table(nxt, t_sig):
                        merged_bbox |= _lines_bbox(units[j])
                        j += 1
                    else:
                        break
                i = j
                consumed_tables.add(ti)
                page_blocks.append(
                    Block(
                        id=next_id,
                        type="table",
                        text=normalize_text(t_md),
                        page_no=page_idx + 1,
                        bbox=(
                            merged_bbox.x0,
                            merged_bbox.y0,
                            merged_bbox.x1,
                            merged_bbox.y1,
                        ),
                    )
                )
                next_id += 1
                emitted_table = True
                break
            if emitted_table:
                continue

            size, bold = _max_span_size([ln for ln, _ in kept])
            level = infer_heading_level(size, body, bold)

            # Heading: up to 2 lines, every line within 5% of the unit's
            # max span size, joined with a space.
            is_heading = (
                level is not None
                and len(line_texts) <= 2
                and all(_within_pct(s, size) for s in line_sizes)
                and len(" ".join(line_texts)) <= _HEADING_MAX_CHARS
            )

            if is_heading:
                btype = "heading"
                text = " ".join(line_texts)
            elif LIST_MARKER_RE.match(raw_text):
                btype = "list_item"
                text = raw_text
            elif _CODE_INDENT_RE.match(raw_text):
                btype = "code"
                text = raw_text
            else:
                btype = "paragraph"
                # Soft-wrapped lines join into one logical line.
                text = _join_paragraph_lines(line_texts)

            page_blocks.append(
                Block(
                    id=next_id,
                    type=btype,  # type: ignore[arg-type]
                    text=normalize_text(text),
                    page_no=page_idx + 1,
                    bbox=bbox,
                    level=level if btype == "heading" else None,
                )
            )
            next_id += 1

        _attach_links(page, page_blocks)
        blocks.extend(page_blocks)

    blocks = _stitch_page_breaks(blocks)
    for i, b in enumerate(blocks):
        b.id = i  # keep ids dense so chunk block_ids stay valid

    title = doc.metadata.get("title") or (capture.title if capture else "")
    if not title:
        first_heading = next((b for b in blocks if b.type == "heading"), None)
        if first_heading is not None:
            title = first_heading.text[:_HEADING_MAX_CHARS]
    url = capture.url if capture else None

    out = Document(
        blocks=blocks,
        page_count=doc.page_count,
        capture=capture,
        source_pdf=pdf_path,
        parser="pymupdf",
        title=title,
        url=url,
    )
    doc.close()
    return out


def _stitch_page_breaks(blocks: list[Block]) -> list[Block]:
    """Merge a paragraph that continues mid-sentence across a page break.

    Merges block n+1 into n when: both are paragraphs; n is the last block
    of page p and n+1 the first of page p+1 (consecutive in the flat list);
    n's text does not end in sentence-final punctuation; and n+1 starts
    with a lowercase letter or digit. The merged block keeps n's id/bbox
    and records `page_span`.
    """
    out: list[Block] = []
    for b in blocks:
        prev = out[-1] if out else None
        if (
            prev is not None
            and prev.type == "paragraph"
            and b.type == "paragraph"
            and b.page_no == prev.page_no + 1
            and not _SENTENCE_END_RE.search(prev.text)
            and b.text
            and (b.text[0].islower() or b.text[0].isdigit())
        ):
            prev.text = _join_paragraph_lines([prev.text, b.text])
            prev.page_span = (prev.page_no, b.page_no)
            if b.links:
                prev.links = [*prev.links, *b.links]
            continue
        out.append(b)
    return out


def _lines_bbox(lines: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    rect = fitz.Rect(lines[0]["bbox"])
    for ln in lines[1:]:
        rect |= fitz.Rect(ln["bbox"])
    return (rect.x0, rect.y0, rect.x1, rect.y1)


__all__ = ["parse_pdf", "ParseError"]
