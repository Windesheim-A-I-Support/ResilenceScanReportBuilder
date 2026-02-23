#!/usr/bin/env python3
"""
Validate a single PDF report against CSV data.
Used by GUI to validate reports immediately after generation.
"""

import re
import pandas as pd
import PyPDF2


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception:
        return None


def extract_scores_from_text(text):
    """Extract resilience scores from PDF text"""
    scores = {}

    # Try multiple patterns for different report formats

    # Pattern 1: "UP - Understanding & Planning" style (v2 template)
    # Use word boundaries to avoid matching partial words
    up_pattern = r"\bUP[:\s-]+.*?(\d+\.?\d*)"
    in_pattern = r"\bIN[:\s-]+.*?(\d+\.?\d*)"
    do_pattern = r"\bDO[:\s-]+.*?(\d+\.?\d*)"

    # Pattern 2: "Upstream (avg: 2.99)" style
    upstream_avg_pattern = r"Upstream\s*\(avg:\s*(\d+\.?\d*)\)"
    internal_avg_pattern = r"Internal\s*\(avg:\s*(\d+\.?\d*)\)"
    downstream_avg_pattern = r"Downstream\s*\(avg:\s*(\d+\.?\d*)\)"

    # Pattern 3: "Upstream Resilience (μ=3.5)" style (current template)
    upstream_mu_pattern = r"Upstream\s+Resilience[^\d]*[μµ]=\s*(\d+\.?\d*)"
    internal_mu_pattern = r"Internal\s+Resilience[^\d]*[μµ]=\s*(\d+\.?\d*)"
    downstream_mu_pattern = r"Downstream\s+Resilience[^\d]*[μµ]=\s*(\d+\.?\d*)"

    # Pattern 4: Overall SCRES
    overall_pattern = r"Overall\s+SCRES[:\s]*(\d+\.?\d*)"

    # Try v2 template patterns first
    up_match = re.search(up_pattern, text, re.IGNORECASE)
    in_match = re.search(in_pattern, text, re.IGNORECASE)
    do_match = re.search(do_pattern, text, re.IGNORECASE)

    # Try μ= patterns (current template)
    upstream_mu_match = re.search(upstream_mu_pattern, text, re.IGNORECASE)
    internal_mu_match = re.search(internal_mu_pattern, text, re.IGNORECASE)
    downstream_mu_match = re.search(downstream_mu_pattern, text, re.IGNORECASE)

    # Try avg: patterns
    upstream_match = re.search(upstream_avg_pattern, text, re.IGNORECASE)
    internal_match = re.search(internal_avg_pattern, text, re.IGNORECASE)
    downstream_match = re.search(downstream_avg_pattern, text, re.IGNORECASE)

    overall_match = re.search(overall_pattern, text, re.IGNORECASE)

    # Use whichever pattern matched (priority: UP > μ= > avg:)
    if up_match:
        scores["up_avg"] = float(up_match.group(1))
    elif upstream_mu_match:
        scores["up_avg"] = float(upstream_mu_match.group(1))
    elif upstream_match:
        scores["up_avg"] = float(upstream_match.group(1))

    if in_match:
        scores["in_avg"] = float(in_match.group(1))
    elif internal_mu_match:
        scores["in_avg"] = float(internal_mu_match.group(1))
    elif internal_match:
        scores["in_avg"] = float(internal_match.group(1))

    if do_match:
        scores["do_avg"] = float(do_match.group(1))
    elif downstream_mu_match:
        scores["do_avg"] = float(downstream_mu_match.group(1))
    elif downstream_match:
        scores["do_avg"] = float(downstream_match.group(1))

    if overall_match:
        scores["overall_scres"] = float(overall_match.group(1))

    return scores


def get_expected_values(csv_path, company_name, person_name=None):
    """Calculate expected values from CSV"""
    try:
        df = pd.read_csv(csv_path)

        # Filter by company
        company_data = df[df["company_name"] == company_name]
        if len(company_data) == 0:
            return None, "Company not found in CSV"

        # Filter by person if specified
        if person_name:
            person_data = company_data[company_data["name"] == person_name]
            if len(person_data) == 0:
                return (
                    None,
                    f"Person '{person_name}' not found for company '{company_name}'",
                )
            row = person_data.iloc[0]
        else:
            row = company_data.iloc[0]

        # Calculate pillar averages
        up_scores = [
            row["up__r"],
            row["up__c"],
            row["up__f"],
            row["up__v"],
            row["up__a"],
        ]
        up_scores_valid = [s for s in up_scores if pd.notna(s)]
        up_avg = (
            sum(up_scores_valid) / len(up_scores_valid) if up_scores_valid else None
        )

        in_scores = [
            row["in__r"],
            row["in__c"],
            row["in__f"],
            row["in__v"],
            row["in__a"],
        ]
        in_scores_valid = [s for s in in_scores if pd.notna(s)]
        in_avg = (
            sum(in_scores_valid) / len(in_scores_valid) if in_scores_valid else None
        )

        do_scores = [
            row["do__r"],
            row["do__c"],
            row["do__f"],
            row["do__v"],
            row["do__a"],
        ]
        do_scores_valid = [s for s in do_scores if pd.notna(s)]
        do_avg = (
            sum(do_scores_valid) / len(do_scores_valid) if do_scores_valid else None
        )

        # Overall
        overall_avgs = [avg for avg in [up_avg, in_avg, do_avg] if avg is not None]
        overall = sum(overall_avgs) / len(overall_avgs) if overall_avgs else None

        return {
            "up_avg": round(up_avg, 2) if up_avg else None,
            "in_avg": round(in_avg, 2) if in_avg else None,
            "do_avg": round(do_avg, 2) if do_avg else None,
            "overall_scres": round(overall, 2) if overall else None,
        }, None

    except Exception as e:
        return None, f"Error loading CSV: {e}"


def validate_report(pdf_path, csv_path, company_name, person_name=None, tolerance=0.15):
    """
    Validate a single PDF report against CSV data.

    Args:
        pdf_path: Path to PDF report
        csv_path: Path to cleaned CSV data
        company_name: Company name to validate
        person_name: Optional person name (for individual reports)
        tolerance: Acceptable difference between values (default 0.15)

    Returns:
        dict with validation results:
        {
            'success': bool,
            'message': str,
            'details': dict with comparison results
        }
    """
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    if text is None:
        return {
            "success": False,
            "message": "Could not extract text from PDF",
            "details": {},
        }

    # Extract scores from PDF
    actual_scores = extract_scores_from_text(text)
    if not actual_scores:
        return {
            "success": False,
            "message": "Could not extract scores from PDF text",
            "details": {},
        }

    # Get expected values from CSV
    expected, error = get_expected_values(csv_path, company_name, person_name)
    if expected is None:
        return {"success": False, "message": error, "details": {}}

    # Compare values
    details = {}
    all_match = True
    mismatches = []

    for key in ["up_avg", "in_avg", "do_avg", "overall_scres"]:
        exp_val = expected.get(key)
        act_val = actual_scores.get(key)

        label = key.replace("_", " ").replace("avg", "Average").title()

        if exp_val is not None and act_val is not None:
            diff = abs(exp_val - act_val)
            matches = diff <= tolerance

            details[key] = {
                "expected": exp_val,
                "actual": act_val,
                "diff": round(diff, 2),
                "matches": matches,
                "label": label,
            }

            if not matches:
                all_match = False
                mismatches.append(
                    f"{label}: Expected={exp_val:.2f}, Actual={act_val:.2f}, Diff={diff:.2f}"
                )
        elif exp_val is None and act_val is None:
            details[key] = {
                "expected": None,
                "actual": None,
                "matches": True,
                "label": label,
                "note": "Both values are N/A",
            }
        else:
            details[key] = {
                "expected": exp_val,
                "actual": act_val,
                "matches": False,
                "label": label,
            }
            all_match = False
            mismatches.append(f"{label}: Missing value")

    if all_match:
        message = "[OK] All values match CSV data"
    else:
        message = f"[WARNING] {len(mismatches)} mismatch(es) found: " + "; ".join(
            mismatches
        )

    return {"success": all_match, "message": message, "details": details}


def main():
    """Command line interface for testing"""
    import sys

    if len(sys.argv) < 4:
        print(
            "Usage: python validate_single_report.py <pdf_path> <csv_path> <company_name> [person_name]"
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    csv_path = sys.argv[2]
    company_name = sys.argv[3]
    person_name = sys.argv[4] if len(sys.argv) > 4 else None

    result = validate_report(pdf_path, csv_path, company_name, person_name)

    print("=" * 70)
    print("PDF REPORT VALIDATION")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Company: {company_name}")
    if person_name:
        print(f"Person: {person_name}")
    print(f"\nResult: {result['message']}")

    if result["details"]:
        print("\nDetails:")
        for key, info in result["details"].items():
            if info["matches"]:
                print(
                    f"  [{info['label']:20s}] Expected={info['expected']:.2f}, Actual={info['actual']:.2f} [OK]"
                )
            else:
                if "note" in info:
                    print(f"  [{info['label']:20s}] {info['note']}")
                else:
                    exp = (
                        f"{info['expected']:.2f}"
                        if info["expected"] is not None
                        else "N/A"
                    )
                    act = (
                        f"{info['actual']:.2f}" if info["actual"] is not None else "N/A"
                    )
                    diff = f"Diff={info['diff']:.2f}" if "diff" in info else ""
                    print(
                        f"  [{info['label']:20s}] Expected={exp}, Actual={act} {diff} [FAIL]"
                    )

    print("=" * 70)

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
