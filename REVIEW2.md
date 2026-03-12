# REVIEW2.md — Independent Code Review (Round 2)

Date: 2026-03-12
Reviewer: Claude Sonnet 4.6
Version reviewed: v0.21.39

---

## Summary

The codebase is in substantially better shape than the original REVIEW.md baseline. The M25–M32 work correctly addressed thread-safety primitives, frozen-path splits, dead-code removal, shared utilities, test coverage, and the monolith refactor. 201 tests pass and ruff is clean.

This review identifies **19 new findings** across correctness, thread-safety, error handling, resource leaks, path correctness, test gaps, dead/duplicate code, and installer issues. The most important are:

- **Thread-safety regression**: `generate_reports_thread()` still writes Tkinter widget state directly from the background thread on lines 858–874, after all the M25 fixes in `_reset_ui` callbacks (§2.1).
- **Unreachable second `except` block**: A duplicate `except Exception` clause at line 863 in `gui_generate.py` can never execute but shadows the first handler's progress-update code (§1.1).
- **ROOT_DIR used for mutable data in frozen app**: `email_template.json` is saved to/loaded from `ROOT_DIR` in `gui_email.py`, which is read-only under Program Files in the installed app (§6.1).
- **SMTP missing `timeout=` in GUI send path**: The fallback SMTP path in `gui_email.py` at lines 1331 and 1372 constructs `smtplib.SMTP()` without `timeout=30`, unlike `send_email.py` (§3.1).
- **`safe_filename` / `safe_display_name` not using shared utils**: `gui_generate.py` still defines local copies of both helpers inside methods (§8.1).
- **`setup_linux.sh` sets `SETUP_RESULT="PASS"` unconditionally**: The final `SETUP_RESULT="PASS"` assignment runs even when earlier R-package errors set `SETUP_RESULT="FAIL"` (§9.1).

Total: 19 findings (3 HIGH, 10 MEDIUM, 6 LOW).

---

## §1 Correctness bugs

### 1.1 Unreachable duplicate `except Exception` clause — HIGH

**File:** `app/gui_generate.py:863`

**Problem:** There are two consecutive `except Exception as e:` handlers in `generate_reports_thread()`. Python resolves `except` clauses top-to-bottom; once the first `except Exception` at line 854 matches, the second one at line 863 (marked `# noqa: B025`) can never be reached. The intended behaviour was apparently to update the progress bar and label after every iteration — but the code that does this (lines 858–861 and 871–874) is split across the two unreachable/misplaced handlers.

The first handler at lines 854–856 correctly logs the error and increments `failed`, but it exits the `except` block **without** updating `self.gen_progress["value"]` or `self.gen_progress_label`. The second handler — which does both — is dead code. The net effect is that the progress bar and label are never updated when an exception occurs.

Additionally, `self.gen_progress["value"] = idx + 1` (lines 858 and 871) is a direct Tkinter widget write from a background thread, violating M25 thread-safety rules (see §2.1).

**Fix:** Collapse into one `except Exception` handler, and wrap the widget updates in `self.root.after(0, ...)` closures. Remove the `# noqa: B025` suppression.

---

### 1.2 `_send_emails_impl` reads `self.df` from background thread — MEDIUM

**File:** `app/gui_email.py:1058–1074`

**Problem:** `_send_emails_impl` runs on the email background thread but reads `self.df` directly at lines 1058–1074 to look up email addresses and `reportsent` values. `self.df` can be replaced on the main thread at any moment (e.g. by "Reload Data") without any synchronisation. This is a data-race: a concurrent replacement of `self.df` during a long send run can produce a `TypeError: 'NoneType' is not subscriptable` or silently use stale data.

**Fix:** Capture a local reference to `self.df` on the main thread before the background thread starts (similar to how `send_config` is assembled at lines 938–951), and pass it into `send_emails_thread` / `_send_emails_impl`.

---

### 1.3 `finalize()` callback accesses `self.df` without None-guard — MEDIUM

**File:** `app/gui_email.py:1441`

**Problem:** Inside the `finalize()` closure (scheduled via `root.after(0, finalize)`) at line 1441, the code does `if "reportsent" in self.df.columns:` without first checking `if self.df is not None`. If the user had removed/reloaded data while emails were being sent, `self.df` can be `None` at this point, raising `AttributeError: 'NoneType' object has no attribute 'columns'`.

**Fix:** Add `if self.df is not None and "reportsent" in self.df.columns:` guard.

---

### 1.4 `save_config()` crashes if `yaml` is None — MEDIUM

**File:** `app/gui_email.py:439`

**Problem:** `save_config()` calls `yaml.dump(...)` unconditionally. At the top of `gui_email.py`, `yaml` is imported with `try/except ImportError`, leaving `yaml = None` if PyYAML is not installed. Calling `None.dump(...)` raises `AttributeError` with no helpful error message. The `except Exception as e:` at line 443 would catch it, but the shown error ("Could not save configuration: 'NoneType' ...") is confusing.

**Fix:** Add an explicit check `if yaml is None: messagebox.showerror(...); return` at the start of `save_config()`, mirroring the guard needed in `load_config()` (which similarly calls `yaml.safe_load` without a None check at line 451).

---

## §2 Thread safety

### 2.1 Direct Tkinter widget writes in `generate_reports_thread()` — HIGH

**File:** `app/gui_generate.py:620–621, 635–642, 858–861, 871–874`

**Problem:** Despite M25 wrapping most widget updates in `root.after(0, ...)`, several direct Tkinter widget writes remain in the background generation thread:

- Lines 620–621: `self.gen_progress["maximum"] = total` and `self.gen_progress["value"] = 0` — direct widget access before the loop.
- Lines 635–642: `self.gen_current_label.config(...)` — direct access inside the per-row loop (the try/except for encoding errors is still a direct widget write).
- Lines 858–861 and 871–874: `self.gen_progress["value"] = idx + 1` and `self.gen_progress_label.config(...)` inside the exception handlers.

All of these are in the background thread started by `start_generation_all()`. The M25 `_reset_ui` closure at line 606–612 correctly uses `root.after`, but these other sites were missed.

**Fix:** Wrap each group in a `self.root.after(0, lambda: ...)` callback. For the per-row progress update, define an inline closure capturing `idx`, `total`, `success`, `failed`, `skipped`.

---

### 2.2 `is_generating` and `is_sending_emails` are plain booleans, not `threading.Event` — MEDIUM

**File:** `app/main.py:52–53`, `app/gui_generate.py:492, 508, 607, 876`, `app/gui_email.py:846, 934, 993, 1021, 1097, 1128, 1425, 1477`

**Problem:** M25 replaced `is_generating` with `_stop_gen = threading.Event()` for the cancellation signal, but `is_generating` (a bare `bool`) is still used as the "currently running" guard in `start_generation_all()` (line 492) and reset from the background thread at lines 607 and 876. Similarly, `is_sending_emails` is written from background threads at lines 993, 1021, 1097, 1425, and 1477.

In CPython, writing a boolean is effectively atomic, so this is unlikely to cause corruption in practice. However, reading `is_generating` on the main thread at line 492 without a memory barrier means the main thread could theoretically see a stale `False` if the thread was just started. The pattern also contradicts the M25 intention documented in CLAUDE.md.

**Fix:** Replace `is_generating` with a second `threading.Event` (`_is_generating`), or document explicitly that the plain boolean is safe enough in CPython. If kept as a bool, moves to `root.after(0, ...)` reset closures so the writes happen on the main thread.

---

## §3 Error handling

### 3.1 `smtplib.SMTP()` missing `timeout=` in GUI send path — MEDIUM

**File:** `app/gui_email.py:1331, 1372`

**Problem:** M29 added `timeout=30` to `smtplib.SMTP()` in `send_email.py`. The GUI's `_send_emails_impl` has two separate SMTP construction paths — the Outlook-fallback path (line 1331) and the direct-SMTP `else` branch (line 1372) — and neither passes `timeout`. A hung SMTP server will block the background email thread indefinitely.

**Fix:** Change both calls to `smtplib.SMTP(smtp_server, smtp_port, timeout=30)`.

---

### 3.2 SMTP port `int()` cast not guarded in `save_config()` and `send_config` assembly — MEDIUM

**File:** `app/gui_email.py:430, 942`

**Problem:** M28 fixed the port-cast in the old `app/main.py`. The refactored code now has two unguarded `int(self.smtp_port_var.get() or 587)` calls: one in `save_config()` (line 430) when writing to `config.yml`, and one in `start_email_all()` (line 942) when assembling `send_config`. If the user types "abc" in the SMTP Port field, `int("abc")` raises `ValueError` — crashing `save_config()` or `start_email_all()` without a friendly error message.

**Fix:** Wrap both casts with `try: int(...) except ValueError: messagebox.showerror(...); return`.

---

### 3.3 Email send loop uses one broad `except Exception` for all SMTP errors — LOW

**File:** `app/gui_email.py:1391`

**Problem:** The entire per-email send block (Outlook attempt + SMTP fallback) is wrapped in a single `except Exception as e:` at line 1391. `smtplib.SMTPAuthenticationError` (wrong credentials), `smtplib.SMTPException` (protocol error), `OSError` (network down), and `ValueError` (invalid email) all produce the same generic log entry `[ERROR] FAILED: {error_msg}`. The granular exception handling added to `send_email.py` in M28 is absent from the GUI path.

**Fix:** Add `except smtplib.SMTPAuthenticationError`, `except smtplib.SMTPException`, `except OSError` before the catch-all, matching the pattern in `send_email.py:217–228`.

---

## §4 Security

### 4.1 Hardcoded institution email addresses in source — LOW

**File:** `app/gui_email.py:1206–1209`

**Problem:** The Outlook account priority list hardcodes three specific email addresses:
```python
priority_accounts = [
    "info@resiliencescan.org",
    "r.deboer@windesheim.nl",
    "cg.verhoef@windesheim.nl",
]
```
These are personal/institutional addresses baked into source code committed to a repository. If this repo is ever made public or shared, those addresses are exposed and will attract spam. They also make the app non-configurable without code changes.

**Fix:** Move these to `config.yml` under an `outlook_accounts` key, with the current values as a documented default. Read them via `send_config` at send time.

---

## §5 Resource leaks

### 5.1 SMTP `server` object not closed in exception path in GUI send — MEDIUM

**File:** `app/gui_email.py:1331–1343`

**Problem:** In the Outlook-fallback SMTP block (lines 1331–1347), `server = smtplib.SMTP(...)` is constructed, then `server.starttls()`, `server.login(...)`, `server.send_message(...)`, `server.quit()` are called in sequence. If `send_message` raises (e.g. `SMTPDataError`), `server.quit()` is never called, leaving the connection open until the socket times out. The same pattern exists in the direct-SMTP `else` branch (lines 1372–1376).

**Fix:** Wrap each SMTP block in a `with smtplib.SMTP(...) as server:` context manager, or add a `try/finally: server.quit()`.

---

### 5.2 Temp PDF file not cleaned up in `generate_single_report_worker()` — MEDIUM

**File:** `app/gui_generate.py:342–480`

**Problem:** M28 added `finally: temp_path.unlink(missing_ok=True)` to `generate_all_reports.py`. The `generate_single_report_worker()` method in `gui_generate.py` creates a temp PDF at `temp_path = out_dir / temp_name` (line 343) but has no `finally` block to clean it up if `shutil.move()` fails or if an exception occurs after a successful render. If `shutil.move()` raises (e.g., cross-device move), the temp file remains on disk with the user-visible "temp_CompanyName_Person.pdf" name.

**Fix:** Wrap the `subprocess.run` + `shutil.move` block in `try/finally: temp_path.unlink(missing_ok=True)`, as done in `generate_all_reports.py:192–195`.

---

## §6 Path / frozen-app correctness

### 6.1 `email_template.json` saved to/loaded from `ROOT_DIR` — HIGH

**File:** `app/gui_email.py:478, 492`

**Problem:** `save_email_template()` writes the template to `ROOT_DIR / "email_template.json"` (line 478) and `load_email_template()` reads from the same path (line 492). `ROOT_DIR` maps to `sys._MEIPASS` (`_internal/`) in the frozen app, which is the read-only installation directory under Program Files (Windows) or `/opt` (Linux). Writing there raises `PermissionError` for non-admin users. The file will silently be missing on next launch, and attempts to save a customised template will fail.

**Fix:** Change both references from `ROOT_DIR` to `_DATA_ROOT` (from `app.app_paths`), matching how all other user-mutable data is stored. Update the import in `gui_email.py` to include `_DATA_ROOT`.

---

### 6.2 `run_integrity_validation()` uses relative `Path("./data/...")` — MEDIUM

**File:** `app/gui_data.py:652–653`

**Problem:** After calling `validate_data_integrity.main()`, the function reads results from `Path("./data/integrity_validation_report.json")` and `Path("./data/integrity_validation_report.txt")` (lines 652–653). These are relative paths resolved against the current working directory at runtime. In the frozen app, the CWD may be the install directory (read-only) or `Documents`, not the data directory. This is the same class of bug as the `view_cleaning_report` finding fixed in M26.

**Fix:** Replace with `_DATA_ROOT / "data" / "integrity_validation_report.json"` (and `.txt`), matching how `view_cleaning_report()` uses `_DATA_ROOT / "data" / "cleaning_report.txt"` at line 541.

---

## §7 Test gaps

### 7.1 No tests for `app_paths._sync_template()` logic — MEDIUM

**File:** `app/app_paths.py:62–107`

**Problem:** `_sync_template()` is the critical function that copies QMDs and assets from `_asset_root()` to `_data_root()` so Quarto can write `.quarto/` next to them. Its conditional copy logic (checks `src_qmd.stat().st_mtime <= dst_qmd.stat().st_mtime`) is tested nowhere. A regression here would silently fail to update templates after an app upgrade.

**Fix:** Add `test_frozen_paths.py` tests that monkeypatch `sys.frozen=True`, create a fake `src/` and `dst/` with controlled mtimes, and verify: (a) sync copies when `src` is newer, (b) sync is skipped when `dst` is current, (c) sync runs if `dst_qmd` does not exist.

---

### 7.2 No tests for `gui_email._send_emails_impl()` file-name parsing — MEDIUM

**File:** `app/gui_email.py:1036–1088`

**Problem:** `_send_emails_impl()` contains a custom PDF filename parser (lines 1044–1054) that splits on `"ResilienceScanReport ("` and `" - "`. This parser is duplicated from `validate_reports._parse_pdf_filename()` but uses a different (more fragile) `str.split` approach rather than a regex. There are no tests covering this parser for: legacy filenames, filenames containing " - " in the company name, or SCROL report filenames.

**Fix:** Extract the filename parser into a shared function (or re-use `validate_reports._parse_pdf_filename()`), and add unit tests in `test_email_send.py`.

---

### 7.3 No tests for `app_paths._check_r_packages_ready()` — LOW

**File:** `app/app_paths.py:133–173`

**Problem:** `_check_r_packages_ready()` is called before every generation run as a preflight check. It constructs an R subprocess and returns `None` or an error string. There are no tests verifying that it returns `None` when Rscript reports all packages OK, or an error string when Rscript reports missing packages, or gracefully handles subprocess timeout.

**Fix:** Add mocked-subprocess tests in a new `tests/test_app_paths.py`.

---

### 7.4 `test_send_emails_smtp_auth_error` assertion is too weak — LOW

**File:** `tests/test_email_send.py:169`

**Problem:** The auth-error test asserts `"Authentication error" in captured.out or "FAIL" in captured.out`. The `send_email.py` code actually prints `[ERROR] Authentication error (check username/password): ...` — so the test would pass even if the word "FAIL" appeared in any unrelated output. The assertion does not verify the auth-error-specific message is present as opposed to a generic exception message.

**Fix:** Tighten to `assert "Authentication error" in captured.out` without the `or "FAIL"` fallback.

---

## §8 Dead code / stubs

### 8.1 `safe_filename` and `safe_display_name` defined locally in `gui_generate.py` — MEDIUM

**File:** `app/gui_generate.py:284–302, 656–676`

**Problem:** M30 extracted these helpers into `utils/filename_utils.py` and wired them into `generate_all_reports.py`, `send_email.py`, and `validate_reports.py`. However, `gui_generate.py` still defines local copies of both functions inside two methods (`generate_single_report_worker` at lines 284–302, and `generate_reports_thread` at lines 656–676). The local definitions shadow the canonical shared implementations and will not receive bug-fix updates applied to `utils/filename_utils.py`.

**Fix:** Remove the local definitions and replace their call sites with `from utils.filename_utils import safe_filename, safe_display_name` at the top of `gui_generate.py`.

---

### 8.2 `use_outlook = True` / `else:` block in `_send_emails_impl` is unreachable — LOW

**File:** `app/gui_email.py:1193–1376`

**Problem:** `use_outlook` is set to `True` at line 1193 and never changed. The `else:` block at line 1348 (`# Direct SMTP if Outlook disabled`) can therefore never execute. It contains a full duplicate of the Outlook-fallback SMTP code (lines 1349–1376) — ~30 lines of unreachable code.

**Fix:** Remove the `use_outlook` variable and the entire `else:` branch. The Outlook-try / SMTP-fallback pattern is sufficient; a separate "direct SMTP if Outlook disabled" path is already handled by the fallback.

---

### 8.3 `update_time()` and `show_about()` belong in `DataMixin` but are general app concerns — LOW

**File:** `app/gui_data.py:1356–1381`

**Problem:** `update_time()` (updates status bar clock every second) and `show_about()` (About dialog) are defined in `DataMixin`. Neither is related to data operations. This is a minor cohesion issue from the M32 refactor — both methods would more naturally sit in `app/main.py` or a dedicated `GuiCoreMixin`.

**Fix:** Move `update_time()` and `show_about()` to `app/main.py` or a small `app/gui_core.py` mixin. This is low priority (cosmetic).

---

## §9 Installer

### 9.1 `SETUP_RESULT="PASS"` unconditionally overrides earlier failure in `setup_linux.sh` — HIGH

**File:** `packaging/setup_linux.sh:204–217`

**Problem:** The script sets `SETUP_RESULT="FAIL"` at line 18 (default) and again at line 206 when the final R-package retry still fails. But line 217 then sets `SETUP_RESULT="PASS"` unconditionally, regardless of what happened on line 206. Any R-package installation failure is silently promoted to `PASS` in `setup_complete.flag`.

The `_on_exit` trap writes `$SETUP_RESULT` to `setup_complete.flag`. Since line 217 runs after the retry-check (lines 192–211), even a definitively failed package install will write `"PASS"` to the flag, causing the app to display "Setup complete — all dependencies ready" when packages are actually missing.

**Fix:** Move `SETUP_RESULT="PASS"` inside the `else` branch of the `STILL_MISSING` check:
```bash
if [ -n "$STILL_MISSING" ]; then
    log "ERROR: ..."
    SETUP_RESULT="FAIL"
else
    log "R package retry succeeded..."
    SETUP_RESULT="PASS"
fi
```
And ensure the outer success path at line 217 is only reached when `MISSING` was empty from the start.

---

### 9.2 `set -e` in `setup_linux.sh` interacts poorly with `|| true` suppression — LOW

**File:** `packaging/setup_linux.sh:6, 190, 195, 202`

**Problem:** `set -e` causes any failing command to abort the script. The R-package verification at line 185–190 uses `|| true` to suppress failures from the `Rscript` call. However, the individual retry loop at line 195 (`Rscript -e "install.packages(...)" || true`) also suppresses failures. If Rscript itself is not on PATH after R installation, `Rscript` returns exit code 127. `|| true` silently suppresses this, and `MISSING` remains empty (because the `2>/dev/null || true` on line 190 prevents the output from being captured), leaving the app thinking all packages installed successfully.

**Fix:** Consider replacing `2>/dev/null || true` with error output redirected to the log, and using explicit `if command -v Rscript &>/dev/null; then ... fi` guards.

---

## §10 Consistency / minor issues

### 10.1 `pd.read_csv()` calls without `encoding=` in pipeline files — MEDIUM

**File:** `clean_data.py:412`, `convert_data.py:233`, `send_email.py:92`, `email_tracker.py:78`, `app/gui_data.py:311, 405, 443, 499`, `app/gui_email.py:1432`

**Problem:** M33 (listed as the next milestone in CLAUDE.md) targets `open()` calls, but `pd.read_csv()` and `pd.to_csv()` calls similarly lack `encoding=` parameters. On Windows with a non-UTF-8 ANSI code page (e.g., cp1252), pandas defaults to `locale.getpreferredencoding(False)` which may be cp1252. Respondent names containing accented characters (é, ü, ñ) could cause silent mojibake or `UnicodeDecodeError`.

**Fix:** Add `encoding="utf-8"` to all `pd.read_csv()` and `pd.to_csv()` calls that operate on `cleaned_master.csv` and related files.

---

### 10.2 `generate_all_reports.py` uses `ROOT / "data"` not `get_user_base_dir()` — LOW

**File:** `generate_all_reports.py:13–15`

**Problem:** The standalone script sets `ROOT = Path(__file__).resolve().parent`, then `DATA = ROOT / "data" / "cleaned_master.csv"` and `OUTPUT_DIR = ROOT / "reports"`. This is documented in CLAUDE.md as a "dev-only CLI tool", so it is intentional. However, there is no comment in the file itself stating this limitation. A user who runs the script from the installed binary's directory would silently read an empty `data/` directory.

**Fix:** Add a prominent comment `# NOTE: dev-only CLI tool — does not use the frozen-app data directory.` near the path constants.

---

### 10.3 `UBUNTU_CODENAME` sourcing may fail on non-Ubuntu distros — LOW

**File:** `packaging/setup_linux.sh:72`

**Problem:** `UBUNTU_CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")` sources `/etc/os-release` to get `UBUNTU_CODENAME`. On Debian and some Ubuntu derivatives, `UBUNTU_CODENAME` is not defined in `/etc/os-release` (only `VERSION_CODENAME` is). The fallback `${UBUNTU_CODENAME:-jammy}` hard-codes "jammy", so on Debian or Ubuntu 24.04+ (Noble) this will add an incorrect CRAN repository entry, causing `apt-get update` to fail or install outdated packages.

**Fix:** Use `VERSION_CODENAME` as the primary key with `UBUNTU_CODENAME` as a fallback:
```bash
CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-${VERSION_CODENAME:-jammy}}")
```

---

## Finding index

| # | File | Severity | Title |
|---|------|----------|-------|
| 1.1 | `app/gui_generate.py:854–874` | HIGH | Unreachable duplicate `except Exception` clause |
| 1.2 | `app/gui_email.py:1058–1074` | MEDIUM | `_send_emails_impl` reads `self.df` from background thread |
| 1.3 | `app/gui_email.py:1441` | MEDIUM | `finalize()` callback accesses `self.df` without None-guard |
| 1.4 | `app/gui_email.py:439, 451` | MEDIUM | `save_config()` and `load_config()` crash if yaml is None |
| 2.1 | `app/gui_generate.py:620–621, 635–642, 858–874` | HIGH | Direct Tkinter widget writes in background generation thread |
| 2.2 | `app/main.py:52–53`, `app/gui_generate.py`, `app/gui_email.py` | MEDIUM | `is_generating`/`is_sending_emails` plain booleans written from threads |
| 3.1 | `app/gui_email.py:1331, 1372` | MEDIUM | `smtplib.SMTP()` missing `timeout=` in GUI send path |
| 3.2 | `app/gui_email.py:430, 942` | MEDIUM | SMTP port `int()` cast not guarded with `try/except ValueError` |
| 3.3 | `app/gui_email.py:1391` | LOW | Broad `except Exception` for all SMTP errors in send loop |
| 4.1 | `app/gui_email.py:1206–1209` | LOW | Hardcoded institution email addresses in source |
| 5.1 | `app/gui_email.py:1331–1343, 1372–1376` | MEDIUM | SMTP `server` not closed in exception path |
| 5.2 | `app/gui_generate.py:342–480` | MEDIUM | Temp PDF file not cleaned up in `generate_single_report_worker()` |
| 6.1 | `app/gui_email.py:478, 492` | HIGH | `email_template.json` saved to read-only `ROOT_DIR` in frozen app |
| 6.2 | `app/gui_data.py:652–653` | MEDIUM | `run_integrity_validation()` uses relative `Path("./data/...")` |
| 7.1 | `app/app_paths.py:62–107` | MEDIUM | No tests for `_sync_template()` copy logic |
| 7.2 | `app/gui_email.py:1036–1088` | MEDIUM | No tests for email filename parser in `_send_emails_impl()` |
| 7.3 | `app/app_paths.py:133–173` | LOW | No tests for `_check_r_packages_ready()` |
| 7.4 | `tests/test_email_send.py:169` | LOW | `test_send_emails_smtp_auth_error` assertion too weak |
| 8.1 | `app/gui_generate.py:284–302, 656–676` | MEDIUM | `safe_filename`/`safe_display_name` still locally defined, not using shared utils |
| 8.2 | `app/gui_email.py:1193–1376` | LOW | `use_outlook = True` / `else:` branch is unreachable dead code |
| 8.3 | `app/gui_data.py:1356–1381` | LOW | `update_time()` and `show_about()` misplaced in `DataMixin` |
| 9.1 | `packaging/setup_linux.sh:217` | HIGH | `SETUP_RESULT="PASS"` unconditionally overrides earlier failure |
| 9.2 | `packaging/setup_linux.sh:6, 190, 195` | LOW | `set -e` + `|| true` silently swallows Rscript-not-found errors |
| 10.1 | Multiple pipeline files | MEDIUM | `pd.read_csv()`/`pd.to_csv()` calls without `encoding=` |
| 10.2 | `generate_all_reports.py:13–15` | LOW | No comment documenting dev-only limitation of path constants |
| 10.3 | `packaging/setup_linux.sh:72` | LOW | `UBUNTU_CODENAME` sourcing fails on Debian / Ubuntu 24.04+ |
