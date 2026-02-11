#!/usr/bin/env python3
"""Build Claunch.app bundle from source files."""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "Claunch.app")
CONTENTS = os.path.join(APP_DIR, "Contents")
MACOS_DIR = os.path.join(CONTENTS, "MacOS")
RESOURCES_DIR = os.path.join(CONTENTS, "Resources")

SRC_SWIFT = os.path.join(ROOT, "src", "claunch", "app", "main.swift")
SRC_PLIST = os.path.join(ROOT, "src", "claunch", "app", "Info.plist")
SRC_HANDLER = os.path.join(ROOT, "src", "claunch", "handler.py")


def clean():
    if os.path.exists(APP_DIR):
        shutil.rmtree(APP_DIR)
        print(f"cleaned {APP_DIR}")


def create_dirs():
    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    print("created app bundle directories")


def compile_swift():
    output = os.path.join(MACOS_DIR, "Claunch")
    cmd = ["swiftc", "-o", output, SRC_SWIFT]
    print(f"compiling: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("swift compilation failed", file=sys.stderr)
        sys.exit(1)
    os.chmod(output, 0o755)
    print(f"compiled {output}")


def copy_resources():
    shutil.copy2(SRC_PLIST, os.path.join(CONTENTS, "Info.plist"))
    shutil.copy2(SRC_HANDLER, os.path.join(RESOURCES_DIR, "handler.py"))
    print("copied Info.plist and handler.py into bundle")


def main():
    print("building Claunch.app...")
    clean()
    create_dirs()
    compile_swift()
    copy_resources()
    print(f"\nbuild complete: {APP_DIR}")


if __name__ == "__main__":
    main()
