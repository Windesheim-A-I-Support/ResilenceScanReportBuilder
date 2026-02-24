# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Set up Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the GUI (main application)
python ResilienceScanGUI.py

# Run pipeline steps individually
python clean_data.py                 # clean data/cleaned_master.csv in-place
python generate_all_reports.py       # render one PDF per row → reports/
python validate_reports.py           # validate generated PDFs against CSV values
python send_email.py                 # send PDFs (TEST_MODE=True by default)

# Run the template app (CI/packaging scaffold only)
python app/main.py

# Lint and test (CI)
pip install pytest ruff pyyaml PyPDF2
ruff check .
ruff format --check .
pytest
pytest tests/test_smoke.py::test_import_main_module   # single test
```

## Release workflow

Bump `version` in `pyproject.toml` and push to `main`. CI detects no git tag `v<version>` exists and fires the build matrix. Do **not** create tags manually. macOS is not a target — only Windows and Linux matter.

---

## Architecture

`ResilienceScanGUI.py` is a native Tkinter desktop application. It directly imports the Python pipeline modules and calls `quarto render` as a subprocess.

```
ResilienceScanGUI.py
  ├── imports convert_data          → Excel → data/cleaned_master.csv
  ├── imports clean_data            → cleans and validates CSV in-place
  ├── imports email_tracker         → tracks per-recipient send status
  ├── imports gui_system_check      → verifies R/Quarto/TinyTeX are present at runtime
  └── imports dependency_manager    → (stub only — installation handled by the installer)
```

`ResilienceScanGUI.py` (project root) is the development entry point. The content will be moved into `app/main.py` as the canonical entry point and PyInstaller target — the CI already points there. When moved, `ROOT_DIR` must use `Path(__file__).resolve().parents[1]` (one level up from `app/`) so that `data/`, `reports/`, and sibling scripts are resolved correctly.

---

## Pipeline flow

```
data/*.xlsx
     │ convert_data.py
     ▼
data/cleaned_master.csv
     │ clean_data.py
     ▼
data/cleaned_master.csv  [validated & cleaned]
     │ generate_all_reports.py + ResilienceReport.qmd  (calls quarto render)
     ▼
reports/YYYYMMDD ResilienceScanReport (Company - Person).pdf
     │ validate_reports.py
     ▼
     │ send_email.py
     ▼
emails via Outlook COM (Windows) or SMTP fallback (Office365)
```

**Key data file:** `data/cleaned_master.csv`
**Score columns:** `up__r/c/f/v/a`, `in__r/c/f/v/a`, `do__r/c/f/v/a` — range 0–5
**PDF naming:** `YYYYMMDD ResilienceScanReport (Company Name - Firstname Lastname).pdf`

---

## Packaging strategy

**Staged installer** — the installer itself silently downloads and sets up all dependencies (R, Quarto, TinyTeX, R packages) during installation. The user sees a normal setup wizard and nothing needs to be manually installed.

`ResilienceReport.qmd` is deeply LaTeX-dependent (TikZ, kableExtra, custom titlepage/coverpage extensions, custom fonts, raw `.tex` include files). The PDF engine **cannot** be switched to Typst or WeasyPrint — TinyTeX is required to preserve the output exactly.

### How it works

1. **PyInstaller** bundles the Python app and all Python packages into a single binary (~50 MB)
2. **The installer** (NSIS on Windows, post-install script on Linux) silently downloads and installs at setup time:
   - R 4.3.2
   - Quarto 1.6.39
   - TinyTeX + required LaTeX packages
   - Required R packages (installed into a local library alongside the app)
3. **At runtime**, `gui_system_check.py` verifies all components are present and shows a clear error if something is missing (e.g. installation was interrupted)

### Artifacts

| Platform | Installer | Size (approx) | Notes |
|----------|-----------|---------------|-------|
| Windows | NSIS `.exe` | ~200 MB download, ~600 MB installed | Requires internet during install; Outlook COM available |
| Linux | `.deb` / `.rpm` / `.AppImage` | ~200 MB download, ~600 MB installed | Post-install script runs setup; SMTP only |

### R packages required by `ResilienceReport.qmd`

`readr`, `dplyr`, `stringr`, `tidyr`, `ggplot2`, `knitr`, `fmsb`, `scales`, `viridis`, `patchwork`, `RColorBrewer`, `gridExtra`, `png`, `lubridate`, `kableExtra`, `rmarkdown`, `jsonlite`, `ggrepel`, `cowplot`

### LaTeX packages required by `ResilienceReport.qmd`

`geometry`, `pdflscape`, `afterpage`, `graphicx`, `float`, `array`, `booktabs`, `longtable`, `multirow`, `wrapfig`, `colortbl`, `tabu`, `threeparttable`, `threeparttablex`, `ulem`, `makecell`, `xcolor`, `tikz`

### Pinned versions

- R: **4.3.2**
- Quarto: **1.6.39**
- TinyTeX: installed via `quarto install tinytex` (uses Quarto-pinned version)

---

## Known issues

| Issue | Location | Fix |
|-------|----------|-----|
| CI action versions all wrong (`@v6` doesn't exist) | `ci.yml` | `checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4` |
| CI builds wrong app (PySide6 placeholder) | `ci.yml` | Replace entry point with `app/main.py` after GUI is moved there |
| `img/` directory | ✓ resolved | All required images present (`corner-bg.png`, `logo.png`, `otter-bar.jpeg`) |
| `_extensions/` (Quarto titlepage) | ✓ resolved | `nmfs-opensci/titlepage` extension present and committed |
| `references.bib` | ✓ resolved | Present at repo root |
| `QTDublinIrish.otf` | ✓ resolved | Present at repo root and inside `_extensions/` font dirs |
| Hardcoded Docker paths `/app/data/`, `/app/outputs/` | `clean_data.py`, `clean_data_enhanced.py`, `generate_single_report.py` | Replace with user data directory paths |
| Two cleaning scripts with diverging logic | `clean_data.py`, `clean_data_enhanced.py` | Merge into `clean_data.py`, delete `clean_data_enhanced.py` |
| GUI imports `clean_data_enhanced` directly | `ResilienceScanGUI.py:1113` | Switch to `clean_data` after merge |
| Missing modules the GUI imports | `convert_data`, `email_tracker`, `gui_system_check`, `dependency_manager` | Create stubs in M1, full implementations in later milestones |
| `validate_reports.py` reads `validation_results.json` that nothing writes | `validate_reports.py` | Use `validate_single_report.py` as shared logic; derive values from CSV |
| `validate_pipeline_docker.py` is Docker-specific and obsolete | — | Delete |
| Installed app cannot write to `Program Files` / `/usr/bin/` | all scripts | User data (`data/`, `reports/`, `config.yml`) must go to `%APPDATA%` / `~/.local/share/` |
| PyInstaller `--onefile` breaks path resolution for data files | `ci.yml` | Switch to `--onedir` |
| `data/`, `reports/`, `config.yml` not in `.gitignore` | `.gitignore` | Add — respondent data must not be committed |

---

## Working rule

**Do not start the next milestone until the current one is fully verified by its gate condition.** Each gate must pass on a clean run before any work on the next milestone begins. If a gate fails, fix it before moving on — do not carry broken behaviour forward.

---

## Task list — milestones (CD: pipeline ships a real installer after every milestone)

### MILESTONE 1 — Fix the CI and ship the real app ✅ DONE (v0.13.0)
- [x] Fix action versions, remove macOS, switch to `--onedir`, fix system libs, update requirements
- [x] Create stub modules, move GUI to `app/main.py`, add `--add-data` flags, update tests
- [x] User-writable data directories (`%APPDATA%\ResilienceScan` / `~/.local/share/resiliencescan`)
- [x] Housekeeping (`.gitignore`, delete docker scripts)
- **Gate:** ✅ CI green, Windows installer + Linux packages on GitHub Release

### MILESTONE 2 — Fix paths and consolidate cleaning scripts ✅ DONE (v0.14.0)
- [x] Merge `clean_data_enhanced.py` into `clean_data.py`, fix all Docker paths, delete enhanced script
- [x] Fix `generate_single_report.py` and `generate_all_reports.py` paths
- **Gate:** ✅ `python clean_data.py` completes on real CSV, installer ships

### MILESTONE 3 — Implement data conversion ✅ DONE (v0.15.0)
- [x] Implement `convert_data.py` fully (Excel → CSV, preserves `reportsent`)
- **Gate:** ✅ GUI "Convert Data" button works, installer ships

### MILESTONE 4 — Verify end-to-end report generation ✅ DONE (v0.16.0)
- [x] Pipeline verified locally (R 4.5.2, Quarto 1.8.27, TinyTeX)
- [x] GUI Generation tab streams stdout, progress bar + Cancel work
- **Gate:** ✅ GUI generates visually correct PDF, installer ships

### MILESTONE 5 — Fix validation ✅ DONE (v0.17.0)
- [x] Rewrite `validate_reports.py` (no JSON dependency, uses `validate_single_report`)
- [x] Implement `email_tracker.py` fully (persists to user data dir)
- [x] Fix PyPDF2 μ→period extraction pattern
- **Gate:** ✅ Validation pass rate ≥ 90%, installer ships

### MILESTONE 6 — Email sending ✅ DONE (v0.18.0)
- [x] SMTP credentials in `config.yml` (writable user data dir), GUI Save Configuration button
- [x] Fix pythoncom Linux crash (try/except ImportError)
- [x] Wire `email_tracker.mark_sent()` / `mark_failed()` after each send
- **Gate:** ✅ GUI sends test email with PDF attached, installer ships

### MILESTONE 7 — Implement `gui_system_check.py` and startup guard ✅ DONE (v0.19.0)
- [x] Full `gui_system_check.py` (checks R, Quarto, TinyTeX, all 19 R packages)
- [x] `_startup_guard()` blocks launch with dialog if components missing
- **Gate:** ✅ Removing Quarto from PATH triggers guard dialog, installer ships

### MILESTONE 8 — Complete the installer (R + Quarto + TinyTeX bundled setup) ✅ DONE (v0.20.5)
- [x] `packaging/setup_dependencies.ps1` — Windows silent R/Quarto/TinyTeX/R-package install
- [x] `packaging/setup_linux.sh` — Linux equivalent (DEBIAN_FRONTEND, system libs for kableExtra)
- [x] `packaging/postinst.sh` — deferred launcher (nohup+disown avoids dpkg lock deadlock)
- [x] NSIS installer runs PS1 via nsExec after extraction
- [x] dpkg-deb builds .deb with postinst + setup_linux.sh bundled in `/opt/REPO_NAME/`
- [x] `_r_library_path()` + R_LIBS injection in quarto render subprocess
- [x] TinyTeX binaries symlinked to `/usr/local/bin` via `$HOME/.TinyTeX/bin/x86_64-linux`
- **Gate:** ✅ Docker Ubuntu 22.04 fresh-machine test: R 4.5.2 + Quarto 1.6.39 + all 19 R packages + system check PASS
