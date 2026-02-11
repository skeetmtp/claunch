#!/usr/bin/env python3
"""claunch URL handler — parses claunch:// URLs and launches claude in a terminal."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import urlparse, parse_qs, unquote


def parse_url(url: str) -> tuple[str, str | None]:
    """Parse a claunch:// URL and return (prompt, directory)."""
    parsed = urlparse(url)

    if parsed.scheme != "claunch":
        raise ValueError(f"unexpected scheme: {parsed.scheme}")

    if parsed.netloc != "open":
        raise ValueError(f"unexpected host: {parsed.netloc} (expected 'open')")

    params = parse_qs(parsed.query)

    prompt_values = params.get("prompt")
    if not prompt_values or not prompt_values[0].strip():
        raise ValueError("missing or empty 'prompt' parameter")
    prompt = prompt_values[0]

    dir_values = params.get("dir")
    directory = dir_values[0] if dir_values and dir_values[0].strip() else None

    if directory and not os.path.isdir(directory):
        raise ValueError(f"directory does not exist: {directory}")

    return prompt, directory


def write_temp_script(directory: str | None, claude_command: str) -> str:
    """Write a temporary shell script that cd's and runs claude, returning its path."""
    fd, path = tempfile.mkstemp(prefix="claunch_", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        f.write("#!/bin/bash\n")
        if directory:
            f.write(f"cd {shlex.quote(directory)}\n")
        f.write(f"exec {claude_command}\n")
    os.chmod(path, 0o755)
    return path


def launch_ghostty(script_path: str) -> bool:
    """Try to launch Ghostty with the given script. Returns True on success."""
    # Try ghostty CLI with +new-window first
    try:
        result = subprocess.run(
            ["which", "ghostty"], capture_output=True, text=True
        )
        if result.returncode == 0:
            result = subprocess.run(
                ["ghostty", "+new-window", f"--command={script_path}"],
                capture_output=True,
            )
            if result.returncode == 0:
                return True
    except FileNotFoundError:
        pass

    # Fallback: open -a Ghostty with --command flag
    ghostty_app = "/Applications/Ghostty.app"
    if not os.path.isdir(ghostty_app):
        return False

    subprocess.Popen(
        ["open", "-na", "Ghostty.app", "--args", f"--command={script_path}"]
    )
    return True


def launch_terminal_app(directory: str | None, claude_command: str) -> None:
    """Fallback: launch in Terminal.app via osascript."""
    command = claude_command
    if directory:
        command = f"cd {shlex.quote(directory)} && {command}"
    subprocess.run([
        "osascript", "-e",
        f'tell application "Terminal" to do script {shlex.quote(command)}',
    ])


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: handler.py <claunch-url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    try:
        prompt, directory = parse_url(url)
    except ValueError as e:
        print(f"claunch: {e}", file=sys.stderr)
        sys.exit(1)

    claude_command = f"claude {shlex.quote(prompt)}"

    # Try Ghostty first, fall back to Terminal.app
    script_path = write_temp_script(directory, claude_command)
    if not launch_ghostty(script_path):
        launch_terminal_app(directory, claude_command)


if __name__ == "__main__":
    main()
