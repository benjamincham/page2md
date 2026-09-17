"""Core dataclasses shared across the page2md pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

BlockType = Literal["heading", "paragraph", "list_item", "table", "code", "caption"]


@dataclass(frozen=True)
class Capture:
    """Provenance for one browser capture."""

    url: str  # final URL after redirects
    requested_url: str
    title: str
    captured_at: str  # ISO-8601 UTC
    backend: str  # "ego-browser"
    pdf_path: Path
    space_id: str | None
    page_label: str | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pdf_path"] = str(self.pdf_path)
        return d


@dataclass
class Block:
    """One structural block of a document."""

    id: int
    type: BlockType
    text: str
    page_no: int  # 1-based
    bbox: tuple[float, float, float, float]
    level: int | None = None  # headings only, 1..6
    links: list[dict[str, str]] = field(default_factory=list)  # {"text", "uri"}
    # set when this block was stitched across a page break: (first, last) page
    page_span: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Document:
    blocks: list[Block]
    page_count: int
    capture: Capture | None
    source_pdf: Path
    parser: str  # "pymupdf" | "docling"
    title: str
    url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [b.to_dict() for b in self.blocks],
            "page_count": self.page_count,
            "capture": self.capture.to_dict() if self.capture else None,
            "source_pdf": str(self.source_pdf),
            "parser": self.parser,
            "title": self.title,
            "url": self.url,
        }


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int
    heading_path: list[str]
    page_start: int
    page_end: int
    block_ids: list[int]
    url: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
