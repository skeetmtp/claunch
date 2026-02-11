# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Claunch

Claunch is a macOS `claunch://` URL scheme handler that opens Claude Code CLI in a terminal window.
It's a hybrid Swift + Python app: Swift handles macOS Apple Event URL dispatch, Python handles
URL parsing and terminal launching. Zero external dependencies (Python stdlib only).

URL format: `claunch://open?prompt=<url-encoded-prompt>&dir=<url-encoded-path>`

## Build & Install

```bash
# Build the .app bundle (requires Xcode Command Line Tools for swiftc)
uv run build.py

# Install to ~/Applications and register URL scheme with Launch Services
bash install.sh
```

There are no tests, no linter configuration, and no CI/CD pipeline.

## Architecture

The app is a macOS `.app` bundle with two layers:

1. **Swift layer** (`src/claunch/app/main.swift`) — Minimal `NSApplicationDelegate` that registers
   for `kAEGetURL` Apple Events. On URL open, it extracts the URL string and spawns
   `uv run handler.py <url>` (falling back to `/usr/bin/python3` if `uv` is not installed),
   then terminates after the Python process exits.

2. **Python handler** (`src/claunch/handler.py`) — Parses the `claunch://` URL, validates
   parameters, writes a temp bash script to `/tmp/claunch_XXXX.sh` (containing `cd` +
   `exec claude <prompt>`), and launches it in a terminal. Terminal preference:
   Ghostty CLI -> Ghostty.app -> Terminal.app (AppleScript fallback).

`build.py` compiles the Swift, copies `Info.plist` and `handler.py` into the bundle structure.
`install.sh` copies the bundle to `~/Applications/` and registers with Launch Services.

## Markdown Style

When writing or editing `.md` files, follow these rules (enforced by markdownlint via
`.markdownlint.json`):

- Max line length: 120 characters
- Fenced code blocks must have a language (e.g. ` ```bash `, ` ```text `)
- Blank line before and after lists
- Table pipes must be column-aligned across all rows (header, separator, data)

Check: `npx markdownlint-cli2 "**/*.md"`

Key design decisions:

- Temp script approach avoids shell quoting issues with direct terminal commands
- All user input escaped with `shlex.quote()`
- `LSBackgroundOnly=true` in Info.plist so the app never shows in the Dock
- handler.py is bundled in `Claunch.app/Contents/Resources/` for standalone operation
