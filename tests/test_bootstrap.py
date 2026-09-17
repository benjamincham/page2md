import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from page2md.cli import main

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "page-to-markdown"
BOOTSTRAP = SKILL_DIR / "scripts" / "bootstrap.sh"
ENSURE_EGO = SKILL_DIR / "scripts" / "ensure-ego.sh"
SKILL_MD = SKILL_DIR / "SKILL.md"


def test_version_flag(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out.strip()
    assert "page2md" in out
    assert out.rsplit(None, 1)[-1]  # non-empty version string


def test_bootstrap_syntax() -> None:
    sh = shutil.which("sh")
    if not sh:
        pytest.skip("sh not available")
    assert BOOTSTRAP.exists()
    subprocess.run([sh, "-n", str(BOOTSTRAP)], check=True)
    assert "[[" not in BOOTSTRAP.read_text()  # no bashisms


def _mkexec(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_bootstrap_idempotent_when_already_installed(tmp_path: Path) -> None:
    sh = shutil.which("sh")
    if not sh:
        pytest.skip("sh not available")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    _mkexec(bindir / "page2md", "#!/bin/sh\necho 'page2md 0.1.0'\n")
    # uv/pipx stubs that record if they are ever invoked.
    marker = tmp_path / "installer-ran"
    for name in ("uv", "pipx"):
        _mkexec(bindir / name, f"#!/bin/sh\ntouch {marker}\nexit 1\n")

    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    proc = subprocess.run(
        [sh, str(BOOTSTRAP)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "already installed" in proc.stdout
    assert "0.1.0" in proc.stdout
    assert not marker.exists()  # no installer was attempted


def test_skill_md_frontmatter_and_setup() -> None:
    text = SKILL_MD.read_text()
    assert text.startswith("---\n")
    fm = text.split("---\n")[1]
    assert "name: page-to-markdown" in fm
    assert "description:" in fm
    assert "## Setup" in text
    assert "scripts/bootstrap.sh" in text
    assert "scripts/ensure-ego.sh" in text


def _run_sh(script: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [shutil.which("sh") or "sh", str(script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_ensure_ego_syntax() -> None:
    sh = shutil.which("sh")
    if not sh:
        pytest.skip("sh not available")
    assert ENSURE_EGO.exists()
    subprocess.run([sh, "-n", str(ENSURE_EGO)], check=True)
    body = ENSURE_EGO.read_text()
    assert "[[" not in body
    assert "cdn.ego.app" not in body  # never embed a DMG URL


def test_ensure_ego_ready_when_stub_on_path(tmp_path: Path) -> None:
    if not shutil.which("sh"):
        pytest.skip("sh not available")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _mkexec(bindir / "ego-browser", "#!/bin/sh\necho stub\n")
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    proc = _run_sh(ENSURE_EGO, env)
    assert proc.returncode == 0, proc.stderr
    assert "ready" in proc.stdout


def test_ensure_ego_skip_install_gate(tmp_path: Path) -> None:
    if not shutil.which("sh"):
        pytest.skip("sh not available")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "npx-ran"
    _mkexec(bindir / "npx", f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    env = dict(
        os.environ,
        PATH=str(bindir),  # no ego-browser, no real tools
        PAGE2MD_SKIP_EGO_INSTALL="1",
        HOME=str(tmp_path),
    )
    proc = _run_sh(ENSURE_EGO, env)
    assert proc.returncode == 1
    assert "skipped" in proc.stdout
    assert not marker.exists()  # npx never invoked in gate-only mode


def test_ensure_ego_non_darwin_branch(tmp_path: Path) -> None:
    import platform

    if platform.system() == "Darwin":
        pytest.skip("Darwin box exercises the installer branch instead")
    if not shutil.which("sh"):
        pytest.skip("sh not available")
    env = dict(
        os.environ,
        PATH="/nonexistent",  # nothing resolvable
        HOME=str(tmp_path),
    )
    env.pop("PAGE2MD_SKIP_EGO_INSTALL", None)
    env.pop("EGO_SKILL_DIR", None)
    proc = _run_sh(ENSURE_EGO, env)
    assert proc.returncode == 1
    assert "macOS-only" in proc.stdout
