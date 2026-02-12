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
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
VALID_TERMINALS = {"ghostty", "iterm", "terminal"}
SUPPORTED_VERSIONS = {1}


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


def _decode_project_dir_recursive(
    prefix: str, remainder: str, results: list[str],
) -> None:
    """Recursively decode a Claude projects dirname by trying dash-to-slash splits.

    Claude encodes paths like /Users/alban/work/lempire as -Users-alban-work-lempire.
    This is ambiguous when path components contain dashes (e.g. my-project), so we try
    all possible splits and check os.path.isdir() to prune.

    The special sequence '--' at the start of a component indicates a dot-prefix
    (e.g. '--meteor' decodes to '.meteor').
    """
    if not remainder:
        if os.path.isdir(prefix):
            results.append(prefix)
        return

    # Try all possible split points: each dash could be a path separator or literal dash
    i = 0
    while i < len(remainder):
        dash_pos = remainder.find("-", i)
        if dash_pos == -1:
            # No more dashes — rest is part of current component
            candidate = prefix + "/" + remainder
            if os.path.isdir(candidate):
                results.append(candidate)
            return

        if dash_pos == 0:
            # Leading dash(es) indicate a dot-prefixed component.
            # '--foo' at top-level or '-foo' after a separator split both encode '.foo'.
            rest = remainder[2:] if remainder.startswith("--") else remainder[1:]
            if not rest:
                return
            next_dash = rest.find("-")
            if next_dash == -1:
                candidate = prefix + "/." + rest
                if os.path.isdir(candidate):
                    results.append(candidate)
                return
            # Try component boundaries — shortest first, then longer
            component = "." + rest[:next_dash]
            new_prefix = prefix + "/" + component
            if os.path.isdir(new_prefix):
                _decode_project_dir_recursive(new_prefix, rest[next_dash + 1:], results)
            j = next_dash + 1
            while j < len(rest):
                next_dash2 = rest.find("-", j)
                if next_dash2 == -1:
                    candidate = prefix + "/." + rest
                    if os.path.isdir(candidate):
                        results.append(candidate)
                    break
                component = "." + rest[:next_dash2]
                new_prefix = prefix + "/" + component
                if os.path.isdir(new_prefix):
                    _decode_project_dir_recursive(new_prefix, rest[next_dash2 + 1:], results)
                j = next_dash2 + 1
            return

        # dash_pos > 0: text before the dash is (part of) a component
        component = remainder[:dash_pos]
        new_prefix = prefix + "/" + component
        # Option A: this dash is a path separator
        if os.path.isdir(new_prefix):
            _decode_project_dir_recursive(new_prefix, remainder[dash_pos + 1:], results)
        # Option B: this dash is literal within the component name — keep scanning
        i = dash_pos + 1


def decode_project_dir(name: str) -> list[str]:
    """Decode a Claude projects directory name to possible filesystem paths.

    Returns a list of valid directory paths that match the encoded name.
    """
    # Strip leading dash (encodes the root '/')
    if name.startswith("-"):
        name = name[1:]
    if not name:
        return []

    results: list[str] = []
    _decode_project_dir_recursive("", name, results)
    return results


def discover_claude_projects() -> dict[str, str]:
    """Scan ~/.claude/projects/ and return {decoded_path: dirname} for valid entries."""
    if not os.path.isdir(CLAUDE_PROJECTS_DIR):
        return {}

    discovered: dict[str, str] = {}
    try:
        entries = os.listdir(CLAUDE_PROJECTS_DIR)
    except OSError:
        return {}

    for entry in entries:
        full = os.path.join(CLAUDE_PROJECTS_DIR, entry)
        if not os.path.isdir(full):
            continue
        paths = decode_project_dir(entry)
        for path in paths:
            discovered[path] = entry
    return discovered


def show_project_picker(project_name: str, candidates: list[str]) -> str | None:
    """Show a macOS dialog to pick a project directory. Returns selected path or None."""
    # Build AppleScript that reads paths from argv to avoid injection
    script = (
        'on run argv\n'
        '  set pathList to {}\n'
        '  repeat with p in argv\n'
        '    set end of pathList to (p as text)\n'
        '  end repeat\n'
        '  set chosen to choose from list pathList '
        'with title "Claunch" '
        f'with prompt "Select directory for project \\"{project_name}\\":" '
        'default items {{item 1 of pathList}}\n'
        '  if chosen is false then return ""\n'
        '  return item 1 of chosen\n'
        'end run'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script, "--"] + candidates,
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def save_project_mapping(config: dict | None, project_name: str, directory: str) -> dict:
    """Save a project mapping to config. Creates config dir/file if needed. Returns updated config."""
    config = dict(config) if config else {}
    projects = dict(config.get("projects") or {})
    projects[project_name] = directory
    config["projects"] = projects

    config_dir = os.path.dirname(CONFIG_PATH)
    os.makedirs(config_dir, exist_ok=True)

    # Atomic write
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

    return config


def resolve_unknown_project(
    project_name: str, config: dict | None,
) -> tuple[str, dict | None]:
    """Discover, pick, and save a project directory for an unknown project name.

    Returns (directory, updated_config). Raises ValueError on failure.
    """
    discovered = discover_claude_projects()
    if not discovered:
        raise ValueError(
            f"unknown project: {project_name!r} — not in config and "
            f"no Claude projects found in {CLAUDE_PROJECTS_DIR}"
        )

    # Filter candidates: exact basename match → partial → all
    exact = [p for p in discovered if os.path.basename(p) == project_name]
    partial = [p for p in discovered if project_name in os.path.basename(p)]

    if exact:
        candidates = exact
    elif partial:
        candidates = partial
    else:
        candidates = sorted(discovered.keys())

    # Auto-select if exactly one exact basename match
    if len(exact) == 1:
        directory = exact[0]
    else:
        candidates = sorted(candidates)
        directory = show_project_picker(project_name, candidates)
        if not directory:
            raise ValueError(f"project selection cancelled for {project_name!r}")

    config = save_project_mapping(config, project_name, directory)
    return directory, config


def parse_url(url: str, config: dict | None = None) -> tuple[str, str | None, int, dict | None]:
    """Parse a claunch:// URL and return (prompt, directory, version, updated_config).

    The directory is resolved from the 'project' parameter via config or auto-discovery.
    """
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

    v_values = params.get("v")
    if not v_values or not v_values[0].strip():
        raise ValueError("missing required 'v' parameter (e.g. v=1)")
    try:
        version = int(v_values[0])
    except ValueError:
        raise ValueError(f"invalid 'v' parameter: {v_values[0]!r} (expected integer)")

    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"unsupported version: {version} (supported: {sorted(SUPPORTED_VERSIONS)})")

    project_values = params.get("project")
    project = project_values[0] if project_values and project_values[0].strip() else None

    directory = None
    if project:
        projects = (config or {}).get("projects") or {}
        if project in projects:
            directory = projects[project]
        else:
            directory, config = resolve_unknown_project(project, config)

    if directory and not os.path.isdir(directory):
        raise ValueError(f"directory does not exist: {directory}")

    return prompt, directory, version, config


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
                [
                    "ghostty",
                    "+new-window",
                    f"--command={script_path}",
                    "--fullscreen=true",
                    "--macos-non-native-fullscreen=visible-menu",
                ],
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
        [
            "open",
            "-na",
            "Ghostty.app",
            "--args",
            f"--command={script_path}",
            "--fullscreen=true",
            "--macos-non-native-fullscreen=visible-menu",
        ]
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
        prompt, directory, version, config = parse_url(url, config)
    except ValueError as e:
        print(f"claunch: {e}", file=sys.stderr)
        sys.exit(1)

    claude_command = f"claude {shlex.quote(prompt)}"
    script_path = write_temp_script(directory, claude_command)
    launch_in_terminal(config, script_path, directory, claude_command)


if __name__ == "__main__":
    main()
