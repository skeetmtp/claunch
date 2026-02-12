#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$SCRIPT_DIR/Claunch.app"
APP_DEST="$HOME/Applications/Claunch.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

if [ ! -d "$APP_SRC" ]; then
    echo "error: Claunch.app not found. Run 'uv run build.py' first." >&2
    exit 1
fi

# Create ~/Applications if needed
mkdir -p "$HOME/Applications"

# Remove old installation
if [ -d "$APP_DEST" ]; then
    rm -rf "$APP_DEST"
    echo "removed previous installation"
fi

# Copy app bundle
cp -R "$APP_SRC" "$APP_DEST"
echo "installed Claunch.app to $APP_DEST"

# Register with Launch Services
if [ -x "$LSREGISTER" ]; then
    "$LSREGISTER" -R "$APP_DEST"
    echo "registered with Launch Services"

    # Verify
    if "$LSREGISTER" -dump | grep -q "claunch"; then
        echo "verification: claunch:// scheme registered successfully"
    else
        echo "warning: claunch scheme not found in Launch Services dump" >&2
        echo "you may need to log out and back in, or run:" >&2
        echo "  $LSREGISTER -R $APP_DEST" >&2
    fi
else
    echo "warning: lsregister not found at expected path" >&2
    echo "try opening $APP_DEST manually to register the URL scheme" >&2
fi

echo ""
echo "done. test with: open 'claunch://open?v=1&prompt=hello+world'"
