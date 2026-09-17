#!/usr/bin/env node
/**
 * page2md-cli — npm launcher for the page2md Python CLI.
 *
 * `npx page2md-cli <args>` (or the `page2md` bin from a global install)
 * ensures the Python CLI is installed once — `uv tool`, then `pipx`, then
 * `python3 -m pip install --user`, from the public git repo or
 * $PAGE2MD_SOURCE — then forwards all arguments to the real CLI.
 */
'use strict';

// PAGE2MD_CLI_LAUNCHER_MARKER — used to detect self-recursion (see resolveBin).
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PKG = 'page2md';
const DEFAULT_SOURCE = 'git+https://github.com/benjamincham/page2md.git';
const SOURCE = process.env.PAGE2MD_SOURCE || DEFAULT_SOURCE;

function isSelf(candidate) {
  // npx / npm run prepend node_modules/.bin to PATH, where our own `page2md`
  // shim lives — resolving to it would recurse forever. Skip any candidate
  // that is this file (or a symlink to it), or that carries our marker.
  let realSelf = __filename;
  try {
    realSelf = fs.realpathSync(__filename);
  } catch {}
  try {
    if (fs.realpathSync(candidate) === realSelf) return true;
  } catch {}
  try {
    const head = fs.readFileSync(candidate, 'utf8').slice(0, 600);
    if (head.includes('PAGE2MD_CLI_LAUNCHER_MARKER')) return true;
  } catch {}
  return false;
}

function resolveBin(cmd) {
  const isWin = process.platform === 'win32';
  const exts = isWin
    ? (process.env.PATHEXT || '.EXE;.CMD;.BAT;.COM').split(';')
    : [''];
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = path.join(dir, cmd + ext);
      let st;
      try {
        st = fs.statSync(candidate);
      } catch {
        continue;
      }
      if (!st.isFile()) continue;
      if (isSelf(candidate)) continue;
      return candidate;
    }
  }
  return null;
}

function hasCmd(cmd) {
  const probe = process.platform === 'win32'
    ? spawnSync('where', [cmd], { stdio: 'ignore' })
    : spawnSync('/bin/sh', ['-c', `command -v ${cmd} 2>/dev/null`], { shell: false });
  return probe.status === 0;
}

function pythonOk() {
  const r = spawnSync('python3', [
    '-c',
    'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)',
  ]);
  return r.status === 0;
}

function userBaseBin() {
  const r = spawnSync('python3', ['-m', 'site', '--user-base'], { encoding: 'utf8' });
  if (r.status !== 0 || !r.stdout) return null;
  const base = r.stdout.trim();
  const rel = process.platform === 'win32'
    ? path.join('Scripts', `${PKG}.exe`)
    : path.join('bin', PKG);
  return path.join(base, rel);
}

function installOnce() {
  if (!hasCmd('python3')) {
    console.error(`${PKG}: python3 (3.10+) is required but was not found on PATH.`);
    process.exit(1);
  }
  if (!pythonOk()) {
    const v = spawnSync('python3', ['--version'], { encoding: 'utf8' });
    console.error(`${PKG}: needs Python 3.10+; found: ${(v.stdout || 'unknown').trim()}`);
    process.exit(1);
  }

  console.error(`${PKG}: one-time setup — installing the Python CLI from ${SOURCE}`);
  const attempts = [
    ['uv', ['tool', 'install', SOURCE], 'uv'],
    ['pipx', ['install', SOURCE], 'pipx'],
    ['python3', ['-m', 'pip', 'install', '--user', SOURCE], 'pip --user'],
  ];
  for (const [cmd, args, label] of attempts) {
    if (!hasCmd(cmd)) continue;
    const r = spawnSync(cmd, args, { stdio: 'inherit' });
    if (r.status === 0) {
      console.error(`${PKG}: installed via ${label}`);
      return;
    }
    console.error(`${PKG}: ${label} install failed, trying next method...`);
  }
}

function main() {
  let bin = resolveBin(PKG);
  if (!bin) {
    installOnce();
    bin = resolveBin(PKG);
    if (!bin) {
      const candidate = userBaseBin();
      if (candidate) {
        console.error(
          `${PKG}: installed, but not on PATH yet. Add it, or invoke directly:\n  ${candidate}`,
        );
        process.exit(1);
      }
      console.error(
        `${PKG}: install failed on all paths (uv/pipx/pip). ` +
        'Install manually from a checkout: pip install /path/to/page2md',
      );
      process.exit(1);
    }
  }

  const r = spawnSync(bin, process.argv.slice(2), {
    stdio: 'inherit',
    env: process.env,
    shell: process.platform === 'win32',
  });
  if (r.error) {
    console.error(`${PKG}: failed to run the CLI: ${r.error.message}`);
    process.exit(1);
  }
  process.exit(r.status == null ? 1 : r.status);
}

main();
