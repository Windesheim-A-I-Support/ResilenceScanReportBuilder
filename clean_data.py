import pandas as pd
import os
import re
from pathlib import Path
from datetime import datetime
import shutil

# Configuration
DATA_DIR = "/app/data"
INPUT_PATH = "/app/outputs/cleaned_master.csv"
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# Required columns for report generation
REQUIRED_COLUMNS = ["company_name", "name"]
RECOMMENDED_COLUMNS = ["email_address", "submitdate", "sector"]


def create_backup(file_path):
    """Create a timestamped backup of a file."""
    if not Path(file_path).exists():
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path(file_path).stem
    ext = Path(file_path).suffix
    backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}{ext}")

    shutil.copy2(file_path, backup_path)
    print(f"[BACKUP] Backup created: {backup_path}")
    return backup_path


def validate_required_columns(df, issues):
    """
    Check if required columns exist in the dataframe.
    Returns True if all required columns are present.
    """
    print("\n[SAMPLE] Validating required columns...")

    df_cols_lower = [col.lower() for col in df.columns]
    missing_required = []
    missing_recommended = []

    # Check required columns
    for req_col in REQUIRED_COLUMNS:
        if req_col.lower() not in df_cols_lower:
            missing_required.append(req_col)
            issues.append(f"[ERROR] CRITICAL: Required column '{req_col}' not found")

    # Check recommended columns
    for rec_col in RECOMMENDED_COLUMNS:
        if rec_col.lower() not in df_cols_lower:
            missing_recommended.append(rec_col)
            issues.append(
                f"[WARNING]  WARNING: Recommended column '{rec_col}' not found"
            )

    if missing_required:
        print(f"   [ERROR] Missing required columns: {', '.join(missing_required)}")
        return False

    print("   [OK] All required columns present")

    if missing_recommended:
        print(
            f"   [WARNING]  Missing recommended columns: {', '.join(missing_recommended)}"
        )

    return True


def fix_company_names(df, issues):
    """
    Fix company name column - removes rows with invalid values.
    """
    print("\n[COMPANY] Cleaning company names...")

    if "company_name" not in df.columns:
        issues.append("[ERROR] Cannot clean company names - column not found")
        return df

    initial_count = len(df)

    # Remove rows with empty/null/invalid company names
    df = df[df["company_name"].notna()]
    df = df[df["company_name"].astype(str).str.strip() != ""]
    df = df[df["company_name"].astype(str).str.strip() != "-"]
    df = df[df["company_name"].astype(str).str.lower().str.strip() != "unknown"]

    # Trim whitespace
    df["company_name"] = df["company_name"].astype(str).str.strip()

    removed_count = initial_count - len(df)

    if removed_count > 0:
        print(f"   [REMOVE]  Removed {removed_count} rows with invalid company names")
        issues.append(f"Removed {removed_count} rows with invalid company names")
    else:
        print("   [OK] All company names valid")

    return df


def fix_person_names(df, issues):
    """
    Fix person name column - trims whitespace.
    """
    print("\n[PERSON] Cleaning person names...")

    if "name" not in df.columns:
        issues.append("[WARNING]  Name column not found")
        return df

    # Count empty/null values
    empty_count = df["name"].isna().sum()
    empty_count += (df["name"].astype(str).str.strip() == "").sum()

    if empty_count > 0:
        print(
            f"   [WARNING]  Found {empty_count} empty names (reports will use 'Unknown')"
        )
        issues.append(f"Found {empty_count} empty person names")

    # Trim whitespace for non-empty values
    df.loc[df["name"].notna(), "name"] = (
        df.loc[df["name"].notna(), "name"].astype(str).str.strip()
    )

    print("   [OK] Person names cleaned")

    return df


def fix_email_addresses(df, issues):
    """
    Fix email addresses - trim whitespace and validate format.
    """
    print("\n[EMAIL] Cleaning email addresses...")

    if "email_address" not in df.columns:
        issues.append("[WARNING]  Email address column not found")
        return df

    # Basic email regex
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    # Trim whitespace
    df.loc[df["email_address"].notna(), "email_address"] = (
        df.loc[df["email_address"].notna(), "email_address"].astype(str).str.strip()
    )

    # Check email format
    invalid_emails = 0
    for email in df["email_address"]:
        if pd.notna(email) and str(email).strip() != "":
            if not re.match(email_pattern, str(email)):
                invalid_emails += 1

    if invalid_emails > 0:
        print(
            f"   [WARNING]  Found {invalid_emails} potentially invalid email addresses"
        )
        issues.append(f"Found {invalid_emails} potentially invalid email addresses")
    else:
        print("   [OK] All email addresses valid")

    return df


def fix_numeric_columns(df, issues):
    """
    Fix score columns - ensure they contain numeric values.
    Converts non-numeric values to NaN.
    """
    print("\n[CLEAN] Cleaning numeric score columns...")

    score_columns = [
        col
        for col in df.columns
        if col.startswith("up__")
        or col.startswith("in__")
        or col.startswith("do__")
        or col.startswith("overall_")
    ]

    if not score_columns:
        print("   [INFO]  No score columns found")
        return df

    print(f"   Found {len(score_columns)} score columns")

    total_fixed = 0
    for col in score_columns:
        # Try to convert to numeric, coercing errors
        original = df[col].copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")

        # Count how many values were fixed
        fixed_count = df[col].isna().sum() - original.isna().sum()
        if fixed_count > 0:
            total_fixed += fixed_count

    if total_fixed > 0:
        print(f"   [FIX] Fixed {total_fixed} non-numeric values (converted to NaN)")
        issues.append(f"Fixed {total_fixed} non-numeric values in score columns")
    else:
        print("   [OK] All score columns contain valid numeric values")

    return df


def validate_data_sufficiency(df, issues):
    """
    Validate that companies have sufficient data for meaningful reports.
    """
    print("\n[DATA] Validating data sufficiency...")

    if "company_name" not in df.columns:
        return

    # Count respondents per company
    company_counts = df["company_name"].value_counts()

    # Check for companies with insufficient data
    single_respondent = company_counts[company_counts == 1]
    if len(single_respondent) > 0:
        print(
            f"   [WARNING]  WARNING: {len(single_respondent)} companies have only 1 respondent"
        )
        print("      These reports may have limited data/examples:")
        for company in single_respondent.head(5).index:
            print(f"      - {company}")
        if len(single_respondent) > 5:
            print(f"      ... and {len(single_respondent) - 5} more")
        issues.append(
            f"{len(single_respondent)} companies have only 1 respondent (limited data)"
        )

    # Check for missing dimension data
    score_columns = [
        col
        for col in df.columns
        if col.startswith("up__") or col.startswith("in__") or col.startswith("do__")
    ]

    if score_columns:
        # Group by company and check missing data
        for company in df["company_name"].unique():
            company_data = df[df["company_name"] == company]
            missing_pct = (
                company_data[score_columns].isna().sum().sum()
                / (len(company_data) * len(score_columns))
                * 100
            )

            if missing_pct > 50:
                print(
                    f"   [WARNING]  {company}: {missing_pct:.0f}% of dimension data missing"
                )
                issues.append(f"{company}: {missing_pct:.0f}% dimension data missing")


def generate_cleaning_report(df, issues, original_count):
    """
    Generate a summary report of cleaning actions.
    """
    print("\n" + "=" * 70)
    print("[DATA] DATA CLEANING REPORT")
    print("=" * 70)

    print("\n[OK] CLEANED DATA:")
    print(f"   - Original records: {original_count}")
    print(f"   - Final records: {len(df)} ({original_count - len(df)} removed)")
    print(f"   - Total columns: {len(df.columns)}")

    if "company_name" in df.columns:
        print(f"   - Unique companies: {df['company_name'].nunique()}")

        # Show distribution of respondents per company
        company_counts = df["company_name"].value_counts()
        print("\n   Company size distribution:")
        print(f"     - 1 respondent:  {(company_counts == 1).sum()} companies")
        print(
            f"     - 2-5 respondents: {((company_counts >= 2) & (company_counts <= 5)).sum()} companies"
        )
        print(
            f"     - 6-10 respondents: {((company_counts >= 6) & (company_counts <= 10)).sum()} companies"
        )
        print(f"     - 10+ respondents: {(company_counts > 10).sum()} companies")

    if "sector" in df.columns:
        print(f"   - Unique sectors: {df['sector'].nunique()}")

    if issues:
        print(f"\n[WARNING]  ISSUES FOUND ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("\n[OK] NO ISSUES FOUND - Data is clean and sufficient!")

    print("=" * 70)


def clean_and_fix():
    """
    Main function: Load cleaned_master.csv, fix data problems, save back.
    Returns (success: bool, summary: str) tuple.
    """
    print("=" * 70)
    print("[CLEAN] DATA CLEANING - FIXING DATA QUALITY ISSUES")
    print("=" * 70)

    issues = []
    summary_lines = []

    # Step 0: Check if data directory exists
    if not os.path.isdir("/app/data"):
        print("\n[ERROR] FAILED: Data directory not found: /app/data")
        print(
            "   Please ensure the data directory exists and contains the converted data file"
        )
        return False, "Data directory not found"

    # Step 1: Check if input file exists
    if not Path(INPUT_PATH).exists():
        print(f"\n[ERROR] FAILED: File not found: {INPUT_PATH}")
        print(
            "   Please run 'Convert Data' first to create cleaned_master.csv from your Excel file"
        )
        return False, "File not found"

    # Step 2: Create backup
    create_backup(INPUT_PATH)

    # Step 3: Load the CSV
    print(f"\n[LOAD] Loading data from: {INPUT_PATH}")
    try:
        df = pd.read_csv(INPUT_PATH)
        original_count = len(df)
        print(f"   [OK] Loaded: {len(df)} rows × {len(df.columns)} columns")
    except Exception as e:
        print(f"   [ERROR] Failed to load: {e}")
        return False, f"Failed to load: {e}"

    # Step 4: Validate required columns
    if not validate_required_columns(df, issues):
        print("\n[ERROR] FAILED: Missing required columns")
        return False, "Missing required columns"

    # Step 5: Fix company names (removes invalid rows)
    rows_before = len(df)
    df = fix_company_names(df, issues)
    rows_removed = rows_before - len(df)
    if rows_removed > 0:
        summary_lines.append(f"Removed {rows_removed} invalid company name(s)")

    # Step 6: Fix person names (trim whitespace)
    df = fix_person_names(df, issues)

    # Step 7: Fix email addresses (trim whitespace, validate)
    df = fix_email_addresses(df, issues)

    # Step 7b: Remove rows without email addresses
    rows_before = len(df)
    if "email_address" in df.columns:
        df = df[
            df["email_address"].notna()
            & (df["email_address"].astype(str).str.strip() != "")
        ]
        rows_removed = rows_before - len(df)
        if rows_removed > 0:
            summary_lines.append(
                f"Removed {rows_removed} row(s) without email addresses"
            )
            print(f"   [OK] Removed {rows_removed} row(s) without email addresses")

    # Step 7c: Remove duplicate records (same company, name, email)
    rows_before = len(df)
    if (
        "company_name" in df.columns
        and "name" in df.columns
        and "email_address" in df.columns
    ):
        df = df.drop_duplicates(
            subset=["company_name", "name", "email_address"], keep="first"
        )
        rows_removed = rows_before - len(df)
        if rows_removed > 0:
            summary_lines.append(f"Removed {rows_removed} duplicate record(s)")
            print(f"   [OK] Removed {rows_removed} duplicate record(s)")

    # Step 8: Fix numeric columns (convert to numeric)
    score_cols_before = [
        col
        for col in df.columns
        if col.startswith(("up__", "in__", "do__", "overall_"))
    ]
    fixed_values = 0
    for col in score_cols_before:
        original = df[col].copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        fixed_values += df[col].isna().sum() - original.isna().sum()

    if fixed_values > 0:
        summary_lines.append(
            f"Fixed {fixed_values} non-numeric value(s) in score columns"
        )

    # Step 9: Validate data sufficiency
    validate_data_sufficiency(df, issues)

    # Step 10: Generate cleaning report
    generate_cleaning_report(df, issues, original_count)

    # Step 10: Save cleaned data back to same file
    print(f"\n[SAVE] Saving cleaned data to: {INPUT_PATH}")

    try:
        df.to_csv(INPUT_PATH, index=False, encoding="utf-8")

        print("   [OK] Saved successfully!")
        print(f"   [DATA] Final shape: {df.shape[0]} rows × {df.shape[1]} columns")

        # Show sample of cleaned data
        print("\n[SAMPLE] Sample of cleaned data (first 3 rows, first 5 columns):")
        display_cols = min(5, len(df.columns))
        print(df.iloc[:3, :display_cols].to_string())

        print("\n" + "=" * 70)
        print("[OK] SUCCESS: Data cleaning completed!")
        print("=" * 70)
        print("\n[INFO]  Data is ready for report generation!")

        # Build summary for GUI
        if not summary_lines:
            summary = "No issues found - data was already clean!"
        else:
            summary = "\n".join(summary_lines)

        return True, summary

    except Exception as e:
        print(f"\n[ERROR] FAILED to save: {e}")
        return False, f"Failed to save: {e}"


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    import sys

    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    success, summary = clean_and_fix()
    exit(0 if success else 1)
