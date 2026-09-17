import json
from pathlib import Path

import pymupdf as fitz

from page2md.cli import main


def _pdf(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Title", fontsize=20)
    page.insert_text((72, 200), "Some body text for the parser.", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_parse_subcommand(tmp_path: Path, capsys) -> None:
    pdf = _pdf(tmp_path / "in.pdf")
    out = tmp_path / "out"
    rc = main(["parse", str(pdf), "--url", "https://ex.com", "--out", str(out)])
    assert rc == 0

    dirs = list(out.iterdir())
    assert len(dirs) == 1
    d = dirs[0]
    for name in ("page.md", "page.json", "chunks.jsonl", "capture.json"):
        assert (d / name).exists(), name
    assert "# Title" in (d / "page.md").read_text()
    rec = json.loads((d / "chunks.jsonl").read_text().splitlines()[0])
    assert rec["url"] == "https://ex.com"
    page_json = json.loads((d / "page.json").read_text())
    assert page_json["blocks"]


def test_parse_json_flag(tmp_path: Path, capsys) -> None:
    pdf = _pdf(tmp_path / "in.pdf")
    out = tmp_path / "out"
    capsys.readouterr()
    rc = main(["parse", str(pdf), "--out", str(out), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert Path(payload["markdown"]).exists()
    assert payload["capture_json"]


def test_parse_error_exit_1(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    capsys.readouterr()
    rc = main(["parse", str(bad), "--out", str(tmp_path / "o")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "page2md:" in err
    assert "Traceback" not in err


FAKE_EGO = """\
#!{python}
import json, re, sys

script = sys.argv[sys.argv.index("-e") + 1]
pdf_path = json.loads(re.search(r'PDF_PATH = (".*");', script).group(1))
url = json.loads(re.search(r'page\\.goto\\((".*?")', script).group(1))
if "fail" in url:
    sys.stderr.write("boom")
    sys.exit(3)

import pymupdf as fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 100), "Title", fontsize=20)
page.insert_text((72, 200), "Body text that outweighs title.", fontsize=10)
doc.save(pdf_path)
print("PAGE2MD_META " + json.dumps({{"url": url, "title": "T", "bytes": 1}}))
"""


def _fake_ego(tmp_path: Path) -> str:
    import stat
    import sys

    path = tmp_path / "ego-browser"
    path.write_text(FAKE_EGO.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def _patch_backend(monkeypatch, fake: str) -> None:
    import page2md.cli as cli
    from page2md.capture import EgoCapture

    monkeypatch.setattr(cli, "EgoCapture", lambda: EgoCapture(binary=fake))


def test_batch_partial_failure_exit_1(tmp_path: Path, capsys, monkeypatch) -> None:
    _patch_backend(monkeypatch, _fake_ego(tmp_path))
    urls = tmp_path / "urls.txt"
    urls.write_text("https://ok.example/\nhttps://fail.example/\n")
    capsys.readouterr()
    rc = main(["batch", str(urls), "--out", str(tmp_path / "o"), "--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["failures"] == 1
    assert payload["results"][0]["ok"] is True
    assert payload["results"][1]["ok"] is False


def test_batch_concurrency_preserves_order(tmp_path: Path, capsys, monkeypatch) -> None:
    _patch_backend(monkeypatch, _fake_ego(tmp_path))
    urls = [f"https://u{i}.example/" for i in range(4)]
    f = tmp_path / "urls.txt"
    f.write_text("\n".join(urls) + "\n")
    capsys.readouterr()
    rc = main(["batch", str(f), "--out", str(tmp_path / "o"), "--concurrency", "3", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["url"] for r in payload["results"]] == urls
    assert all(r["ok"] for r in payload["results"])
