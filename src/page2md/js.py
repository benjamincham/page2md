"""Builds the Node ESM capture script executed by `ego-browser nodejs -e`.

Pure string construction, no I/O: fully unit-testable. Every interpolated
value goes through ``json.dumps`` so quotes/backslashes in URLs or paths can
never break out of a JavaScript string literal.
"""

from __future__ import annotations

import json
from pathlib import Path


def build_capture_script(
    *,
    url: str,
    pdf_path: Path,
    space: str,
    timeout_ms: int,
    wait_selector: str | None,
    settle_ms: int,
) -> str:
    """Return a self-contained Node ESM script for `ego-browser nodejs -e`."""
    url_js = json.dumps(url)
    path_js = json.dumps(str(pdf_path))
    space_js = json.dumps(space)

    wait_lines = ""
    if wait_selector is not None:
        sel_js = json.dumps(wait_selector)
        wait_lines = (
            f"await page.waitForSelector({sel_js}, {{ state: 'visible', timeout: TIMEOUT_MS }});\n"
        )

    return f"""
const fs = await import("node:fs/promises");
const path = await import("node:path");
const TIMEOUT_MS = {int(timeout_ms)};
const PDF_PATH = {path_js};

const task = await taskSpace({space_js});
try {{
  const page = task.page("p1");
  await page.goto({url_js}, {{ timeout: TIMEOUT_MS, waitUntil: "domcontentloaded" }});
  await page.waitForLoadState("domcontentloaded");
{wait_lines}  await page.waitForTimeout({int(settle_ms)});

  // Best-effort scroll down and back up to trigger lazy-loading. A failure
  // here must never abort the capture.
  try {{
    await page.evaluate(async () => {{
      const step = Math.max(400, Math.floor(window.innerHeight * 0.8));
      for (let y = 0; y < document.body.scrollHeight; y += step) {{
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 80));
      }}
      window.scrollTo(0, 0);
    }});
  }} catch (_scrollErr) {{
  }}

  const res = await page.cdp("Page.printToPDF", {{
    printBackground: true,
    generateTaggedPDF: true,
    generateDocumentOutline: true,
    transferMode: "ReturnAsBase64",
  }});

  const buf = Buffer.from(res.data, "base64");
  await fs.mkdir(path.dirname(PDF_PATH), {{ recursive: true }});
  await fs.writeFile(PDF_PATH, buf);

  console.log("PAGE2MD_META " + JSON.stringify({{
    url: await page.url(),
    title: await page.title(),
    spaceId: task.spaceId,
    page: page.label,
    bytes: buf.length,
  }}));
  await task.finish({{ keep: [] }});
}} catch (err) {{
  // On failure the task space is left open so it can be inspected;
  // the ego-browser skill forbids finish() on error paths.
  console.error("page2md capture failed:", err);
  throw err;
}}
""".lstrip("\n")
