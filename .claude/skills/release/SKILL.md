---
name: release
description: Tag a new version, wait for CI, and update the Homebrew tap
argument-hint: "[version, e.g. 0.2.0]"
disable-model-invocation: true
allowed-tools: Read, Edit, Bash(git *), Bash(gh *), Bash(sleep *)
---

Release a new version of Claunch. The version argument is required (e.g. `/release 0.2.0`).

Follow these steps exactly, stopping on any failure:

## 1. Validate

- The version argument (`$ARGUMENTS`) must be semver (e.g. `0.2.0`), without a `v` prefix.
  If missing or invalid, ask the user for the version.
- Run `git status` and confirm the working tree is clean (no uncommitted changes).
  If dirty, stop and tell the user to commit or stash first.

## 2. Bump version

Update the version string in both files:

- `pyproject.toml` — the `version = "..."` line
- `src/claunch/app/Info.plist` — both `<string>X.Y.Z</string>` values after
  `CFBundleVersion` and `CFBundleShortVersionString`

## 3. Commit and tag

```bash
git add pyproject.toml src/claunch/app/Info.plist
git commit -m "Bump version to $ARGUMENTS"
git tag "v$ARGUMENTS"
```

## 4. Push

```bash
git push origin main
git push origin "v$ARGUMENTS"
```

## 5. Wait for GitHub Actions

Poll the release workflow run until it completes (timeout after 5 minutes):

```bash
gh run list --workflow=release.yml --branch="v$ARGUMENTS" --limit=1 --json status,conclusion,databaseId
```

Poll every 15 seconds. If conclusion is `failure`, stop and tell the user.

## 6. Get sha256 from release

```bash
gh release view "v$ARGUMENTS" --repo skeetmtp/claunch
```

Extract the sha256 from the release body.

## 7. Update Homebrew tap

Edit `/Users/alban/Developer/claude/homebrew-claunch/Casks/claunch.rb`:

- Update `version "..."` to the new version
- Update `sha256 "..."` to the sha256 from step 6

Then commit and push:

```bash
cd /Users/alban/Developer/claude/homebrew-claunch
git pull origin main
# (edit the file)
git add Casks/claunch.rb
git commit -m "Update claunch to $ARGUMENTS"
git push origin main
```

## 8. Done

Print a summary:

```
Released v$ARGUMENTS
  GitHub: https://github.com/skeetmtp/claunch/releases/tag/v$ARGUMENTS
  Homebrew: brew install --cask skeetmtp/claunch/claunch
  sha256: <the sha256>
```
