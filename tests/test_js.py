import json
from pathlib import Path

from page2md.js import build_capture_script


def test_script_contains_required_parts(tmp_path: Path) -> None:
    script = build_capture_script(
        url="https://example.com/a?b=1",
        pdf_path=tmp_path / "out" / "page.pdf",
        space="page2md",
        timeout_ms=45000,
        wait_selector="#main",
        settle_ms=1200,
    )
    assert 'taskSpace("page2md")' in script
    assert 'task.page("p1")' in script
    assert 'page.goto("https://example.com/a?b=1"' in script
    assert 'waitForLoadState("load")' in script
    assert 'waitForSelector("#main"' in script
    assert "waitForTimeout(1200)" in script
    assert "page.evaluate" in script
    assert 'page.cdp("Page.printToPDF"' in script
    assert "generateTaggedPDF: true" in script
    assert '"ReturnAsBase64"' in script
    assert "node:fs/promises" in script
    assert "PAGE2MD_META " in script
    assert "task.finish({ keep: [] })" in script
    # finish() runs only on the success path; errors keep the space open
    assert "console.error" in script
    assert "throw err" in script
    assert "finally" not in script
    assert json.dumps(str(tmp_path / "out" / "page.pdf")) in script


def test_no_wait_selector_line_when_absent(tmp_path: Path) -> None:
    script = build_capture_script(
        url="https://x.example",
        pdf_path=tmp_path / "p.pdf",
        space="s",
        timeout_ms=1000,
        wait_selector=None,
        settle_ms=0,
    )
    assert "waitForSelector" not in script


def test_url_with_quotes_round_trips(tmp_path: Path) -> None:
    evil_url = "https://example.com/it's \"quoted\"?a='b'"
    evil_path = tmp_path / "we 'ird" / 'pa"th' / "page.pdf"
    script = build_capture_script(
        url=evil_url,
        pdf_path=evil_path,
        space="sp'ace",
        timeout_ms=1000,
        wait_selector="div[x='1']",
        settle_ms=10,
    )
    # Every interpolated value must appear as its exact JSON literal —
    # json.dumps output is always a valid JS string literal.
    for value in (evil_url, str(evil_path), "sp'ace", "div[x='1']"):
        assert json.dumps(value) in script
