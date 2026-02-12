#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DEST="$HOME/Applications/Claunch.app"
APP_LOCAL="$SCRIPT_DIR/Claunch.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

found=false

# Unregister and remove ~/Applications install
if [ -d "$APP_DEST" ]; then
    if [ -x "$LSREGISTER" ]; then
        "$LSREGISTER" -u "$APP_DEST" 2>/dev/null || true
    fi
    rm -rf "$APP_DEST"
    echo "removed $APP_DEST"
    found=true
fi

# Unregister local build directory (doesn't delete — that's the build artifact)
if [ -d "$APP_LOCAL" ] && [ -x "$LSREGISTER" ]; then
    "$LSREGISTER" -u "$APP_LOCAL" 2>/dev/null || true
    echo "unregistered $APP_LOCAL from Launch Services"
    found=true
fi

if [ "$found" = false ]; then
    echo "Claunch.app not found — nothing to uninstall."
    exit 0
fi

echo ""
echo "done. Claunch has been uninstalled."
