# Security: Add confirmation dialog before execution

## Problem

Clicking any `claunch://` URL immediately launches Claude Code with the attacker-controlled
prompt — no user confirmation. Since Claude Code can read/write files and execute commands,
a malicious link sent via Slack/email/browser is a real phishing/RCE vector. The
shell-injection protection (`shlex.quote`) is solid, but the real threat is **prompt
injection into Claude Code itself**.

## Changes

All functional changes are in **one file**: `src/claunch/handler.py`.
Docs updated in `SPEC.md` and `CLAUDE.md`.

### 1. Native macOS confirmation dialog — `show_confirmation()`

Add a new function that uses `osascript` to show a native Cocoa alert before executing.

- Dialog shows the **decoded prompt** (truncated to 500 chars for readability) and **target
  directory**
- Two buttons: **"Cancel"** (default, pre-selected) and **"Run in Claude"**
- Caution icon (yellow warning triangle)
- User-controlled text passed as **argv** to the AppleScript (not string-interpolated),
  preventing AppleScript injection
- Cancel / close window → `osascript` exits with code 1 → handler exits cleanly, no
  terminal opens

Why `osascript` and not Swift `NSAlert`: the app is `LSBackgroundOnly=true`, and `osascript
display dialog` works reliably from headless processes. The project already uses `osascript`
for the Terminal.app fallback (line 85-87).

### 2. Prompt length limit

Add `MAX_PROMPT_LENGTH = 2000` constant. Reject prompts exceeding this in `parse_url()`
(before the dialog is even shown). Prevents absurdly long/obfuscated payloads.

### 3. Temp script self-cleanup

In `write_temp_script()`, add a `trap cleanup EXIT` and remove the `exec` prefix so the
trap actually fires when Claude exits. The temp `.sh` file deletes itself on exit.

### 4. Wire confirmation into `main()`

Insert `show_confirmation()` call between `parse_url()` and command execution. If the user
cancels, exit with code 0 (normal exit, not error).

## Files to modify

| File                          | Change                                                   |
| ----------------------------- | -------------------------------------------------------- |
| `src/claunch/handler.py`      | Add constants, `show_confirmation()`, prompt length      |
|                               | check, temp cleanup trap, confirmation gate in `main()`  |
| `SPEC.md`                     | Document confirmation dialog, update function table,     |
|                               | update verification checklist, remove "not yet done"     |
|                               | item about temp cleanup                                  |
| `CLAUDE.md`                   | Mention confirmation dialog in architecture description  |

No changes to: `main.swift`, `Info.plist`, `build.py`, `install.sh`.

## Verification

1. `uv run build.py` — builds successfully
2. `bash install.sh` — installs to ~/Applications
3. `open 'claunch://open?v=1&prompt=hello+world'` — dialog appears showing "hello world",
   click "Run in Claude" → Ghostty opens with Claude
4. Same URL, click "Cancel" → nothing happens, clean exit
5. Prompt with quotes: `open 'claunch://open?v=1&prompt=fix%20%22main.py%22'` — dialog shows
   `fix "main.py"` as literal text (no AppleScript injection)
6. Over-limit prompt (>2000 chars) — rejected before dialog with error
7. After Claude exits, verify `/tmp/claunch_*.sh` was cleaned up
