"""`page2md` command line interface (stdlib argparse only)."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as metadata_version
from pathlib import Path

from . import __version__
from .capture import EgoCapture
from .errors import Page2mdError
from .pipeline import DistillResult, distill_pdf, distill_url


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default="page2md-out", help="output root directory")
    p.add_argument("--deep", action="store_true", help="use the docling deep parser")
    p.add_argument("--max-tokens", type=int, default=1000)
    p.add_argument("--json", action="store_true", help="print machine-readable result")


def _add_capture(p: argparse.ArgumentParser) -> None:
    p.add_argument("--space", default="page2md", help="ego task space name")
    p.add_argument("--timeout-ms", type=int, default=45_000)
    p.add_argument("--wait-selector", default=None)


def _version() -> str:
    try:
        return metadata_version("page2md")
    except PackageNotFoundError:
        return __version__


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="page2md",
        description=(
            "URL -> ego-browser PDF -> fully local Markdown/blocks/chunks. "
            "No LLM calls anywhere. NOTE: capture (the `url`/`batch` commands) "
            "requires ego lite, which is macOS-only; `parse` runs anywhere."
        ),
    )
    ap.add_argument("--version", action="version", version=f"page2md {_version()}")
    sub = ap.add_subparsers(dest="command", required=True)

    p_url = sub.add_parser("url", help="capture one URL and distill it")
    p_url.add_argument("url")
    _add_common(p_url)
    _add_capture(p_url)

    p_batch = sub.add_parser(
        "batch",
        help="distill a file of URLs, one per line ('-' for stdin)",
    )
    p_batch.add_argument("file", help="newline-delimited URL file, or '-' for stdin")
    p_batch.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "parallel captures (default 1, sequential and safe: task spaces "
            "are stateful). >1 runs captures in parallel, each URL in its own "
            "space named <space>-<i>."
        ),
    )
    _add_common(p_batch)
    _add_capture(p_batch)

    p_parse = sub.add_parser("parse", help="distill an already-captured PDF")
    p_parse.add_argument("pdf")
    p_parse.add_argument("--url", default=None, help="source URL for metadata")
    _add_common(p_parse)

    return ap


def _emit(result: DistillResult, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.to_dict()))
    else:
        for key, value in result.to_dict().items():
            if value:
                print(f"{key}: {value}")


def _run_url(args: argparse.Namespace) -> int:
    result = distill_url(
        args.url,
        Path(args.out),
        deep=args.deep,
        max_tokens=args.max_tokens,
        space=args.space,
        timeout_ms=args.timeout_ms,
        wait_selector=args.wait_selector,
    )
    _emit(result, args.json)
    return 0


def _capture_one(
    i: int, url: str, args: argparse.Namespace, backend: EgoCapture
) -> dict[str, object]:
    space = args.space if args.concurrency <= 1 else f"{args.space}-{i}"
    try:
        result = distill_url(
            url,
            Path(args.out),
            deep=args.deep,
            max_tokens=args.max_tokens,
            capture_backend=backend,
            space=space,
            timeout_ms=args.timeout_ms,
            wait_selector=args.wait_selector,
        )
        return {"url": url, "ok": True, **result.to_dict()}
    except Page2mdError as exc:
        return {"url": url, "ok": False, "error": str(exc)}


def _run_batch(args: argparse.Namespace) -> int:
    if args.file == "-":
        urls = [ln.strip() for ln in sys.stdin if ln.strip()]
    else:
        urls = [ln.strip() for ln in Path(args.file).read_text().splitlines() if ln.strip()]

    backend = EgoCapture()
    if args.concurrency <= 1:
        results = [_capture_one(i, url, args, backend) for i, url in enumerate(urls)]
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            # map preserves input order regardless of completion order.
            results = list(
                pool.map(lambda iu: _capture_one(iu[0], iu[1], args, backend), enumerate(urls))
            )

    failures = sum(1 for r in results if not r["ok"])
    if args.json:
        print(json.dumps({"results": results, "failures": failures}))
    else:
        for r in results:
            status = "OK" if r["ok"] else f"FAIL: {r['error']}"
            print(f"{r['url']}: {status}")
    return 1 if failures else 0


def _run_parse(args: argparse.Namespace) -> int:
    result = distill_pdf(
        Path(args.pdf),
        Path(args.out),
        deep=args.deep,
        max_tokens=args.max_tokens,
        url=args.url,
    )
    _emit(result, args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "url":
            return _run_url(args)
        if args.command == "batch":
            return _run_batch(args)
        if args.command == "parse":
            return _run_parse(args)
    except Page2mdError as exc:
        print(f"page2md: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
