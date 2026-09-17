from page2md.layout import (
    body_font_size,
    boilerplate_lines,
    infer_heading_level,
    is_page_number,
    normalize_text,
)


def _span(text: str, size: float, flags: int = 0, font: str = "Helvetica") -> dict:
    return {"text": text, "size": size, "flags": flags, "font": font}


def test_body_font_size_char_weighted() -> None:
    spans = [
        _span("a" * 100, 10.0),
        _span("b" * 5, 10.0),
        _span("TITLE", 20.0),  # 3 spans of size 20 but few chars
        _span("TITLE", 20.0),
        _span("TITLE", 20.0),
    ]
    assert body_font_size(spans) == 10.0


def test_body_font_size_empty() -> None:
    assert body_font_size([]) == 0.0


def test_heading_thresholds() -> None:
    body = 10.0
    assert infer_heading_level(18.0, body, False) == 1
    assert infer_heading_level(15.0, body, False) == 2
    assert infer_heading_level(13.0, body, False) == 3
    assert infer_heading_level(11.5, body, False) == 4
    assert infer_heading_level(10.5, body, True) == 5
    # bold requirement for level 5
    assert infer_heading_level(10.5, body, False) is None
    # plain body text (ratio 1.0, even when bold) is not a heading
    assert infer_heading_level(10.0, body, True) is None
    assert infer_heading_level(9.0, body, False) is None
    # degenerate sizes
    assert infer_heading_level(0.0, body, True) is None
    assert infer_heading_level(20.0, 0.0, True) is None


def test_boilerplate_strips_footer() -> None:
    pages = [[f"Content {i}", f"My Footer {i}"] for i in range(6)]
    # footer text differs only by digit -> normalised to '#'
    stripped = boilerplate_lines(pages, min_pages=3, ratio=0.6)
    assert "my footer #" in stripped
    assert "content #" in stripped  # also repeats -> boilerplate by rule


def test_boilerplate_keeps_rare_line() -> None:
    pages = [["Common", f"Body {i}"] for i in range(5)] + [["Unique", "Body x"]]
    stripped = boilerplate_lines(pages)
    assert "common" in stripped
    assert "unique" not in stripped


def test_boilerplate_never_empties_page() -> None:
    pages = [["Only line"]] * 6
    stripped = boilerplate_lines(pages)
    assert stripped == set()


def test_boilerplate_min_pages() -> None:
    pages = [["x", "y"], ["x", "z"]]
    assert boilerplate_lines(pages, min_pages=3) == set()


def test_normalize_text() -> None:
    assert normalize_text("\ufb01nd") == "find"
    assert normalize_text("o\ufb00ensive") == "offensive"
    assert normalize_text("a\u00a0b") == "a b"  # nbsp -> space
    assert normalize_text("a\u200bb") == "ab"  # zero-width dropped
    assert normalize_text("\u2460") == "1"  # NFKC compatibility


def test_is_page_number() -> None:
    assert is_page_number("3")
    assert is_page_number("Page 12")
    assert is_page_number("3/10")
    assert is_page_number("3 of 10")
    assert not is_page_number("Chapter 3 begins")
    assert not is_page_number("")
