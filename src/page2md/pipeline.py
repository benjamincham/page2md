"""End-to-end pipelines: URL -> PDF -> Markdown/blocks/chunks, or PDF -> same."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .capture import EgoCapture
from .chunk import chunk_document
from .markdown import document_to_markdown
from .models import Capture, Document
from .parse import parse_pdf


@dataclass(frozen=True)
class DistillResult:
    """Paths written by a pipeline run."""

    out_dir: Path
    pdf: Path
    markdown: Path
    document_json: Path
    chunks_jsonl: Path
    capture_json: Path | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "out_dir": str(self.out_dir),
            "pdf": str(self.pdf),
            "markdown": str(self.markdown),
            "document_json": str(self.document_json),
            "chunks_jsonl": str(self.chunks_jsonl),
            "capture_json": str(self.capture_json) if self.capture_json else None,
        }


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:48] or "page"


def url_slug(url: str) -> str:
    """host + path slug + 8-char sha1 — unique per full URL incl. query."""
    parsed = urlparse(url)
    base = _slugify(f"{parsed.netloc}{parsed.path}")
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{base}-{digest}"


def _write_outputs(
    doc: Document,
    out_dir: Path,
    *,
    max_tokens: int,
    capture: Capture | None,
) -> DistillResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "page.md"
    md_path.write_text(document_to_markdown(doc), encoding="utf-8")

    doc_path = out_dir / "page.json"
    doc_path.write_text(json.dumps(doc.to_dict(), indent=2), encoding="utf-8")

    chunks_path = out_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as fh:
        for chunk in chunk_document(doc, max_tokens=max_tokens):
            fh.write(json.dumps(chunk.to_dict()) + "\n")

    capture_path: Path | None = None
    if capture is not None:
        capture_path = out_dir / "capture.json"
        capture_path.write_text(json.dumps(capture.to_dict(), indent=2), encoding="utf-8")

    return DistillResult(
        out_dir=out_dir,
        pdf=doc.source_pdf,
        markdown=md_path,
        document_json=doc_path,
        chunks_jsonl=chunks_path,
        capture_json=capture_path,
    )


def distill_url(
    url: str,
    out_root: Path | str,
    *,
    deep: bool = False,
    max_tokens: int = 1000,
    capture_backend: EgoCapture | None = None,
    space: str = "page2md",
    timeout_ms: int = 45_000,
    wait_selector: str | None = None,
    settle_ms: int = 1200,
) -> DistillResult:
    """Full pipeline: capture via ego-browser, then parse/chunk locally."""
    out_dir = Path(out_root) / url_slug(url)
    backend = capture_backend or EgoCapture()
    capture = backend.capture(
        url,
        out_dir,
        space=space,
        timeout_ms=timeout_ms,
        wait_selector=wait_selector,
        settle_ms=settle_ms,
    )
    doc = parse_pdf(capture.pdf_path, capture=capture, deep=deep)
    return _write_outputs(doc, out_dir, max_tokens=max_tokens, capture=capture)


def distill_pdf(
    pdf_path: Path | str,
    out_root: Path | str,
    *,
    deep: bool = False,
    max_tokens: int = 1000,
    url: str | None = None,
) -> DistillResult:
    """Stage 2 only: parse an already-captured PDF (works without ego-browser)."""
    pdf_path = Path(pdf_path)
    if url:
        name = url_slug(url)
    else:
        digest = hashlib.sha1(str(pdf_path).encode()).hexdigest()[:8]
        name = f"{_slugify(pdf_path.stem)}-{digest}"
    out_dir = Path(out_root) / name
    captured_at = ""
    if pdf_path.exists():
        captured_at = datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat()
    capture = Capture(
        url=url or "",
        requested_url=url or "",
        title="",
        captured_at=captured_at,
        backend="local-pdf",
        pdf_path=pdf_path,
        space_id=None,
        page_label=None,
    )
    doc = parse_pdf(pdf_path, capture=capture, deep=deep)
    return _write_outputs(doc, out_dir, max_tokens=max_tokens, capture=capture)
