from page2md.chunk import chunk_document
from page2md.models import Block, Document


def _doc(blocks: list[Block]) -> Document:
    return Document(
        blocks=blocks,
        page_count=1,
        capture=None,
        source_pdf="x.pdf",  # type: ignore[arg-type]
        parser="pymupdf",
        title="t",
        url="https://ex.com",
    )


def _block(i: int, btype: str, text: str, level: int | None = None, page: int = 1) -> Block:
    return Block(id=i, type=btype, text=text, page_no=page, bbox=(0, 0, 1, 1), level=level)  # type: ignore[arg-type]


def test_packing_respects_max_tokens() -> None:
    words = " ".join(["word"] * 600)  # ~600+ tokens
    doc = _doc([_block(i, "paragraph", words) for i in range(4)])
    chunks = chunk_document(doc, max_tokens=700, min_tokens=1)
    assert len(chunks) == 4
    assert all(c.token_count <= 700 for c in chunks)


def test_table_never_split() -> None:
    big_table = "\n".join(f"| r{i} | {('x ' * 50).strip()} |" for i in range(50))
    doc = _doc(
        [
            _block(0, "paragraph", "intro"),
            _block(1, "table", big_table),
            _block(2, "paragraph", "outro"),
        ]
    )
    chunks = chunk_document(doc, max_tokens=200, min_tokens=1)
    table_chunks = [c for c in chunks if "r0" in c.text]
    assert len(table_chunks) == 1
    assert "| r49 " in table_chunks[0].text
    assert table_chunks[0].token_count > 200  # oversized but intact


def test_heading_path_nested() -> None:
    doc = _doc(
        [
            _block(0, "heading", "Top", level=1),
            _block(1, "paragraph", "p1"),
            _block(2, "heading", "Sub", level=2),
            _block(3, "paragraph", "p2"),
        ]
    )
    chunks = chunk_document(doc, max_tokens=10**6, min_tokens=1)
    assert chunks[-1].heading_path == ["Top", "Sub"]


def test_trailing_small_chunk_merges() -> None:
    big = " ".join(["w"] * 500)
    doc = _doc(
        [
            _block(0, "paragraph", big),
            _block(1, "paragraph", big),
            _block(2, "paragraph", "tiny"),
        ]
    )
    chunks = chunk_document(doc, max_tokens=600, min_tokens=200)
    assert len(chunks) == 2
    assert "tiny" in chunks[-1].text
    assert chunks[-1].block_ids == [1, 2]


def test_page_range() -> None:
    doc = _doc([_block(0, "paragraph", "a" * 2000, page=2), _block(1, "paragraph", "b", page=5)])
    chunks = chunk_document(doc, max_tokens=10**6, min_tokens=1)
    assert chunks[0].page_start == 2 and chunks[0].page_end == 5
    assert chunks[0].url == "https://ex.com"
