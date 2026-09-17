# page2md

[![npm](https://img.shields.io/npm/v/page2md-cli?label=npm%20page2md-cli)](https://www.npmjs.com/package/page2md-cli)
[![skills.sh](https://skills.sh/b/benjamincham/page2md)](https://skills.sh/benjamincham/page2md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**page2md is an agent skill** that turns any web page into clean, LLM-ready Markdown. Install it once and your AI agent (Claude Code, Cursor, Codex, pi, …) can grab any URL as structured Markdown, typed blocks, and token-bounded citable chunks — on demand, in natural language.

It renders the page to PDF with the ego lite browser, then a fully local extraction layer (PyMuPDF — no LLM, no API calls, zero model tokens) distills it into:

- `page.md` — clean Markdown with YAML front matter
- `page.json` — typed blocks with heading levels, bounding boxes, links
- `chunks.jsonl` — token-bounded chunks with `heading_path` for precise citation and context budgeting

## Who is this for

Agents and the developers who direct them: RAG ingestion, research workflows, content pipelines, or any task where an agent needs a page's *content* without burning tokens parsing HTML.

## Install the skill for your agent

page2md ships as an [Agent Skill](https://agentskills.io) — a `SKILL.md` folder your agent loads dynamically. Install it with the [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add benjamincham/page2md --skill page-to-markdown        # this project
npx skills add benjamincham/page2md --skill page-to-markdown -g     # all your agents, user-level
```

The CLI auto-detects installed agents (Claude Code, Cursor, Codex, …) and installs the skill into their skills directories. List what a repo offers before installing:

```bash
npx skills add benjamincham/page2md -l
```

**No install needed?** Generate a one-shot prompt with the skill's instructions instead:

```bash
npx skills use benjamincham/page2md@page-to-markdown
```

## Using with an agent

Once the skill is installed, just tell the agent what you want — no special syntax:

```
use page2md, grab the md for https://example.com
```

```
fetch https://docs.example.com/guide with page2md and give me the chunks under 500 tokens
```

The agent handles the rest — capturing the page, extracting, and returning the Markdown. It reads the skill's `SKILL.md` for the exact commands, gates and output paths.

> **For agents:** the skill folder is `skills/page-to-markdown/` in this repo. Point an agent at this repository and it can bootstrap itself — `SKILL.md` contains the full setup and usage protocol.

## Quick install (CLI, via npx)

The same engine is available as a plain CLI, no agent required.

Run the following command in your terminal to install page2md globally:

```bash
npm install -g page2md-cli@latest
```

That puts `page2md` (and `page2md-cli`) on your PATH. The npm package is a thin launcher: on first run it installs the Python CLI once (via `uv tool`, `pipx`, or `pip --user`) from this repo's git URL, then forwards everything to it. Subsequent runs skip straight to the CLI. Set `PAGE2MD_SOURCE` to install from a different source (e.g. a fork or local checkout).

Prefer not to install anything? Run it straight away with npx:

```bash
npx page2md-cli url "https://example.com" --out out --json
```

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10 or later** | Required for the CLI and Python API |
| **macOS** | Required for `url` and `batch` capture — ego lite is macOS-only. `page2md parse` works on any OS. |
| **ego lite** | The `ego-browser` CLI must be on your PATH. Install from [citrolabs/ego-lite](https://github.com/citrolabs/ego-lite), then run `scripts/ensure-ego.sh` to verify. Onboarding requires a one-time manual step in the ego lite GUI window. |

> **Tip:** If you only need to distill an already-captured PDF, `page2md parse <pdf>` works on any OS and does not require ego lite.

## Install (pip)

```bash
pip install -e .            # base: pymupdf, pymupdf4llm, tiktoken
pip install -e '.[deep]'    # optional docling deep parser (local CPU models)
pip install -e '.[dev]'     # dev tools: pytest, ruff, mypy
```

> **Note:** page2md is not published to PyPI — install the skill or CLI as above, or `pip install` from a local checkout / git URL.

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
