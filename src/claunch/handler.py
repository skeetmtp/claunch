#!/usr/bin/env python3
"""claunch URL handler — parses claunch:// URLs and launches claude in a terminal."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import urlparse, parse_qs, unquote


CONFIG_PATH = os.path.expanduser("~/.config/claunch/config.json")
VALID_TERMINALS = {"ghostty", "iterm", "terminal"}


def load_config() -> dict | None:
    """Load and validate the config file. Returns None if missing or invalid."""
    if not os.path.isfile(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"claunch: warning: failed to read config: {e}", file=sys.stderr)
        return None

    if not isinstance(config, dict):
        print("claunch: warning: config must be a JSON object", file=sys.stderr)
        return None

    terminal = config.get("terminal")
    if terminal is not None and terminal not in VALID_TERMINALS:
        print(
            f"claunch: warning: unknown terminal {terminal!r}, ignoring config",
            file=sys.stderr,
        )
        return None

    projects = config.get("projects")
    if projects is not None and not isinstance(projects, dict):
        print("claunch: warning: 'projects' must be an object, ignoring config", file=sys.stderr)
        return None

    return config


def parse_url(url: str, config: dict | None = None) -> tuple[str, str | None]:
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

    project_values = params.get("project")
    project = project_values[0] if project_values and project_values[0].strip() else None

    if directory and project:
        raise ValueError("'dir' and 'project' are mutually exclusive")

    if project:
        projects = (config or {}).get("projects") or {}
        if project not in projects:
            raise ValueError(f"unknown project: {project!r} (not found in config)")
        directory = projects[project]

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


def launch_iterm(script_path: str) -> bool:
    """Try to launch iTerm2 with the given script. Returns True on success."""
    if not os.path.isdir("/Applications/iTerm.app"):
        return False
    subprocess.run([
        "osascript", "-e",
        f'tell application "iTerm2" to create window with default profile '
        f'command {shlex.quote(script_path)}',
    ])
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


def launch_in_terminal(
    config: dict | None, script_path: str, directory: str | None, claude_command: str,
) -> None:
    """Launch the script in the configured terminal, or fall back to the default chain."""
    terminal = (config or {}).get("terminal")

    if terminal == "ghostty":
        if not launch_ghostty(script_path):
            print("claunch: error: ghostty is configured but not available", file=sys.stderr)
            sys.exit(1)
    elif terminal == "iterm":
        if not launch_iterm(script_path):
            print("claunch: error: iterm is configured but iTerm.app not found", file=sys.stderr)
            sys.exit(1)
    elif terminal == "terminal":
        launch_terminal_app(directory, claude_command)
    else:
        # No config or no terminal preference — use default fallback chain
        if not launch_ghostty(script_path):
            launch_terminal_app(directory, claude_command)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: handler.py <claunch-url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    config = load_config()

    try:
        prompt, directory = parse_url(url, config)
    except ValueError as e:
        print(f"claunch: {e}", file=sys.stderr)
        sys.exit(1)

    claude_command = f"claude {shlex.quote(prompt)}"
    script_path = write_temp_script(directory, claude_command)
    launch_in_terminal(config, script_path, directory, claude_command)


if __name__ == "__main__":
    main()
