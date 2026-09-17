#!/bin/sh
# bootstrap.sh — install the page2md Python CLI for an agent that
# installed this skill via `npx skills add`. Idempotent: safe to re-run.
set -eu

# Default install source. A git URL works for uv, pipx and pip alike; edit
# this single line once the repo has a public URL. Override at runtime with
# PAGE2MD_SOURCE — a local checkout path or any pip-installable spec.
DEFAULT_SOURCE="git+https://github.com/benjamincham/page2md.git"
SRC="${PAGE2MD_SOURCE:-$DEFAULT_SOURCE}"

if command -v page2md >/dev/null 2>&1; then
    echo "page2md already installed: $(page2md --version)"
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "page2md needs Python 3.10+; install python3 first" >&2
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "page2md needs Python 3.10+; found: $(python3 --version 2>&1)" >&2
    exit 1
fi

installed=0
if command -v uv >/dev/null 2>&1; then
    echo "installing page2md via uv tool install..."
    if uv tool install "$SRC"; then
        installed=1
    else
        echo "uv install failed, trying pipx" >&2
    fi
fi
if [ "$installed" -eq 0 ] && command -v pipx >/dev/null 2>&1; then
    echo "installing page2md via pipx install..."
    if pipx install "$SRC"; then
        installed=1
    else
        echo "pipx install failed, trying pip --user" >&2
    fi
fi
if [ "$installed" -eq 0 ]; then
    echo "installing page2md via python3 -m pip install --user..."
    if python3 -m pip install --user "$SRC"; then
        installed=1
    else
        echo "pip --user install failed" >&2
    fi
fi

if [ "$installed" -eq 0 ]; then
    echo "page2md install failed on all paths; install it manually from a checkout or wheel: pip install /path/to/page2md" >&2
    exit 1
fi

if command -v page2md >/dev/null 2>&1; then
    page2md --version
    exit 0
fi

USER_BIN="$(python3 -m site --user-base)/bin"
echo "page2md installed, but its binary is not on PATH."
echo "Add this directory to your PATH, then run 'page2md --version': $USER_BIN"
exit 0
