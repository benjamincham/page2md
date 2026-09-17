"""Render a Document to LLM-ready Markdown with YAML front matter."""

from __future__ import annotations

from .layout import LIST_MARKER_RE
from .models import Block, Document


def _escape_yaml(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def render_block(block: Block) -> str:
    """Render one block to its Markdown form (no trailing blank line)."""
    if block.type == "heading":
        level = min(6, max(1, block.level or 1))
        return f"{'#' * level} {block.text.replace(chr(10), ' ')}"
    if block.type == "list_item":
        lines = block.text.splitlines()
        m = LIST_MARKER_RE.match(lines[0])
        first = lines[0][m.end() :] if m else lines[0]
        out = [f"- {first}".rstrip()]
        out.extend(f"  {ln}" for ln in lines[1:])
        return "\n".join(out)
    if block.type == "table":
        return block.text  # already pipe-table markdown, verbatim
    if block.type == "code":
        return f"```\n{block.text}\n```"
    return block.text


def document_to_markdown(doc: Document) -> str:
    """Single Markdown document: YAML front matter + rendered blocks."""
    capture = doc.capture
    front = {
        "url": doc.url or (capture.url if capture else ""),
        "title": doc.title,
        "captured_at": capture.captured_at if capture else "",
        "backend": capture.backend if capture else "",
        "parser": doc.parser,
        "page_count": str(doc.page_count),
        "source_pdf": str(doc.source_pdf),
    }
    lines = ["---"]
    for key, value in front.items():
        lines.append(f'{key}: "{_escape_yaml(value)}"')
    lines.append("---")
    lines.append("")

    for block in doc.blocks:
        lines.append(render_block(block))
        lines.append("")
        if block.links:
            for link in block.links:
                lines.append(f"[{link['text']}]({link['uri']})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
