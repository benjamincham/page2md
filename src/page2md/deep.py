"""Optional `deep` parse path backed by docling (local CPU models, no LLM).

Not on the default path: docling is a heavy optional dependency that
downloads model weights on first use. Imported lazily so the base install
stays light.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ParseError
from .models import Block, Capture, Document

_DOC_TO_BLOCKTYPE = {
    "section-header": "heading",
    "title": "heading",
    "list-item": "list_item",
    "table": "table",
    "code": "code",
    "caption": "caption",
}


def parse_deep(pdf_path: Path | str, *, capture: Capture | None = None) -> Document:
    """Parse with docling. Raises ParseError if docling is not installed."""
    pdf_path = Path(pdf_path)
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise ParseError(
            "The `deep` parser requires docling, which is an optional heavy "
            "dependency. Install it with: pip install 'page2md[deep]'"
        ) from exc

    if not pdf_path.exists():
        raise ParseError(f"PDF not found: {pdf_path}")

    try:
        conv = DocumentConverter()
        result = conv.convert(str(pdf_path))
        dl_doc = result.document
    except Exception as exc:
        raise ParseError(f"docling failed on {pdf_path}: {exc}") from exc

    blocks: list[Block] = []
    next_id = 0
    for item, _level in dl_doc.iterate_items():
        label = getattr(getattr(item, "label", None), "value", str(getattr(item, "label", "")))
        text = getattr(item, "text", "") or ""
        if label == "table":
            try:
                text = item.export_to_markdown()
            except Exception:
                pass
        text = text.strip()
        if not text:
            continue
        prov = getattr(item, "prov", None) or []
        page_no = 1
        bbox = (0.0, 0.0, 0.0, 0.0)
        if prov:
            p0 = prov[0]
            page_no = int(getattr(p0, "page_no", 1))
            bb = getattr(p0, "bbox", None)
            if bb is not None:
                bbox = (
                    float(getattr(bb, "l", 0.0)),
                    float(getattr(bb, "t", 0.0)),
                    float(getattr(bb, "r", 0.0)),
                    float(getattr(bb, "b", 0.0)),
                )
        btype = _DOC_TO_BLOCKTYPE.get(label, "paragraph")
        level = getattr(item, "level", None) if btype == "heading" else None
        blocks.append(
            Block(
                id=next_id,
                type=btype,  # type: ignore[arg-type]
                text=text,
                page_no=page_no,
                bbox=bbox,
                level=level,
            )
        )
        next_id += 1

    title: str = ""
    name = getattr(dl_doc, "name", "")
    if isinstance(name, str):
        title = name

    return Document(
        blocks=blocks,
        page_count=_docling_page_count(dl_doc),
        capture=capture,
        source_pdf=pdf_path,
        parser="docling",
        title=title or (capture.title if capture else ""),
        url=capture.url if capture else None,
    )


def _docling_page_count(dl_doc: Any) -> int:
    pages = getattr(dl_doc, "pages", None)
    if pages:
        return len(pages)
    return 0


__all__ = ["parse_deep"]
