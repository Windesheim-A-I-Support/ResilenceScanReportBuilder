"""
convert_data.py — converts the Excel master database to cleaned_master.csv.

Called by the GUI's "Convert Data" button via convert_and_save() -> bool.
Also runnable standalone: python convert_data.py
"""

import os
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path resolution — same strategy as clean_data.py
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    if sys.platform == "win32":
        _user_base = Path(os.environ.get("APPDATA", Path.home())) / "ResilienceScan"
    else:
        _user_base = Path.home() / ".local" / "share" / "resiliencescan"
else:
    _user_base = Path(__file__).resolve().parent

DATA_DIR = _user_base / "data"
OUTPUT_PATH = DATA_DIR / "cleaned_master.csv"

_EXCEL_EXTENSIONS = (".xlsx", ".xls")
# Columns whose presence marks the real header row
_HEADER_MARKERS = {"submitdate", "reportsent"}


def _normalize_col(name: str) -> str:
    """Normalize an Excel column name to cleaned_master.csv convention.

    Removes non-alphanumeric characters (keeping spaces), then replaces
    spaces with underscores.  Examples:
      'Name:'          -> 'name'
      'E-mail address' -> 'email_address'
      'Up - R1a'       -> 'up__r1a'
      '# competitors'  -> '_competitors'
    """
    name = str(name).lower().strip()
    name = re.sub(r"[^a-z0-9 ]", "", name)  # drop non-alphanumeric, keep spaces
    name = name.replace(" ", "_")
    return name


def _find_excel(data_dir: Path) -> Path | None:
    """Return the first Excel file in data_dir (.xlsx preferred over .xls)."""
    for ext in _EXCEL_EXTENSIONS:
        matches = sorted(data_dir.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def _header_skiprows(path: Path, sheet: str | int) -> int:
    """Return the number of rows to skip so the real column header is row 0.

    Scans the first 10 rows for one that contains a known header marker
    ('submitdate' or 'reportsent').  Falls back to 0 if not found.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=10)
    for i, row in raw.iterrows():
        vals = {str(v).lower().strip() for v in row if pd.notna(v)}
        if vals & _HEADER_MARKERS:
            return int(i)
    return 0


def _read_excel(path: Path) -> pd.DataFrame:
    """Read the Excel file, auto-detecting sheet name and header row."""
    xl = pd.ExcelFile(path)
    sheet = "MasterData" if "MasterData" in xl.sheet_names else xl.sheet_names[0]
    skip = _header_skiprows(path, sheet)
    return pd.read_excel(path, sheet_name=sheet, skiprows=skip)


def _preserve_reportsent(df: pd.DataFrame, old_csv: Path) -> pd.DataFrame:
    """Override reportsent values with those from the existing CSV.

    The app's CSV is the authoritative source for email-send tracking state;
    the Excel file may have been re-exported with stale values.  Matching is
    attempted in order: 'hash', 'email_address', then 'name'+'company_name'.
    """
    if "reportsent" not in df.columns or not old_csv.exists():
        return df
    try:
        old = pd.read_csv(old_csv, low_memory=False)
    except Exception:
        return df
    if "reportsent" not in old.columns:
        return df

    for key in ("hash", "email_address"):
        if key in old.columns and key in df.columns:
            mapping = old.dropna(subset=[key]).set_index(key)["reportsent"].to_dict()
            filled = df[key].map(mapping).fillna(df["reportsent"])
            df["reportsent"] = filled.infer_objects(copy=False)
            return df

    if {"name", "company_name"} <= (set(old.columns) & set(df.columns)):
        old_key = old["name"].astype(str) + "|" + old["company_name"].astype(str)
        new_key = df["name"].astype(str) + "|" + df["company_name"].astype(str)
        mapping = dict(zip(old_key, old["reportsent"]))
        filled = new_key.map(mapping).fillna(df["reportsent"])
        df["reportsent"] = filled.infer_objects(copy=False)
    return df


def convert_and_save() -> bool:
    """Convert the first Excel file in DATA_DIR to cleaned_master.csv.

    Preserves the reportsent column from any existing CSV so that email
    send-tracking state is not lost when the Excel source is refreshed.

    Returns True on success, False on failure.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    excel_file = _find_excel(DATA_DIR)
    if excel_file is None:
        print(f"[ERROR] No Excel file (.xlsx/.xls) found in {DATA_DIR}")
        return False

    print(f"[INFO] Reading: {excel_file.name}")
    try:
        df = _read_excel(excel_file)
    except Exception as e:
        print(f"[ERROR] Cannot read Excel file: {e}")
        return False

    # Drop fully-empty rows and columns
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.dropna(axis=1, how="all")

    # Normalize column names to snake_case CSV convention
    df.columns = [_normalize_col(c) for c in df.columns]

    # Drop unnamed artifact columns produced by Excel formatting
    df = df.loc[:, ~df.columns.str.fullmatch(r"unnamed_\d+")]

    print(f"[INFO] {len(df)} rows, {len(df.columns)} columns after normalization")

    # Restore per-row send-tracking state from any existing CSV
    df = _preserve_reportsent(df, OUTPUT_PATH)

    # Guarantee reportsent column exists and defaults to False
    if "reportsent" not in df.columns:
        df.insert(1, "reportsent", False)

    try:
        df.to_csv(OUTPUT_PATH, index=False)
        print(f"[OK] Saved {len(df)} rows to {OUTPUT_PATH}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write CSV: {e}")
        return False


if __name__ == "__main__":
    ok = convert_and_save()
    exit(0 if ok else 1)
