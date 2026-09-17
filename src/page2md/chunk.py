"""Pack Document blocks into citable, token-bounded chunks."""

from __future__ import annotations

from .markdown import render_block
from .models import Block, Chunk, Document
from .tokens import count_tokens


def chunk_document(doc: Document, *, max_tokens: int = 1000, min_tokens: int = 200) -> list[Chunk]:
    """Greedy packing in reading order.

    - Never splits a `table` or `code` block, even if it alone exceeds
      `max_tokens` — it becomes its own oversized chunk.
    - Breaks at the best heading boundary available.
    - A trailing chunk under `min_tokens` is merged into the previous one.
    """
    chunks: list[Chunk] = []
    cur_blocks: list[Block] = []
    cur_tokens = 0
    heading_stack: list[str] = []  # list of ancestor heading texts
    cur_path: list[str] = []

    def flush() -> None:
        nonlocal cur_blocks, cur_tokens
        if not cur_blocks:
            return
        text = "\n\n".join(render_block(b) for b in cur_blocks)
        chunks.append(
            Chunk(
                index=len(chunks),
                text=text,
                token_count=count_tokens(text),
                heading_path=list(cur_path),
                page_start=min(b.page_no for b in cur_blocks),
                page_end=max(b.page_no for b in cur_blocks),
                block_ids=[b.id for b in cur_blocks],
                url=doc.url,
            )
        )
        cur_blocks = []
        cur_tokens = 0

    for block in doc.blocks:
        b_tokens = count_tokens(block.text)

        if block.type == "heading":
            flush()
            level = block.level or 1
            # maintain ancestor stack: heading_stack[level-1] is this heading
            heading_stack = heading_stack[: level - 1]
            while len(heading_stack) < level - 1:
                heading_stack.append("")
            heading_stack.append(block.text)
            cur_path = [h for h in heading_stack if h]
            cur_blocks.append(block)
            cur_tokens += b_tokens
            continue

        if block.type in ("table", "code") and b_tokens > max_tokens:
            flush()
            cur_blocks.append(block)
            flush()
            continue

        if cur_tokens + b_tokens > max_tokens and cur_blocks:
            flush()

        cur_blocks.append(block)
        cur_tokens += b_tokens

    flush()

    # Merge a too-small trailing chunk into its predecessor.
    if len(chunks) >= 2 and chunks[-1].token_count < min_tokens:
        last = chunks.pop()
        prev = chunks.pop()
        merged_text = prev.text + "\n\n" + last.text
        chunks.append(
            Chunk(
                index=prev.index,
                text=merged_text,
                token_count=count_tokens(merged_text),
                heading_path=prev.heading_path or last.heading_path,
                page_start=prev.page_start,
                page_end=last.page_end,
                block_ids=[*prev.block_ids, *last.block_ids],
                url=doc.url,
            )
        )

    return chunks
