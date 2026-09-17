from pathlib import Path

from page2md.markdown import document_to_markdown
from page2md.models import Block, Capture, Document


def _doc(blocks: list[Block]) -> Document:
    cap = Capture(
        url="https://ex.com/a",
        requested_url="https://ex.com/a",
        title="T",
        captured_at="2026-01-01T00:00:00+00:00",
        backend="ego-browser",
        pdf_path=Path("p.pdf"),
        space_id="7",
        page_label="p1",
    )
    return Document(
        blocks=blocks,
        page_count=3,
        capture=cap,
        source_pdf=Path("p.pdf"),
        parser="pymupdf",
        title="T",
        url="https://ex.com/a",
    )


def test_front_matter() -> None:
    md = document_to_markdown(_doc([]))
    assert md.startswith("---\n")
    fm = md.split("---\n")[1]
    assert 'url: "https://ex.com/a"' in fm
    assert 'parser: "pymupdf"' in fm
    assert 'page_count: "3"' in fm
    assert 'captured_at: "2026-01-01T00:00:00+00:00"' in fm


def test_heading_levels() -> None:
    doc = _doc(
        [
            Block(id=0, type="heading", text="H1", page_no=1, bbox=(0, 0, 1, 1), level=1),
            Block(id=1, type="heading", text="H3", page_no=1, bbox=(0, 0, 1, 1), level=3),
            Block(id=2, type="paragraph", text="body", page_no=1, bbox=(0, 0, 1, 1)),
            Block(id=3, type="list_item", text="- item", page_no=1, bbox=(0, 0, 1, 1)),
        ]
    )
    md = document_to_markdown(doc)
    assert "\n# H1\n" in md
    assert "\n### H3\n" in md
    assert "\nbody\n" in md
    assert "- item" in md


def test_list_marker_stripped_by_regex() -> None:
    doc = _doc(
        [
            Block(
                id=0,
                type="list_item",
                text="1. 4x faster",
                page_no=1,
                bbox=(0, 0, 1, 1),
            ),
            Block(
                id=1,
                type="list_item",
                text="- 2023",
                page_no=1,
                bbox=(0, 0, 1, 1),
            ),
        ]
    )
    md = document_to_markdown(doc)
    assert "- 4x faster" in md  # digit content must survive the strip
    assert "- 2023" in md


def test_table_verbatim() -> None:
    table_md = "| a | b |\n|---|---|\n| 1 | 2 |"
    doc = _doc([Block(id=0, type="table", text=table_md, page_no=1, bbox=(0, 0, 1, 1))])
    md = document_to_markdown(doc)
    assert table_md in md


def test_code_fenced() -> None:
    doc = _doc([Block(id=0, type="code", text="x = 1", page_no=1, bbox=(0, 0, 1, 1))])
    md = document_to_markdown(doc)
    assert "```\nx = 1\n```" in md
