"""Stage 1: drive `ego-browser` to print a fully-rendered page to PDF."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .errors import CaptureError
from .js import build_capture_script
from .models import Capture

META_PREFIX = "PAGE2MD_META "

_EGO_MISSING_MSG = (
    "`ego-browser` not found on PATH or in ~/.local/bin. Capture needs "
    "macOS with ego lite installed — run the skill's "
    "`scripts/ensure-ego.sh` to install it (onboarding is a manual step). "
    "On other platforms `page2md parse <pdf>` works anywhere."
)


def _resolve_binary(binary: str) -> str:
    """PATH lookup, then the standard ~/.local/bin fallback."""
    found = shutil.which(binary)
    if found:
        return found
    local = Path.home() / ".local" / "bin" / binary
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    raise CaptureError(_EGO_MISSING_MSG)


@dataclass
class EgoCapture:
    """Captures URLs to PDF via the ego-browser CLI."""

    binary: str = "ego-browser"

    def capture(
        self,
        url: str,
        out_dir: Path | str,
        *,
        space: str = "page2md",
        timeout_ms: int = 45_000,
        wait_selector: str | None = None,
        settle_ms: int = 1200,
    ) -> Capture:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "page.pdf"

        script = build_capture_script(
            url=url,
            pdf_path=pdf_path,
            space=space,
            timeout_ms=timeout_ms,
            wait_selector=wait_selector,
            settle_ms=settle_ms,
        )

        binary = _resolve_binary(self.binary)

        try:
            proc = subprocess.run(
                [binary, "nodejs", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000 + 60,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CaptureError(_EGO_MISSING_MSG) from exc
        except subprocess.TimeoutExpired as exc:
            raise CaptureError(
                f"ego-browser capture of {url} timed out after {timeout_ms} ms"
            ) from exc

        stderr_tail = (proc.stderr or "")[-2000:].strip()

        if "[ego-browser:notice]" in (proc.stdout or "") or "[ego-browser:notice]" in (
            proc.stderr or ""
        ):
            warnings.warn(
                "An ego lite upgrade is available; run `ego-browser upgrade`.",
                stacklevel=2,
            )

        meta: dict[str, object] | None = None
        all_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in all_output.splitlines():
            if line.startswith(META_PREFIX):
                try:
                    meta = json.loads(line[len(META_PREFIX) :])
                except json.JSONDecodeError:
                    meta = None

        if proc.returncode != 0 and meta is None:
            raise CaptureError(
                f"ego-browser exited with code {proc.returncode} for {url}.\n{stderr_tail}"
            )

        if meta is None:
            raise CaptureError(
                f"ego-browser did not emit a {META_PREFIX.strip()} line for {url}.\n{stderr_tail}"
            )

        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise CaptureError(
                f"ego-browser reported success but produced no PDF at {pdf_path}.\n{stderr_tail}"
            )

        return Capture(
            url=str(meta.get("url") or url),
            requested_url=url,
            title=str(meta.get("title") or ""),
            captured_at=datetime.now(timezone.utc).isoformat(),
            backend="ego-browser",
            pdf_path=pdf_path,
            space_id=str(meta["spaceId"]) if meta.get("spaceId") is not None else None,
            page_label=str(meta["page"]) if meta.get("page") is not None else None,
        )
