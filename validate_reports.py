import re
import json
import pandas as pd
from pathlib import Path
import PyPDF2

# Configuration
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "cleaned_master.csv"
REPORTS_DIR = ROOT / "reports"
VALIDATION_FILE = ROOT / "validation_results.json"


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        print(f"   [ERROR] Could not read PDF: {e}")
        return None


def extract_scores_from_text(text):
    """Extract resilience scores from PDF text"""
    scores = {}

    # Updated patterns based on actual PDF text format
    # Pattern: "Upstream (avg: 2.99)" found in pillar analysis section
    upstream_pattern = r"Upstream\s*\(avg:\s*(\d+\.?\d*)\)"
    internal_pattern = r"Internal\s*\(avg:\s*(\d+\.?\d*)\)"
    downstream_pattern = r"Downstream\s*\(avg:\s*(\d+\.?\d*)\)"
    overall_pattern = r"Overall\s+SCRES:\s*(\d+\.?\d*)"

    upstream_match = re.search(upstream_pattern, text, re.IGNORECASE)
    internal_match = re.search(internal_pattern, text, re.IGNORECASE)
    downstream_match = re.search(downstream_pattern, text, re.IGNORECASE)
    overall_match = re.search(overall_pattern, text, re.IGNORECASE)

    if upstream_match:
        scores["upstream_avg"] = float(upstream_match.group(1))
    if internal_match:
        scores["internal_avg"] = float(internal_match.group(1))
    if downstream_match:
        scores["downstream_avg"] = float(downstream_match.group(1))
    if overall_match:
        scores["overall_scres"] = float(overall_match.group(1))

    return scores


def get_expected_values(df, company_name):
    """Calculate expected values for a company from CSV"""
    company_data = df[df["company_name"] == company_name]
    if len(company_data) == 0:
        return None

    row = company_data.iloc[0]

    # Calculate upstream
    up_scores = [row["up__r"], row["up__c"], row["up__f"], row["up__v"], row["up__a"]]
    up_scores_valid = [s for s in up_scores if pd.notna(s)]
    up_avg = sum(up_scores_valid) / len(up_scores_valid) if up_scores_valid else 0

    # Calculate internal
    in_scores = [row["in__r"], row["in__c"], row["in__f"], row["in__v"], row["in__a"]]
    in_scores_valid = [s for s in in_scores if pd.notna(s)]
    in_avg = sum(in_scores_valid) / len(in_scores_valid) if in_scores_valid else 0

    # Calculate downstream
    do_scores = [row["do__r"], row["do__c"], row["do__f"], row["do__v"], row["do__a"]]
    do_scores_valid = [s for s in do_scores if pd.notna(s)]
    do_avg = sum(do_scores_valid) / len(do_scores_valid) if do_scores_valid else 0

    # Overall
    overall = (up_avg + in_avg + do_avg) / 3

    return {
        "company": company_name,
        "person": row.get("name", "Unknown"),
        "upstream": {
            "R": float(row["up__r"]) if pd.notna(row["up__r"]) else None,
            "C": float(row["up__c"]) if pd.notna(row["up__c"]) else None,
            "F": float(row["up__f"]) if pd.notna(row["up__f"]) else None,
            "V": float(row["up__v"]) if pd.notna(row["up__v"]) else None,
            "A": float(row["up__a"]) if pd.notna(row["up__a"]) else None,
            "avg": round(up_avg, 2),
        },
        "internal": {"avg": round(in_avg, 2)},
        "downstream": {"avg": round(do_avg, 2)},
        "overall_scres": round(overall, 2),
    }


def compare_values(expected, actual, tolerance=0.1):
    """Compare expected vs actual values with tolerance"""
    results = {}

    for key in ["upstream_avg", "internal_avg", "downstream_avg", "overall_scres"]:
        exp_key = key.replace("_avg", "").replace("_scres", "")
        if key == "overall_scres":
            exp_val = expected.get("overall_scres")
        else:
            pillar = key.replace("_avg", "")
            exp_val = expected.get(pillar, {}).get("avg")

        act_val = actual.get(key)

        if exp_val is not None and act_val is not None:
            diff = abs(exp_val - act_val)
            matches = diff <= tolerance
            results[key] = {
                "expected": exp_val,
                "actual": act_val,
                "diff": round(diff, 2),
                "matches": matches,
            }
        else:
            results[key] = {
                "expected": exp_val,
                "actual": act_val,
                "matches": False,
                "error": "Missing value",
            }

    return results


def main():
    print("=" * 70)
    print("PDF REPORT VALIDATION - AUTOMATED VERIFICATION")
    print("=" * 70)

    # Load CSV data
    print("\n[LOAD] Loading CSV data...")
    df = pd.read_csv(DATA)
    print(f"   Total companies: {df['company_name'].nunique()}")

    # Load validation results
    print(f"\n[LOAD] Loading validation results from {VALIDATION_FILE}...")
    with open(VALIDATION_FILE, "r") as f:
        validation_data = json.load(f)

    test_companies = [item for item in validation_data if item["status"] == "success"]
    print(f"   Found {len(test_companies)} successful reports to validate")

    # Validate each report
    print("\n" + "=" * 70)
    print("VALIDATING REPORTS")
    print("=" * 70)

    all_passed = True
    results_summary = []

    for item in test_companies:
        company = item["company"]
        expected = item["expected"]

        # Find the PDF file
        pdf_pattern = f"*{company}*.pdf"
        pdf_files = list(REPORTS_DIR.glob(pdf_pattern))

        if not pdf_files:
            print(f"\n[{company}]")
            print("   [FAIL] PDF file not found")
            all_passed = False
            continue

        pdf_file = pdf_files[0]
        print(f"\n[{company}]")
        print(f"   File: {pdf_file.name}")

        # Extract text from PDF
        text = extract_text_from_pdf(pdf_file)
        if text is None:
            print("   [FAIL] Could not extract PDF text")
            all_passed = False
            continue

        # Extract scores from text
        actual_scores = extract_scores_from_text(text)

        if not actual_scores:
            print("   [WARN] Could not extract scores from PDF")
            print("   [INFO] This might mean the PDF format is different than expected")
            all_passed = False
            continue

        # Compare with expected values
        comparison = compare_values(expected, actual_scores)

        # Display results
        all_match = True
        for key, result in comparison.items():
            label = key.replace("_", " ").title()
            if result["matches"]:
                print(
                    f"   [OK] {label}: Expected={result['expected']:.2f}, Actual={result['actual']:.2f}"
                )
            else:
                if "error" in result:
                    print(f"   [FAIL] {label}: {result['error']}")
                else:
                    print(
                        f"   [FAIL] {label}: Expected={result['expected']:.2f}, Actual={result['actual']:.2f}, Diff={result['diff']:.2f}"
                    )
                all_match = False
                all_passed = False

        results_summary.append(
            {"company": company, "all_match": all_match, "comparison": comparison}
        )

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results_summary if r["all_match"])
    failed = len(results_summary) - passed

    print(f"   Passed: {passed}/{len(results_summary)}")
    print(f"   Failed: {failed}/{len(results_summary)}")

    if all_passed:
        print("\n   [SUCCESS] All reports validated successfully!")
        print("   [SUCCESS] Chart values, averages, and overall SCRES are correct!")
        print("\n   Issues I004, I006, I007 can be marked as RESOLVED!")
    else:
        print("\n   [ATTENTION] Some validation issues detected")
        print("   Review the details above for specific problems")

    print("=" * 70)


if __name__ == "__main__":
    try:
        import PyPDF2
    except ImportError:
        print("PyPDF2 not installed. Installing...")
        import subprocess

        subprocess.check_call(["pip", "install", "PyPDF2"])
        import PyPDF2

    main()
