import stat
import sys
from pathlib import Path

import pytest

from page2md.capture import EgoCapture
from page2md.errors import CaptureError

FAKE_OK = """\
#!{python}
import json, re, sys

script = sys.argv[sys.argv.index("-e") + 1]
m = re.search(r'PDF_PATH = (".*");', script)
pdf_path = json.loads(m.group(1))

import pymupdf as fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "hello")
doc.save(pdf_path)

print("PAGE2MD_META " + json.dumps({{
    "url": "https://final.example/page",
    "title": "A Title",
    "spaceId": 7,
    "page": "p1",
    "bytes": 1234,
}}))
"""

FAKE_EXIT = "#!/bin/sh\necho boom >&2\nexit 3\n"
FAKE_NO_META = "#!/bin/sh\necho nothing\n"
FAKE_EMPTY_PDF = """\
#!{python}
import json, re, sys
script = sys.argv[sys.argv.index("-e") + 1]
pdf_path = json.loads(re.search(r'PDF_PATH = (".*");', script).group(1))
open(pdf_path, "wb").close()
print("PAGE2MD_META " + json.dumps({{"url": "u", "title": "t", "bytes": 0}}))
"""


def _make_fake(tmp_path: Path, body: str, name: str = "ego-browser") -> str:
    path = tmp_path / name
    path.write_text(body.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def test_capture_success(tmp_path: Path) -> None:
    fake = _make_fake(tmp_path, FAKE_OK)
    cap = EgoCapture(binary=fake).capture("https://example.com", tmp_path / "out", timeout_ms=5000)
    assert cap.url == "https://final.example/page"
    assert cap.requested_url == "https://example.com"
    assert cap.title == "A Title"
    assert cap.backend == "ego-browser"
    assert cap.space_id == "7"
    assert cap.page_label == "p1"
    assert cap.captured_at
    assert Path(cap.pdf_path).stat().st_size > 0


def test_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(CaptureError, match="macOS"):
        EgoCapture(binary="/nonexistent/ego-browser").capture(
            "https://x", tmp_path / "o", timeout_ms=1000
        )


def test_nonzero_exit(tmp_path: Path) -> None:
    fake = _make_fake(tmp_path, FAKE_EXIT)
    with pytest.raises(CaptureError, match="boom"):
        EgoCapture(binary=fake).capture("https://x", tmp_path / "o", timeout_ms=1000)


def test_no_meta_line(tmp_path: Path) -> None:
    fake = _make_fake(tmp_path, FAKE_NO_META)
    with pytest.raises(CaptureError, match="PAGE2MD_META"):
        EgoCapture(binary=fake).capture("https://x", tmp_path / "o", timeout_ms=1000)


def test_empty_pdf(tmp_path: Path) -> None:
    fake = _make_fake(tmp_path, FAKE_EMPTY_PDF)
    with pytest.raises(CaptureError, match="no PDF"):
        EgoCapture(binary=fake).capture("https://x", tmp_path / "o", timeout_ms=1000)


def test_upgrade_notice_warns(tmp_path: Path) -> None:
    body = FAKE_OK.replace(
        'print("PAGE2MD_META',
        'print("[ego-browser:notice] upgrade available")\nprint("PAGE2MD_META',
    )
    fake = _make_fake(tmp_path, body)
    with pytest.warns(UserWarning, match="upgrade"):
        EgoCapture(binary=fake).capture("https://x", tmp_path / "o", timeout_ms=5000)


def test_local_bin_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ego-browser not on PATH but executable at ~/.local/bin is used."""
    fake = _make_fake(tmp_path, FAKE_OK, name="ego-browser-src")
    local_bin = tmp_path / "home" / ".local" / "bin"
    local_bin.mkdir(parents=True)
    target = local_bin / "ego-browser"
    target.write_text(Path(fake).read_text())
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.delenv("PATH", raising=False)

    import os

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = "/nonexistent-dir"
    try:
        cap = EgoCapture().capture("https://example.com", tmp_path / "out", timeout_ms=5000)
    finally:
        os.environ["PATH"] = old_path
    assert cap.title == "A Title"
