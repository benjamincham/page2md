from pathlib import Path

import pymupdf as fitz
import pytest

from page2md.errors import ParseError
from page2md.parse import parse_pdf


def _make_pdf(path: Path, pages: list[list[tuple[str, float, tuple[float, float]]]]) -> Path:
    """pages: list of [(text, fontsize, (x, y))]."""
    doc = fitz.open()
    for entries in pages:
        page = doc.new_page()
        for text, size, pos in entries:
            page.insert_text(pos, text, fontsize=size)
    doc.save(path)
    doc.close()
    return path


def test_headings_and_paragraph(tmp_path: Path) -> None:
    pdf = _make_pdf(
        tmp_path / "doc.pdf",
        [
            [
                ("Big Title", 20.0, (72, 100)),
                ("Section One", 15.0, (72, 160)),
                ("Body text here stays a paragraph.", 10.0, (72, 220)),
            ]
        ],
    )
    doc = parse_pdf(pdf)
    assert doc.parser == "pymupdf"
    assert doc.page_count == 1
    assert len(doc.blocks) == 3
    h1, h2, para = doc.blocks
    assert h1.type == "heading" and h1.level == 1 and h1.text == "Big Title"
    assert h2.type == "heading" and h2.level == 2
    assert para.type == "paragraph"
    for b in doc.blocks:
        assert b.page_no == 1
        x0, y0, x1, y1 = b.bbox
        assert x1 > x0 and y1 > y0  # non-degenerate


def test_repeated_footer_stripped(tmp_path: Path) -> None:
    bodies = ["alpha", "beta", "gamma", "delta", "eps", "zeta"]
    pdf = _make_pdf(
        tmp_path / "foot.pdf",
        [
            [
                (f"Unique {w} content about topic.", 10.0, (72, 200)),
                ("ACME Corp", 8.0, (72, 780)),
            ]
            for w in bodies
        ],
    )
    doc = parse_pdf(pdf)
    texts = [b.text for b in doc.blocks]
    assert all("ACME" not in t for t in texts)
    assert len(doc.blocks) == 6
    assert [b.page_no for b in doc.blocks] == [1, 2, 3, 4, 5, 6]


def test_link_attached_to_block(tmp_path: Path) -> None:
    path = tmp_path / "link.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Read more details here.", fontsize=10)
    page.insert_text((72, 200), "Other text.", fontsize=10)
    # Cover the first line with a link rect.
    link_rect = fitz.Rect(72, 88, 300, 104)
    page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": "https://ex.com/x"})
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    linked = [b for b in parsed.blocks if b.links]
    assert len(linked) == 1
    assert "Read more" in linked[0].text
    assert linked[0].links[0]["uri"] == "https://ex.com/x"


def test_two_column_reading_order(tmp_path: Path) -> None:
    path = tmp_path / "cols.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Interleaved textboxes; column repair must order L1..L3 then R1..R3.
    for text, rect in [
        ("L1", fitz.Rect(60, 90, 300, 110)),
        ("R1", fitz.Rect(350, 90, 560, 110)),
        ("L2", fitz.Rect(60, 190, 300, 210)),
        ("R2", fitz.Rect(350, 190, 560, 210)),
        ("L3", fitz.Rect(60, 290, 300, 310)),
        ("R3", fitz.Rect(350, 290, 560, 310)),
    ]:
        page.insert_textbox(rect, text, fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    texts = [b.text for b in parsed.blocks]
    assert texts == ["L1", "L2", "L3", "R1", "R2", "R3"]


def test_missing_pdf_raises(tmp_path: Path) -> None:
    with pytest.raises(ParseError):
        parse_pdf(tmp_path / "nope.pdf")


def test_table_block_single(tmp_path: Path) -> None:
    path = tmp_path / "t.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Draw a real ruled grid; pymupdf4llm detects tables from vector lines.
    xs = [72.0, 200.0, 400.0]
    ys = [100.0, 140.0, 180.0]
    for y in ys:
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y))
    for x in xs:
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]))
    for (r, c), text in {
        (0, 0): "Name",
        (0, 1): "Age",
        (1, 0): "Ada",
        (1, 1): "36",
    }.items():
        page.insert_text((xs[c] + 5, ys[r] + 15), text, fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    tables = [b for b in parsed.blocks if b.type == "table"]
    assert len(tables) == 1
    assert "|" in tables[0].text and "Ada" in tables[0].text


def test_numbered_heading_merged(tmp_path: Path) -> None:
    path = tmp_path / "num.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 90, 400, 140), "2.1\nMethod", fontsize=15)
    page.insert_text((72, 220), "Body text here.", fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    headings = [b for b in parsed.blocks if b.type == "heading"]
    assert len(headings) == 1
    assert headings[0].text == "2.1 Method"
    assert headings[0].level == 2


def test_two_line_same_size_heading(tmp_path: Path) -> None:
    path = tmp_path / "two.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 90, 400, 140), "Deep\nDive", fontsize=15)
    page.insert_text((72, 220), "Body text here.", fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    headings = [b for b in parsed.blocks if b.type == "heading"]
    assert len(headings) == 1
    assert headings[0].text == "Deep Dive"


def test_paragraph_soft_wrap_and_dehyphenation(tmp_path: Path) -> None:
    path = tmp_path / "wrap.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(72, 90, 400, 160),
        "A multi-\nline para-\ngraph here.",
        fontsize=10,
    )
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].type == "paragraph"
    assert parsed.blocks[0].text == "A multiline paragraph here."


def test_title_fallback_to_first_heading(tmp_path: Path) -> None:
    path = tmp_path / "title.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "The Real Title", fontsize=20)
    page.insert_text((72, 200), "Body text that outweighs the title by far.", fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    assert parsed.title == "The Real Title"


def test_pymupdf4llm_page_number_mapping(tmp_path: Path) -> None:
    """A table on page 3 must land on a page-3 table block — proves the
    `metadata.page_number` keying maps 4llm chunks to the right page."""
    path = tmp_path / "p3.pdf"
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page()
        page.insert_text((72, 100), "filler text", fontsize=10)
    page = doc.new_page()
    xs = [72.0, 200.0, 400.0]
    ys = [100.0, 140.0, 180.0]
    for y in ys:
        page.draw_line(fitz.Point(xs[0], y), fitz.Point(xs[-1], y))
    for x in xs:
        page.draw_line(fitz.Point(x, ys[0]), fitz.Point(x, ys[-1]))
    cells = {(0, 0): "Name", (0, 1): "Value", (1, 0): "alpha", (1, 1): "beta"}
    for (r, c), text in cells.items():
        page.insert_text((xs[c] + 5, ys[r] + 15), text, fontsize=10)
    doc.save(path)
    doc.close()

    parsed = parse_pdf(path)
    tables = [b for b in parsed.blocks if b.type == "table"]
    assert len(tables) == 1
    assert tables[0].page_no == 3


def test_two_column_false_positive_guard() -> None:
    from page2md.parse import _looks_two_column

    def ln(x0: float, x1: float) -> dict:
        return {"bbox": (x0, 50.0, x1, 60.0)}

    left = [ln(60, 300) for _ in range(4)]
    # Balanced columns -> two column
    assert _looks_two_column(left + [ln(350, 560) for _ in range(4)])
    # 4 vs 1: smaller cluster below 3 -> not two column
    assert not _looks_two_column(left + [ln(350, 560)])
    # 8 vs 2: smaller cluster >= 3 fails even though 25% is 2
    assert not _looks_two_column([ln(60, 300) for _ in range(8)] + [ln(350, 560) for _ in range(2)])


def _two_page(path: Path, p1_text: str, p2_text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 720), p1_text, fontsize=10)
    page = doc.new_page()
    page.insert_text((72, 100), p2_text, fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_paragraph_stitched_across_page_break(tmp_path: Path) -> None:
    pdf = _two_page(
        tmp_path / "st.pdf",
        "This sentence runs past the page break and",
        "continues on the next page.",
    )
    parsed = parse_pdf(pdf)
    assert len(parsed.blocks) == 1
    b = parsed.blocks[0]
    assert b.type == "paragraph"
    assert b.text == "This sentence runs past the page break and continues on the next page."
    assert b.page_span == (1, 2)
    assert b.page_no == 1
    assert b.id == 0  # ids stay dense


def test_paragraph_not_stitched_after_full_stop(tmp_path: Path) -> None:
    pdf = _two_page(
        tmp_path / "ns.pdf",
        "This sentence is complete.",
        "Next one starts here.",
    )
    parsed = parse_pdf(pdf)
    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].page_span is None
    assert [b.id for b in parsed.blocks] == [0, 1]
