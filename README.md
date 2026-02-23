# my-app

> **Fork this template** to ship a Python desktop app to every platform automatically.

A GitHub template that packages and releases a Python application as:

| Platform | Artifacts |
|----------|-----------|
| Windows  | `.exe` |
| macOS    | `.app.zip`, `.dmg` |
| Linux    | `.AppImage`, `.deb`, `.rpm` |

Releases are fully automated — no pull requests, no manual steps.

---

## How it works

```
bump version in pyproject.toml
push to main  →  CI (lint + test)  →  new version detected
                                    →  GitHub Release created automatically
                                    →  .exe / .app / .dmg / .AppImage / .deb / .rpm attached
```

---

## Getting started

### 1. Fork and rename

Fork this repository, then update these files:

| File | What to change |
|------|---------------|
| `pyproject.toml` | `name`, `description` |
| `nfpm.yaml` | `maintainer`, `homepage` |
| `packaging/template.desktop` | `Name`, `Categories` |
| `app/main.py` | Replace with your application |
| `requirements.txt` | Your runtime dependencies |

### 2. Replace the app

All application code lives in `app/main.py`. The entry point must be `app/main.py` (matched in the PyInstaller build command in the workflow). Replace the example PySide6 app with your own.

### 3. Add icons (optional)

Place icons in `assets/`:

| File | Used by |
|------|---------|
| `assets/icon.ico` | Windows `.exe` |
| `assets/icon.icns` | macOS `.app` |
| `assets/icon.png` | Linux AppImage |

If omitted, the binary is built without an icon.

### 4. Enable release-please

Release Please needs write access to open PRs and create releases.

In your repository: **Settings → Actions → General → Workflow permissions** → set to **Read and write permissions**.

### 5. Ship a release

Bump the version in `pyproject.toml`, then push:

```bash
# Edit pyproject.toml: version = "1.0.0"
git add pyproject.toml
git commit -m "chore: release 1.0.0"
git push origin main
```

Once CI passes, the release workflow detects the new version tag does not yet
exist and automatically:
1. Builds `.exe`, `.app.zip`, `.dmg`, `.AppImage`, `.deb`, `.rpm`
2. Creates a `v1.0.0` GitHub Release with all artifacts attached

Subsequent pushes with the same version are ignored — a release is only
created once per version number.

---

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/main.py          # run the app
pytest                      # run tests
```

---

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | every push / PR | lint (ruff) + tests (pytest) |
| `release.yml` | CI passes on main | detect new version → build + publish release |
| `codeql.yml` | push / PR / weekly | security analysis |

---

## Project structure

```
├── app/
│   └── main.py                  # your application — edit this
├── assets/                      # icons (optional)
├── packaging/
│   └── template.desktop         # Linux desktop entry template
├── tests/
│   └── test_smoke.py
├── nfpm.yaml                    # Linux package config (.deb / .rpm)
├── requirements.txt             # runtime dependencies
└── pyproject.toml
```
