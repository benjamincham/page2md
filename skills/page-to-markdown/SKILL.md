---
name: page-to-markdown
description: Turn any URL into LLM-ready Markdown, structured blocks, and citable chunks with zero LLM tokens. Uses the ego lite browser (`ego-browser` CLI) to print fully-rendered pages to PDF, then a fully local Python layer extracts text, tables, headings, links and token-bounded chunks. Use it whenever you need clean page content for context — reading docs, articles, dashboards, or any rendered page — without spending model tokens on extraction.
---

# page2md

`page2md <url>` prints a rendered page to PDF via ego lite, then converts
the PDF to Markdown + JSON blocks + token-bounded chunks. **No LLM/API calls
anywhere** — extraction is deterministic code (PyMuPDF) or local CPU models.

## Setup (run once)

1. Install the Python CLI:

   ```bash
   bash scripts/bootstrap.sh   # relative to this skill directory
   page2md --version           # verify
   ```

   Idempotent — re-running is safe. Tries `uv tool`, `pipx`, then
   `pip install --user` (needs Python 3.10+). Install from a local checkout
   with `PAGE2MD_SOURCE=/path/to/page2md bash scripts/bootstrap.sh`.

2. Before the first `url`/`batch` capture, install/verify ego lite:

   ```bash
   bash scripts/ensure-ego.sh
   ```

   It resolves `ego-browser` (PATH or `~/.local/bin`), or installs ego lite
   via ego's own installer on macOS. **Gate:** never run `page2md url` /
   `batch` without first confirming `command -v ego-browser`. If it is
   missing, run `scripts/ensure-ego.sh`; if that reports onboarding pending,
   STOP and tell the user to finish onboarding in the ego lite window — do
   not retry the capture blindly.

## Caveat: capture is macOS-only

The `url` and `batch` subcommands drive ego lite, which runs only on macOS.
On other platforms, capture elsewhere and use `page2md parse <pdf>` —
the entire distillation stage works on any OS.

## Commands

```bash
# Capture a URL and distill it (macOS + ego lite required)
page2md url "https://example.com/article" --out ./out --json

# Distill an already-captured PDF (runs anywhere, no browser needed)
page2md parse ./page.pdf --url "https://example.com/article" --out ./out --json

# Distill many URLs; sequential by default (task spaces are stateful)
page2md batch urls.txt --out ./out --json

# Parallel captures: each URL gets its own space <space>-<i>
page2md batch urls.txt --out ./out --concurrency 4 --json
```

Useful flags: `--wait-selector CSS` (wait for an element before printing),
`--timeout-ms N`, `--space NAME` (ego task space), `--max-tokens N`
(chunk size, default 1000), `--deep` (docling parser, `pip install 'page2md[deep]'`).

## Output

Each run writes `out/<slug>/` containing `page.pdf`, `page.md`,
`page.json` (document + typed blocks with bboxes/links), `chunks.jsonl`
(citable chunks with `heading_path`, page range, block ids) and
`capture.json` (provenance). With `--json`, stdout is a single JSON object
of those paths — parse it, then read the files you need:

```bash
page2md parse report.pdf --out ./out --json
# {"out_dir": "...", "pdf": "...", "markdown": "...", "document_json": "...",
#  "chunks_jsonl": "...", "capture_json": "..."}
```

Exit code is 0 on success, 1 with a one-line stderr message on capture or
parse failure. Prefer `page.md` for reading; `chunks.jsonl` when you need
to cite or budget tokens.
