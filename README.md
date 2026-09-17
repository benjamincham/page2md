# page2md

**page2md** converts any web page into clean, LLM-ready Markdown. It renders the page to a PDF using the ego lite browser, then extracts structured Markdown, typed block annotations, and token-bounded citable chunks — entirely on your local machine, with no LLM or API calls.

## Who is this for

Developers and agents that need deterministic, reproducible web-page extraction: content pipelines, RAG ingestion, automated research agents, or any workflow where you need a page's text without burning LLM tokens on HTML parsing.

## Using with an agent

Once the skill is installed, just tell the agent what you want:

```
use page2md, grab the md for https://example.com
```

The agent handles the rest — capturing, extracting, and returning the Markdown.

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10 or later** | Required for the CLI and Python API |
| **macOS** | Required for `url` and `batch` capture — ego lite is macOS-only. `page2md parse` works on any OS. |
| **ego lite** | The `ego-browser` CLI must be on your PATH. Install from [citrolabs/ego-lite](https://github.com/citrolabs/ego-lite), then run `scripts/ensure-ego.sh` to verify. Onboarding requires a one-time manual step in the ego lite GUI window. |

> **Tip:** If you only need to distill an already-captured PDF, `page2md parse <pdf>` works on any OS and does not require ego lite.

## Install

```bash
pip install -e .            # base: pymupdf, pymupdf4llm, tiktoken
pip install -e '.[deep]'    # optional docling deep parser (local CPU models)
pip install -e '.[dev]'     # dev tools: pytest, ruff, mypy
```

> **Note:** page2md is not published to PyPI — install from a local checkout or a git URL.

### Install as an agent skill

page2md ships a skill under `skills/page-to-markdown/`, installable with the `skills` CLI:

```bash
npx skills add <repo-url> --skill page-to-markdown        # project scope
npx skills add <repo-url> --skill page-to-markdown -g     # global
```

After installing the skill, run the bootstrap script once to install the Python CLI (tries `uv tool`, `pipx`, then `pip install --user`):

```bash
bash <installed-skill-dir>/scripts/bootstrap.sh
page2md --version
```

To install from a local checkout instead of the default source:

```bash
PAGE2MD_SOURCE=/path/to/page2md bash scripts/bootstrap.sh
```

## Usage

```bash
# Capture a URL and distill it (macOS + ego lite required)
page2md url "https://example.com" --out out --json

# Distill many URLs sequentially
page2md batch urls.txt --out out --json

# Distill an already-captured PDF (runs anywhere, no ego lite needed)
page2md parse page.pdf --url "https://example.com" --out out --json
```

Useful flags: `--wait-selector CSS`, `--timeout-ms N`, `--space NAME` (ego task space), `--max-tokens N` (chunk size, default 1000), `--deep` (docling parser).

### Output

Each run writes `out/<slug>/`:

| File | Contents |
|---|---|
| `page.pdf` | Captured PDF |
| `page.md` | LLM-ready Markdown with YAML front matter |
| `page.json` | Document + typed blocks (heading levels, bboxes, links) |
| `chunks.jsonl` | Token-bounded citable chunks with `heading_path` and page range |
| `capture.json` | Provenance: final URL, title, timestamp, backend |

With `--json`, stdout is a single JSON object containing all output paths.

## Python API

```python
from page2md import distill_url, distill_pdf

result = distill_url("https://example.com", "out")   # macOS + ego lite
result = distill_pdf("page.pdf", "out")              # any OS
```

## Licence

MIT — see [`LICENSE`](LICENSE).
