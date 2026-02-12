#!/usr/bin/env python3
"""Build Claunch.app bundle from source files."""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "Claunch.app")
CONTENTS = os.path.join(APP_DIR, "Contents")
MACOS_DIR = os.path.join(CONTENTS, "MacOS")
RESOURCES_DIR = os.path.join(CONTENTS, "Resources")

SRC_SWIFT = os.path.join(ROOT, "src", "claunch", "app", "main.swift")
SRC_PLIST = os.path.join(ROOT, "src", "claunch", "app", "Info.plist")
SRC_HANDLER = os.path.join(ROOT, "src", "claunch", "handler.py")

BINARY = os.path.join(MACOS_DIR, "Claunch")
MIN_MACOS = "12.0"


def clean():
    if os.path.exists(APP_DIR):
        shutil.rmtree(APP_DIR)
        print(f"cleaned {APP_DIR}")


def create_dirs():
    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)
    print("created app bundle directories")


def compile_swift(*, universal=False):
    if universal:
        compile_universal()
    else:
        cmd = ["swiftc", "-o", BINARY, SRC_SWIFT]
        print(f"compiling: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("swift compilation failed", file=sys.stderr)
            sys.exit(1)
        os.chmod(BINARY, 0o755)
        print(f"compiled {BINARY}")


def compile_universal():
    archs = ["arm64", "x86_64"]
    slices = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for arch in archs:
            target = f"{arch}-apple-macosx{MIN_MACOS}"
            out = os.path.join(tmpdir, f"Claunch-{arch}")
            cmd = ["swiftc", "-o", out, "-target", target, SRC_SWIFT]
            print(f"compiling ({arch}): {' '.join(cmd)}")
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"swift compilation failed for {arch}", file=sys.stderr)
                sys.exit(1)
            slices.append(out)

        cmd = ["lipo", "-create"] + slices + ["-output", BINARY]
        print(f"creating universal binary: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("lipo failed", file=sys.stderr)
            sys.exit(1)

    os.chmod(BINARY, 0o755)
    print(f"compiled universal binary {BINARY}")


def copy_resources():
    shutil.copy2(SRC_PLIST, os.path.join(CONTENTS, "Info.plist"))
    shutil.copy2(SRC_HANDLER, os.path.join(RESOURCES_DIR, "handler.py"))
    print("copied Info.plist and handler.py into bundle")


def codesign():
    cmd = ["codesign", "--force", "--sign", "-", APP_DIR]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ad-hoc code signing failed", file=sys.stderr)
        sys.exit(1)
    print("ad-hoc signed app bundle")


def create_zip():
    zip_path = os.path.join(ROOT, "Claunch.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    cmd = ["ditto", "-c", "-k", "--keepParent", APP_DIR, zip_path]
    print(f"creating zip: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("ditto zip failed", file=sys.stderr)
        sys.exit(1)

    sha = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    digest = sha.hexdigest()
    print(f"\n{zip_path}")
    print(f"sha256: {digest}")
    return digest


def main():
    parser = argparse.ArgumentParser(description="Build Claunch.app")
    parser.add_argument("--universal", action="store_true",
                        help="Build universal binary (arm64 + x86_64)")
    parser.add_argument("--zip", action="store_true",
                        help="Create Claunch.zip and print sha256")
    args = parser.parse_args()

    print("building Claunch.app...")
    clean()
    create_dirs()
    compile_swift(universal=args.universal)
    copy_resources()
    codesign()
    print(f"\nbuild complete: {APP_DIR}")

    if args.zip:
        create_zip()


if __name__ == "__main__":
    main()
