# Claunch

URL scheme handler for Claude Code CLI. Click a `claunch://` link in your browser, Slack, or docs
and it opens a Ghostty terminal window running `claude` with the prompt from the URL.

## URL Format

```text
claunch://open?prompt=<url-encoded-prompt>&dir=<url-encoded-path>
claunch://open?prompt=<url-encoded-prompt>&project=<name>
```

| Parameter | Required | Description                                                   |
|-----------|----------|---------------------------------------------------------------|
| `prompt`  | yes      | Passed as positional arg to `claude`                          |
| `dir`     | no       | Working directory (`cd` before running `claude`)              |
| `project` | no       | Project name; looked up in config or auto-discovered          |

`dir` and `project` are mutually exclusive.

## Requirements

- macOS (Apple Event URL scheme handling)
- [uv](https://docs.astral.sh/uv/) (manages Python automatically; falls back to system `python3` at runtime)
- Xcode Command Line Tools (`swiftc`)
- [Ghostty](https://ghostty.org) terminal (falls back to Terminal.app)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` on PATH)

## Quick Start

```bash
# Build the .app bundle
uv run build.py

# Install to ~/Applications and register the URL scheme
bash install.sh

# Test it
open 'claunch://open?prompt=hello+world'
```

## Examples

```text
# Basic prompt
claunch://open?prompt=explain+this+codebase

# With working directory
claunch://open?prompt=list+files&dir=/tmp

# With project name (looked up in config, or auto-discovered)
claunch://open?prompt=review+the+auth+flow&project=myapp

# URL-encoded special characters
claunch://open?prompt=fix%20the%20bug%20in%20%22main.py%22
```

## Project Auto-Discovery

When you use `project=<name>` and the name isn't in your config, the handler scans
`~/.claude/projects/` to find a matching directory:

- **Single exact match** (basename equals project name) → auto-selected, no dialog
- **Multiple matches** → macOS picker dialog
- The selected mapping is saved to `~/.config/claunch/config.json` for future use

## How It Works

1. macOS sees a `claunch://` URL and launches `Claunch.app`
   (registered via `LSBackgroundOnly` + `CFBundleURLTypes`)
2. The Swift wrapper receives the URL as an Apple Event, locates `handler.py` in the app bundle's
   Resources, and calls `uv run handler.py <url>` (falls back to `python3` if `uv` is not installed)
3. The Python handler parses the URL, writes a temp launcher script, and opens a Ghostty window
   running `claude <prompt>` in the specified directory
4. If Ghostty is not available, it falls back to Terminal.app via `osascript`

## Project Structure

```text
claunch/
├── pyproject.toml              # Package metadata (no external deps)
├── build.py                    # Compile Swift + assemble .app bundle
├── install.sh                  # Copy to ~/Applications + register URL scheme
└── src/
    └── claunch/
        ├── __init__.py
        ├── handler.py          # URL parsing + terminal launching
        └── app/
            ├── main.swift      # macOS Apple Event URL handler
            └── Info.plist      # URL scheme registration
```

After building, `Claunch.app` contains:

```text
Claunch.app/
└── Contents/
    ├── Info.plist
    ├── MacOS/
    │   └── Claunch             # Compiled Swift binary
    └── Resources/
        └── handler.py          # Python handler (copied from src)
```

## Uninstall

```bash
rm -rf ~/Applications/Claunch.app
```
