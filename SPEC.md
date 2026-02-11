# Claunch — Technical Specification

## Overview

Claunch is a macOS tool that registers the `claunch://` custom URL scheme. When a user clicks a
`claunch://` URL (e.g. in a browser, Slack, docs), it opens a Ghostty terminal window running
`claude` in interactive mode with the prompt from the URL.

**Status:** v0.1.0 — all core components implemented, ready for build + test on macOS.

## URL Scheme

```text
claunch://open?prompt=<url-encoded-prompt>&dir=<url-encoded-path>
```

| Parameter | Required | Type   | Description                                                  |
| --------- | -------- | ------ | ------------------------------------------------------------ |
| `prompt`  | yes      | string | URL-encoded text passed as positional arg to `claude`        |
| `dir`     | no       | string | URL-encoded absolute path; working directory for the session |

The scheme is `claunch`, the host is `open`. Any other host value is rejected. Standard URL
encoding applies — spaces as `+` or `%20`, quotes as `%22`, etc.

## Architecture

Hybrid Swift + Python design. A thin Swift wrapper handles macOS URL scheme Apple Events (which
require a proper `.app` bundle and Cocoa event loop). All URL parsing and terminal launching logic
lives in Python, avoiding the need for PyObjC.

```text
macOS / Browser
    │
    │ claunch:// Apple Event
    v
Claunch (Swift) — NSApplication, delegates to Python
    │
    │ uv run handler.py <url>
    v
handler.py — parse URL, write script, launch terminal
```

## Components

### 1. Swift URL Event Handler — `src/claunch/app/main.swift`

**What it does:**

- Creates a minimal `NSApplication` with an `NSApplicationDelegate`
- Registers a handler for `kAEGetURL` Apple Events (the `kInternetEventClass` event that macOS
  sends when a registered URL scheme is opened)
- On URL event: extracts the URL string from the Apple Event descriptor, locates `handler.py` in
  `Bundle.main` Resources, spawns `uv run handler.py <url>` via `Process` (falls back to `python3`
  if `uv` is not installed)
- Terminates the app after the Python process completes

**Key implementation details:**

- Uses `keyDirectObject` to extract the URL from the event descriptor
- `Process.terminationHandler` dispatches termination back to the main queue
- Error paths (`guard let` failures) log via `NSLog` and terminate

**Size:** ~48 lines.

### 2. Info.plist — `src/claunch/app/Info.plist`

**What it does:**

- Declares the app bundle identity (`com.claunch.urlhandler`)
- Registers the `claunch` URL scheme via `CFBundleURLTypes`
- Sets `LSBackgroundOnly = true` so the app doesn't appear in the Dock

**Key fields:**

| Key                  | Value                    | Purpose                  |
| -------------------- | ------------------------ | ------------------------ |
| `CFBundleIdentifier` | `com.claunch.urlhandler` | Unique bundle ID         |
| `CFBundleExecutable` | `Claunch`                | Binary name in MacOS/    |
| `LSBackgroundOnly`   | `true`                   | No dock icon             |
| `CFBundleURLSchemes` | `["claunch"]`            | Registers the URL scheme |

### 3. Python Handler — `src/claunch/handler.py`

**What it does:**

- Accepts the full `claunch://` URL as `sys.argv[1]`
- Parses with `urllib.parse.urlparse` + `parse_qs`
- Validates: scheme must be `claunch`, host must be `open`, prompt must be non-empty, dir must
  exist if provided
- Constructs the claude command with `shlex.quote` escaping
- Writes a temporary launcher shell script (`/tmp/claunch_XXXX.sh`) containing `cd <dir>` and
  `exec claude <prompt>`
- Attempts to launch Ghostty, falls back to Terminal.app

**Functions:**

| Function              | Signature                               | Description                           |
| --------------------- | --------------------------------------- | ------------------------------------- |
| `parse_url`           | `(url: str) -> tuple[str, str \| None]` | Parse/validate URL, return prompt+dir |
| `write_temp_script`   | `(directory, claude_command) -> str`    | Write temp `.sh` script, return path  |
| `launch_ghostty`      | `(script_path: str) -> bool`            | Try Ghostty CLI then `open -a`        |
| `launch_terminal_app` | `(directory, claude_command) -> None`   | Fallback via `osascript` + Terminal   |
| `main`                | `() -> None`                            | Entry point: parse, build, launch     |

**Terminal launching strategy:**

1. **Ghostty (primary):** Check if `ghostty` CLI is on PATH. If so, use
   `ghostty +new-window --command=<script>`. If the CLI isn't available but
   `/Applications/Ghostty.app` exists, fall back to
   `open -na Ghostty.app --args --command=<script>`.
2. **Terminal.app (fallback):** Use
   `osascript -e 'tell application "Terminal" to do script "<command>"'`.

The temp script approach avoids issues with `open -na Ghostty.app --args -e` (tab duplication and
login wrapper problems on macOS).

**Security:** All user-supplied strings (prompt, directory) are escaped with `shlex.quote` before
being embedded in shell commands.

### 4. Build Script — `build.py`

**What it does:**

1. Cleans any existing `Claunch.app` directory
2. Creates `Claunch.app/Contents/{MacOS,Resources}` structure
3. Compiles Swift:
   `swiftc -o Claunch.app/Contents/MacOS/Claunch src/claunch/app/main.swift`
4. Copies `Info.plist` to `Claunch.app/Contents/`
5. Copies `handler.py` to `Claunch.app/Contents/Resources/`
6. Sets executable permissions on the binary

**Requirements:** `swiftc` (Xcode Command Line Tools).

### 5. Install Script — `install.sh`

**What it does:**

1. Verifies `Claunch.app` exists (errors if not built yet)
2. Creates `~/Applications/` if needed
3. Removes any previous `Claunch.app` installation
4. Copies the built `.app` bundle to `~/Applications/`
5. Registers with Launch Services via `lsregister -R`
6. Verifies registration by checking `lsregister -dump` for `claunch`

## File Inventory

| File                         | Language | Lines | Status |
| ---------------------------- | -------- | ----- | ------ |
| `pyproject.toml`             | TOML     | 13    | Done   |
| `src/claunch/__init__.py`    | Python   | 1     | Done   |
| `src/claunch/handler.py`     | Python   | 109   | Done   |
| `src/claunch/app/main.swift` | Swift    | 48    | Done   |
| `src/claunch/app/Info.plist` | XML      | 33    | Done   |
| `build.py`                   | Python   | 60    | Done   |
| `install.sh`                 | Bash     | 46    | Done   |

## Built App Bundle Structure

```text
Claunch.app/
└── Contents/
    ├── Info.plist               # Copied from src/claunch/app/Info.plist
    ├── MacOS/
    │   └── Claunch              # Compiled from src/claunch/app/main.swift
    └── Resources/
        └── handler.py           # Copied from src/claunch/handler.py
```

## Dependencies

| Dependency                        | Type               | Purpose                                           |
| --------------------------------- | ------------------ | ------------------------------------------------- |
| [uv](https://docs.astral.sh/uv/)  | Build + Runtime    | Runs Python scripts; manages Python automatically |
| swiftc                            | Build-time         | Compile main.swift                                |
| Ghostty                           | Runtime (optional) | Primary terminal emulator                         |
| Terminal.app                      | Runtime (fallback) | Fallback terminal                                 |
| claude CLI                        | Runtime            | The tool being launched                           |

Zero external Python packages. The handler uses only stdlib: `os`, `shlex`, `subprocess`, `sys`,
`tempfile`, `urllib.parse`.

## Verification Checklist

| #   | Test              | Command                                             | Expected                            |
| --- | ----------------- | --------------------------------------------------- | ----------------------------------- |
| 1   | Build             | `uv run build.py`                                   | Produces `Claunch.app/` with bin    |
| 2   | Install           | `bash install.sh`                                   | Copies to `~/Applications/`         |
| 3   | Basic prompt      | `open 'claunch://open?prompt=hello+world'`          | Ghostty opens, claude starts        |
| 4   | With directory    | `open 'claunch://open?prompt=list+files&dir=/tmp'`  | claude runs in `/tmp`               |
| 5   | URL encoding      | See note below                                      | Prompt: `fix the bug in "main.py"`  |
| 6   | Missing prompt    | `open 'claunch://open'`                             | Error logged, no terminal opens     |
| 7   | Bad directory     | `open 'claunch://open?prompt=hi&dir=/nonexistent'`  | Error logged, no terminal opens     |
| 8   | Terminal fallback | Uninstall Ghostty, repeat test 3                    | Terminal.app opens instead          |

Test 5 command: `open 'claunch://open?prompt=fix%20the%20bug%20in%20%22main.py%22'`

## What's Not Yet Done

- **No automated tests** — handler.py functions are testable but no test suite exists yet
- **No icon** — the app bundle has no `AppIcon.icns`
- **No code signing** — the binary is unsigned (fine for local use, would need signing for
  distribution)
- **No Homebrew formula / installer package** — manual build + install only
- **Ghostty launch strategy not validated on hardware** — the `+new-window --command=` approach
  and the `open -na` fallback need testing on an actual Mac to confirm which path works; the
  handler tries both
- **Temp script cleanup** — launcher scripts in `/tmp` are not cleaned up after use
