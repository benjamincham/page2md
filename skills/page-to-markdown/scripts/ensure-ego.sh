#!/bin/sh
# ensure-ego.sh — gate page2md capture on ego lite being installed.
# Installs ego lite via ego's OWN installer (never a hardcoded DMG URL).
# Idempotent. Honest exit codes: 0 only when `ego-browser` is resolvable.
set -eu

find_ego() {
    # prints the resolved ego-browser path, or nothing
    if command -v ego-browser >/dev/null 2>&1; then
        command -v ego-browser
        return 0
    fi
    if [ -x "$HOME/.local/bin/ego-browser" ]; then
        echo "$HOME/.local/bin/ego-browser"
        return 0
    fi
    return 1
}

found_installer() {
    # locates ego lite's own install.sh inside an installed ego-browser skill
    if [ -n "${EGO_SKILL_DIR:-}" ] && [ -f "$EGO_SKILL_DIR/scripts/install.sh" ]; then
        echo "$EGO_SKILL_DIR/scripts/install.sh"
        return 0
    fi
    for base in \
        "./.claude/skills" \
        "$HOME/.claude/skills" \
        "./.agents/skills" \
        "$HOME/.agents/skills" \
        "$HOME/.config/agents/skills"; do
        p="$base/ego-browser/scripts/install.sh"
        if [ -f "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}

if resolved=$(find_ego); then
    echo "ego-browser ready: $resolved"
    case "$resolved" in
        "$HOME/.local/bin/"*)
            echo "note: it is not on PATH — export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac
    exit 0
fi

if [ -n "${PAGE2MD_SKIP_EGO_INSTALL:-}" ]; then
    echo "ego-browser not installed; install skipped (PAGE2MD_SKIP_EGO_INSTALL set)"
    exit 1
fi

if [ "$(uname -s)" != "Darwin" ]; then
    echo "ego lite is macOS-only today; capture is unavailable on this OS."
    echo "page2md parse <pdf> works anywhere — capture the PDF on a Mac first."
    exit 1
fi

# macOS, ego-browser missing: find or fetch ego's own installer.
if ! installer=$(found_installer); then
    if command -v npx >/dev/null 2>&1; then
        echo "ego-browser skill not found locally; fetching via npx skills..."
        npx -y skills@latest add citrolabs/ego-lite \
            --skill ego-browser --agent claude-code --copy -y || true
        installer=$(found_installer) || installer=""
    fi
fi

if [ -z "${installer:-}" ]; then
    echo "could not find ego's installer; run: npx skills add citrolabs/ego-lite" >&2
    exit 1
fi

echo "running ego's installer: $installer"
sh "$installer" || echo "ego installer exited non-zero; continuing to re-check" >&2

if resolved=$(find_ego); then
    echo "ego-browser ready: $resolved"
    exit 0
fi

echo "ego lite was installed and launched, but onboarding must be finished"
echo "in the ego lite window — it registers the ego-browser command."
echo "Re-run this script afterwards to verify."
exit 1
