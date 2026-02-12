"""claunch CLI — bootstrap and manage claunch configuration."""

from __future__ import annotations

import json
import os
import sys
import tempfile

from claunch.handler import CONFIG_PATH, find_executable


def detect_terminal() -> str:
    """Auto-detect the best available terminal, returning its config key."""
    ghostty_path = find_executable(
        "ghostty", ["/Applications/Ghostty.app/Contents/MacOS/ghostty"],
    )
    if ghostty_path != "ghostty" or os.path.isdir("/Applications/Ghostty.app"):
        return "ghostty"
    if os.path.isdir("/Applications/iTerm.app"):
        return "iterm"
    return "terminal"


def cmd_init() -> None:
    """Create a default config file with auto-detected terminal."""
    if os.path.isfile(CONFIG_PATH):
        print(f"claunch: config already exists at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    terminal = detect_terminal()
    config = {"terminal": terminal, "projects": {}}

    config_dir = os.path.dirname(CONFIG_PATH)
    os.makedirs(config_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, CONFIG_PATH)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    print(f"Created {CONFIG_PATH}")
    print(f"  terminal: {terminal}")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: claunch <command>", file=sys.stderr)
        print("commands:", file=sys.stderr)
        print("  init    Create default config file", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    if command == "init":
        cmd_init()
    else:
        print(f"claunch: unknown command: {command}", file=sys.stderr)
        sys.exit(1)
