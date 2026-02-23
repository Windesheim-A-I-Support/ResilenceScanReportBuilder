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

### MILESTONE 1 — Fix the CI and ship the real app (unblocks everything)
The CI is currently broken (wrong action versions) and builds the wrong app. Several template assets required by `ResilienceReport.qmd` are also missing from the repo entirely — without them no report can ever render. Fix all of this first so every subsequent commit ships a real, improvable installer.

**CI fixes:**
- [ ] **1a** Fix action versions in `ci.yml`: `checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4`.
- [ ] **1b** Remove macOS from the CI build matrix.
- [ ] **1c** Switch PyInstaller from `--onefile` to `--onedir` on both Windows and Linux. `--onefile` re-extracts the entire app on every launch and causes path resolution failures for data files. `--onedir` is required for a complex app with assets.
- [ ] **1d** Fix Linux system libraries in `ci.yml` — remove Qt/PySide6 libs (`libxkbcommon-x11-0` etc.), add `python3-tk` and `tk-dev` for tkinter.
- [ ] **1e** Update `requirements.txt`: replace `PySide6` / `requests` with `pandas`, `numpy`, `openpyxl`, `xlrd`, `PyPDF2`, `pyyaml`.

**Missing template assets (reports cannot render without these):**
- [x] **1f** `img/` directory confirmed present with all required images (`corner-bg.png`, `logo.png`, `otter-bar.jpeg`).
- [x] **1g** `references.bib` confirmed present at repo root.
- [x] **1h** `QTDublinIrish.otf` confirmed present (repo root + inside `_extensions/` font dirs).
- [x] **1i** Quarto titlepage extension confirmed present (`_extensions/nmfs-opensci/titlepage/` and `_extensions/titlepage/`).

**Move the real app into the CI target:**
- [ ] **1j** Create four stub modules so `ResilienceScanGUI.py` can be imported without errors:
  - `convert_data.py` — stub `convert_and_save() → bool`
  - `email_tracker.py` — stub `EmailTracker` class with required method signatures
  - `gui_system_check.py` — stub `SystemChecker` class
  - `dependency_manager.py` — stub `DependencyManager` class
- [ ] **1k** Move `ResilienceScanGUI.py` into `app/main.py`. Change `ROOT_DIR = Path(__file__).resolve().parent` → `ROOT_DIR = Path(__file__).resolve().parents[1]`. Delete the root `ResilienceScanGUI.py`.
- [ ] **1l** Add `--add-data` flags to the PyInstaller command for all template assets: `ResilienceReport.qmd`, `img/`, `tex/`, `_extensions/`, `references.bib`, and the custom font file. These must be accessible to `quarto render` at runtime.
- [ ] **1m** Update `tests/test_smoke.py` to import from the new entry point and mock tkinter (not PySide6).

**User-writable data directories:**
- [ ] **1n** Decide and document the user data path strategy: `data/` and `reports/` must be writable when the app is installed to `Program Files` (Windows) or `/usr/bin/` (Linux). Use `%APPDATA%\ResilienceScan\` on Windows and `~/.local/share/resiliencescan/` on Linux. Update `ROOT_DIR` usage in `app/main.py` to distinguish between read-only app resources (bundled assets) and writable user data.

**Housekeeping:**
- [ ] **1o** Add `data/`, `reports/`, `outputs/`, `config.yml` to `.gitignore` (respondent data must not be committed).
- [ ] **1p** Delete `validate_pipeline_docker.py` (Docker-specific, no longer relevant).
- [ ] **Gate:** Push to `main`, bump version → CI goes green, Windows installer and Linux packages attach to the GitHub Release. The installer opens the GUI window on a machine that has R and Quarto installed.

### MILESTONE 2 — Fix paths and consolidate cleaning scripts
- [ ] **2a** Merge all logic from `clean_data_enhanced.py` into `clean_data.py`. Use the user data directory (established in M1n) for all paths. Keep the `clean_and_fix() → (bool, str)` signature the GUI calls. Delete `clean_data_enhanced.py`.
- [ ] **2b** Fix `generate_single_report.py` — `OUTPUT_DIR` must point to the user data `reports/` directory.
- [ ] **2c** Fix all paths in `generate_all_reports.py` to use the same user data directory. App resources (QMD template, img/, tex/) must be read from the PyInstaller bundle path (`sys._MEIPASS` when frozen, repo root in development).
- [ ] **Gate:** `python clean_data.py` completes without error on a real CSV. Push → installer ships.

### MILESTONE 3 — Implement data conversion
- [ ] **3a** Implement `convert_data.py` fully: reads `.xlsx` from the user data `data/` directory, writes `cleaned_master.csv` there, preserves `reportsent` column from any existing CSV.
- [ ] **Gate:** GUI "Convert Data" button successfully converts an Excel file and the result appears in the Data tab. Push → installer ships.

### MILESTONE 4 — Verify end-to-end report generation
- [ ] **4a** Install R 4.3.2, Quarto 1.6.39, and TinyTeX locally (`quarto install tinytex`). Install all R packages from the packaging table. Install the Quarto titlepage extension (`quarto add nmfs-opensci/quarto_titlepages`).
- [ ] **4b** Gate (local only): `python generate_all_reports.py` produces at least one correctly rendered PDF in `reports/`. Open and visually verify the cover page, charts, and layout are intact.
- [ ] **4c** Wire the GUI Generation tab to run `generate_all_reports.py` logic in a background thread, streaming stdout to the log tab in real time. Confirm progress bar and Cancel button work cleanly (no temp files left on cancel).
- [ ] **Gate:** GUI generates a visually correct PDF end-to-end. Push → installer ships.

### MILESTONE 5 — Fix validation
`validate_single_report.py` already exists as a clean, reusable module. Use it as the foundation.
- [ ] **5a** Rewrite `validate_reports.py` to call `validate_single_report.validate_report()` for each PDF: scan the user data `reports/` directory, match each PDF to its CSV row by company+person name, aggregate results. Remove the `validation_results.json` dependency entirely.
- [ ] **5b** Implement `email_tracker.py` fully: persist state to the user data directory as `email_tracker.json`. Wire to the GUI Email Status tab (sent/pending/failed display).
- [ ] **Gate:** `python validate_reports.py` runs against generated PDFs and reports a pass rate ≥ 90%. Push → installer ships.

### MILESTONE 6 — Email sending
- [ ] **6a** Move SMTP credentials out of `send_email.py` into `config.yml` stored in the user data directory (not the repo). Wire the GUI Email tab SMTP fields to read/write this file.
- [ ] **6b** Gate (local): `python send_email.py` with `TEST_MODE = True` delivers one test email with the correct PDF attached.
- [ ] **6c** Wire GUI "Start Sending" to run `send_emails()` in a background thread, updating the email tracker and status display after each send.
- [ ] **Gate:** GUI sends a test email with PDF attached. Push → installer ships.

### MILESTONE 7 — Implement `gui_system_check.py` and startup guard
- [ ] **7a** Implement `gui_system_check.py` fully: check that `R`, `quarto`, and TinyTeX (`tlmgr`) are on PATH; verify the required R packages are installed; return a structured result with pass/fail per component.
- [ ] **7b** On app launch, run the system check. If anything is missing, show a blocking dialog with a clear description of what is missing and that the installation may be incomplete — do not silently proceed.
- [ ] **Gate:** Deliberately remove Quarto from PATH, launch the app, confirm the error dialog appears correctly. Push → installer ships with startup guard.

### MILESTONE 8 — Complete the installer (R + Quarto + TinyTeX bundled setup)
This is the final step that makes the installer fully self-contained. No internet connection should be required after the initial install.

- [ ] **8a** Extend the NSIS script in `ci.yml` to silently download and run during setup:
  - R 4.3.2 installer (from CRAN) — add R to system PATH
  - Rtools (required for compiling R packages with native code on Windows)
  - Quarto 1.6.39 installer (from GitHub releases) — add Quarto to system PATH
  - `quarto install tinytex` — then `tlmgr install` for all LaTeX packages listed in the packaging table
  - `Rscript -e "install.packages(c(...))"` for all R packages listed in the packaging table, installed to a fixed library path alongside the app
- [ ] **8b** Write the Linux post-install script (`.deb` / `.rpm` `postinst`) to do the equivalent using `apt` for R and the Quarto `.deb` from GitHub releases.
- [ ] **8c** Ensure the app knows where to find the R library installed by the installer (set `R_LIBS` env var or pass `lib=` to `library()` calls via the Quarto render command).
- [ ] **Gate:** Install on a **fresh machine with nothing pre-installed** → app opens, system check passes, generates a report, sends a test email. Bump version, push → final installer ships on GitHub Release.
