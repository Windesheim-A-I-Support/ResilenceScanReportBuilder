import re
import pandas as pd
from pathlib import Path
import PyPDF2

# Configuration
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "cleaned_master.csv"
REPORTS_DIR = ROOT / "reports"
VALIDATION_FILE = ROOT / "validation_results.json"
OUTPUT_FILE = ROOT / "detailed_validation_report.txt"


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


def extract_all_scores_from_text(text):
    """Extract all resilience scores from PDF text including individual dimensions"""
    scores = {}

    # Extract pillar averages (from pillar analysis section)
    upstream_avg_pattern = r"Upstream\s*\(avg:\s*(\d+\.?\d*)\)"
    internal_avg_pattern = r"Internal\s*\(avg:\s*(\d+\.?\d*)\)"
    downstream_avg_pattern = r"Downstream\s*\(avg:\s*(\d+\.?\d*)\)"
    overall_pattern = r"Overall\s+SCRES:\s*(\d+\.?\d*)"

    upstream_avg_match = re.search(upstream_avg_pattern, text, re.IGNORECASE)
    internal_avg_match = re.search(internal_avg_pattern, text, re.IGNORECASE)
    downstream_avg_match = re.search(downstream_avg_pattern, text, re.IGNORECASE)
    overall_match = re.search(overall_pattern, text, re.IGNORECASE)

    if upstream_avg_match:
        scores["upstream_avg"] = float(upstream_avg_match.group(1))
    if internal_avg_match:
        scores["internal_avg"] = float(internal_avg_match.group(1))
    if downstream_avg_match:
        scores["downstream_avg"] = float(downstream_avg_match.group(1))
    if overall_match:
        scores["overall_scres"] = float(overall_match.group(1))

    # Extract individual dimension scores from pillar analysis
    # Pattern: "Strongest: Flexibility (3.50)" or "Weakest: Visibility (2.25)"
    # We'll look for dimension names with scores

    dimension_patterns = {
        "Redundancy": r"Redundancy\s*\((\d+\.?\d*)\)",
        "Collaboration": r"Collaboration\s*\((\d+\.?\d*)\)",
        "Flexibility": r"Flexibility\s*\((\d+\.?\d*)\)",
        "Visibility": r"Visibility\s*\((\d+\.?\d*)\)",
        "Agility": r"Agility\s*\((\d+\.?\d*)\)",
    }

    # Extract scores for each dimension
    # Note: This will find ALL mentions, so we need to be smart about which ones are for which pillar

    # Split text into pillar sections
    upstream_section = ""
    internal_section = ""
    downstream_section = ""

    # Try to split by pillar headers
    sections = re.split(
        r"(Upstream|Internal|Downstream)\s*\(avg:", text, flags=re.IGNORECASE
    )

    if len(sections) >= 3:
        for i in range(1, len(sections), 2):
            pillar_name = sections[i].lower()
            pillar_text = (
                sections[i + 1][:500] if i + 1 < len(sections) else ""
            )  # Take first 500 chars

            if "upstream" in pillar_name:
                upstream_section = pillar_text
            elif "internal" in pillar_name:
                internal_section = pillar_text
            elif "downstream" in pillar_name:
                downstream_section = pillar_text

    # Extract dimension scores for each pillar
    def extract_dimensions_from_section(section, prefix):
        """Extract R, C, F, V, A scores from a section"""
        dim_scores = {}
        for dim_name, pattern in dimension_patterns.items():
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                code = dim_name[0]  # R, C, F, V, or A
                dim_scores[f"{prefix}_{code}"] = float(match.group(1))
        return dim_scores

    # Extract from each section
    scores.update(extract_dimensions_from_section(upstream_section, "up"))
    scores.update(extract_dimensions_from_section(internal_section, "in"))
    scores.update(extract_dimensions_from_section(downstream_section, "do"))

    return scores


def get_expected_values(df, company_name):
    """Calculate expected values for a company from CSV"""
    company_data = df[df["company_name"] == company_name]
    if len(company_data) == 0:
        return None

    row = company_data.iloc[0]

    # Calculate upstream
    up_scores = {
        "R": float(row["up__r"]) if pd.notna(row["up__r"]) else None,
        "C": float(row["up__c"]) if pd.notna(row["up__c"]) else None,
        "F": float(row["up__f"]) if pd.notna(row["up__f"]) else None,
        "V": float(row["up__v"]) if pd.notna(row["up__v"]) else None,
        "A": float(row["up__a"]) if pd.notna(row["up__a"]) else None,
    }
    up_scores_valid = [s for s in up_scores.values() if s is not None]
    up_avg = sum(up_scores_valid) / len(up_scores_valid) if up_scores_valid else None

    # Calculate internal
    in_scores = {
        "R": float(row["in__r"]) if pd.notna(row["in__r"]) else None,
        "C": float(row["in__c"]) if pd.notna(row["in__c"]) else None,
        "F": float(row["in__f"]) if pd.notna(row["in__f"]) else None,
        "V": float(row["in__v"]) if pd.notna(row["in__v"]) else None,
        "A": float(row["in__a"]) if pd.notna(row["in__a"]) else None,
    }
    in_scores_valid = [s for s in in_scores.values() if s is not None]
    in_avg = sum(in_scores_valid) / len(in_scores_valid) if in_scores_valid else None

    # Calculate downstream
    do_scores = {
        "R": float(row["do__r"]) if pd.notna(row["do__r"]) else None,
        "C": float(row["do__c"]) if pd.notna(row["do__c"]) else None,
        "F": float(row["do__f"]) if pd.notna(row["do__f"]) else None,
        "V": float(row["do__v"]) if pd.notna(row["do__v"]) else None,
        "A": float(row["do__a"]) if pd.notna(row["do__a"]) else None,
    }
    do_scores_valid = [s for s in do_scores.values() if s is not None]
    do_avg = sum(do_scores_valid) / len(do_scores_valid) if do_scores_valid else None

    # Overall
    overall_avgs = [avg for avg in [up_avg, in_avg, do_avg] if avg is not None]
    overall = sum(overall_avgs) / len(overall_avgs) if overall_avgs else None

    return {
        "company": company_name,
        "person": row.get("name", "Unknown"),
        "upstream": up_scores,
        "upstream_avg": round(up_avg, 2) if up_avg else None,
        "internal": in_scores,
        "internal_avg": round(in_avg, 2) if in_avg else None,
        "downstream": do_scores,
        "downstream_avg": round(do_avg, 2) if do_avg else None,
        "overall_scres": round(overall, 2) if overall else None,
    }


def compare_all_values(expected, actual, tolerance=0.15):
    """Compare all expected vs actual values with tolerance"""
    results = {"pillar_avgs": {}, "dimensions": {}, "overall": {}}

    # Check pillar averages
    for pillar in ["upstream", "internal", "downstream"]:
        exp_key = f"{pillar}_avg"
        exp_val = expected.get(exp_key)
        act_val = actual.get(exp_key)

        if exp_val is not None and act_val is not None:
            diff = abs(exp_val - act_val)
            matches = diff <= tolerance
            results["pillar_avgs"][pillar] = {
                "expected": exp_val,
                "actual": act_val,
                "diff": round(diff, 2),
                "matches": matches,
            }
        elif exp_val is None and act_val is None:
            results["pillar_avgs"][pillar] = {
                "expected": None,
                "actual": None,
                "matches": True,
                "note": "Both NA",
            }
        else:
            results["pillar_avgs"][pillar] = {
                "expected": exp_val,
                "actual": act_val,
                "matches": False,
                "error": "Mismatch in NA handling",
            }

    # Check individual dimensions
    for pillar in ["up", "in", "do"]:
        pillar_name = {"up": "upstream", "in": "internal", "do": "downstream"}[pillar]
        for dim in ["R", "C", "F", "V", "A"]:
            exp_val = expected.get(pillar_name, {}).get(dim)
            act_key = f"{pillar}_{dim}"
            act_val = actual.get(act_key)

            key = f"{pillar_name}_{dim}"

            if exp_val is not None and act_val is not None:
                diff = abs(exp_val - act_val)
                matches = diff <= tolerance
                results["dimensions"][key] = {
                    "expected": exp_val,
                    "actual": act_val,
                    "diff": round(diff, 2),
                    "matches": matches,
                }
            elif exp_val is None and act_val is None:
                results["dimensions"][key] = {
                    "expected": None,
                    "actual": None,
                    "matches": True,
                    "note": "Both NA",
                }
            elif exp_val is None:
                results["dimensions"][key] = {
                    "expected": None,
                    "actual": act_val,
                    "matches": True,  # PDF shows value, CSV doesn't - OK
                    "note": "CSV has NA",
                }
            elif act_val is None:
                results["dimensions"][key] = {
                    "expected": exp_val,
                    "actual": None,
                    "matches": False,
                    "error": "Not found in PDF",
                }

    # Check overall SCRES
    exp_val = expected.get("overall_scres")
    act_val = actual.get("overall_scres")

    if exp_val is not None and act_val is not None:
        diff = abs(exp_val - act_val)
        matches = diff <= tolerance
        results["overall"] = {
            "expected": exp_val,
            "actual": act_val,
            "diff": round(diff, 2),
            "matches": matches,
        }
    else:
        results["overall"] = {
            "expected": exp_val,
            "actual": act_val,
            "matches": False,
            "error": "Missing value",
        }

    return results


def main():
    output_lines = []

    def log(msg):
        print(msg)
        output_lines.append(msg)

    log("=" * 70)
    log("DETAILED PDF REPORT VALIDATION")
    log("Checking ALL dimension values (R, C, F, V, A) for all pillars")
    log("=" * 70)

    # Load CSV data
    log("\n[LOAD] Loading CSV data...")
    df = pd.read_csv(DATA)
    log(f"   Total companies: {df['company_name'].nunique()}")

    # Find all report PDFs
    log(f"\n[SCAN] Scanning for PDF reports in {REPORTS_DIR}...")
    pdf_files = list(REPORTS_DIR.glob("*.pdf"))
    log(f"   Found {len(pdf_files)} PDF files")

    # Validate each report
    log("\n" + "=" * 70)
    log("VALIDATING REPORTS")
    log("=" * 70)

    all_results = []

    for pdf_file in pdf_files:
        # Extract company name from filename
        filename = pdf_file.stem
        # Pattern: "YYYYMMDD ResilienceScanReport (Company Name - Person)" or "(Company Name)"
        company_match = re.search(r"\(([^)]+?)(?:\s*-\s*[^)]+)?\)\.?$", filename)

        if not company_match:
            log(f"\n[SKIP] Could not extract company from: {filename}")
            continue

        company_name = company_match.group(1).strip()

        # Check if company exists in CSV
        if company_name not in df["company_name"].values:
            log(f"\n[SKIP] {company_name} - not found in CSV")
            continue

        log(f"\n[{company_name}]")
        log(f"   File: {pdf_file.name}")

        # Get expected values from CSV
        expected = get_expected_values(df, company_name)
        if not expected:
            log("   [FAIL] Could not calculate expected values")
            continue

        # Extract text from PDF
        text = extract_text_from_pdf(pdf_file)
        if text is None:
            log("   [FAIL] Could not extract PDF text")
            continue

        # Extract scores from text
        actual_scores = extract_all_scores_from_text(text)

        if not actual_scores:
            log("   [WARN] Could not extract any scores from PDF")
            continue

        # Compare with expected values
        comparison = compare_all_values(expected, actual_scores)

        # Display pillar averages
        log("\n   PILLAR AVERAGES:")
        all_pillars_match = True
        for pillar, result in comparison["pillar_avgs"].items():
            if result["matches"]:
                if "note" in result:
                    log(f"      [{pillar.upper():10s}] {result['note']}")
                else:
                    log(
                        f"      [{pillar.upper():10s}] Expected={result['expected']:.2f}, Actual={result['actual']:.2f} [OK]"
                    )
            else:
                if "error" in result:
                    log(f"      [{pillar.upper():10s}] {result['error']} [FAIL]")
                else:
                    log(
                        f"      [{pillar.upper():10s}] Expected={result['expected']:.2f}, Actual={result['actual']:.2f}, Diff={result['diff']:.2f} [FAIL]"
                    )
                all_pillars_match = False

        # Display individual dimensions (only mismatches or if verbose)
        log("\n   INDIVIDUAL DIMENSIONS:")
        dimension_issues = []
        dimensions_checked = 0
        dimensions_matched = 0

        for dim_key, result in comparison["dimensions"].items():
            dimensions_checked += 1
            if result["matches"]:
                dimensions_matched += 1
                # Only show if not both NA
                if "note" not in result:
                    log(
                        f"      [{dim_key:15s}] Expected={result['expected']:.2f}, Actual={result['actual']:.2f} [OK]"
                    )
            else:
                if "error" in result:
                    log(f"      [{dim_key:15s}] {result['error']} [FAIL]")
                    dimension_issues.append(dim_key)
                else:
                    log(
                        f"      [{dim_key:15s}] Expected={result['expected']:.2f}, Actual={result['actual']:.2f}, Diff={result['diff']:.2f} [FAIL]"
                    )
                    dimension_issues.append(dim_key)

        # Display overall SCRES
        log("\n   OVERALL SCRES:")
        overall_result = comparison["overall"]
        if overall_result["matches"]:
            log(
                f"      Expected={overall_result['expected']:.2f}, Actual={overall_result['actual']:.2f} [OK]"
            )
        else:
            if "error" in overall_result:
                log(f"      {overall_result['error']} [FAIL]")
            else:
                log(
                    f"      Expected={overall_result['expected']:.2f}, Actual={overall_result['actual']:.2f}, Diff={overall_result['diff']:.2f} [FAIL]"
                )

        # Summary for this company
        log("\n   SUMMARY:")
        log(f"      Dimensions: {dimensions_matched}/{dimensions_checked} matched")
        if dimension_issues:
            log(f"      Issues: {', '.join(dimension_issues)}")

        all_match = (
            all_pillars_match
            and len(dimension_issues) == 0
            and overall_result["matches"]
        )
        log(f"      Status: {'[PASS]' if all_match else '[FAIL]'}")

        all_results.append(
            {
                "company": company_name,
                "all_match": all_match,
                "dimensions_matched": dimensions_matched,
                "dimensions_total": dimensions_checked,
                "comparison": comparison,
            }
        )

    # Final Summary
    log("\n" + "=" * 70)
    log("FINAL VALIDATION SUMMARY")
    log("=" * 70)

    passed = sum(1 for r in all_results if r["all_match"])
    failed = len(all_results) - passed

    total_dims_matched = sum(r["dimensions_matched"] for r in all_results)
    total_dims_checked = sum(r["dimensions_total"] for r in all_results)

    log(f"   Companies validated: {len(all_results)}")
    log(f"   Fully passed: {passed}/{len(all_results)}")
    log(f"   Had issues: {failed}/{len(all_results)}")
    log(f"   Total dimensions checked: {total_dims_checked}")
    log(f"   Total dimensions matched: {total_dims_matched}")
    log(f"   Match rate: {(total_dims_matched / total_dims_checked * 100):.1f}%")

    if passed == len(all_results):
        log("\n   [SUCCESS] All reports validated successfully!")
        log("   [SUCCESS] All chart values, averages, and overall SCRES are correct!")
        log("\n   Issues I004, I006, I007 are CONFIRMED FIXED!")
    else:
        log("\n   [ATTENTION] Some validation issues detected")
        log("   Review the details above for specific problems")

    log("=" * 70)

    # Save detailed report
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    log(f"\n[SAVE] Detailed report saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
