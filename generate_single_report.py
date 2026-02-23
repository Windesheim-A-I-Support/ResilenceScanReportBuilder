import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "ResilienceReport.qmd"
OUTPUT_DIR = ROOT / "reports"


def generate_single_report(company_name, person_name=""):
    """Generate a single PDF report for specified company"""

    print("=" * 70)
    print("[TEST] SINGLE REPORT GENERATOR")
    print("=" * 70)
    print(f"\nCompany: {company_name}")
    if person_name:
        print(f"Person: {person_name}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get current date for filename
    date_str = datetime.now().strftime("%Y%m%d")

    # Create safe display name
    def safe_display_name(name):
        if not name:
            return "Unknown"
        name_str = str(name).strip()
        name_str = name_str.replace("/", "-").replace("\\", "-").replace(":", "-")
        name_str = name_str.replace("*", "").replace("?", "").replace('"', "'")
        name_str = name_str.replace("<", "(").replace(">", ")").replace("|", "-")
        return name_str

    display_company = safe_display_name(company_name)
    display_person = safe_display_name(person_name) if person_name else "Report"

    # Output filename
    output_filename = (
        f"{date_str} ResilienceScanReport ({display_company} - {display_person}).pdf"
    )
    output_file = OUTPUT_DIR / output_filename

    print(f"\n[FILE] Output: {output_filename}")

    # Build quarto command
    temp_output = f"temp_{display_company}.pdf"
    cmd = [
        "quarto",
        "render",
        str(TEMPLATE),
        "-P",
        f"company={company_name}",
        "--to",
        "pdf",
        "--output",
        temp_output,
    ]

    # Note: person name is extracted from CSV automatically by the template

    print("\n[RENDER] Running Quarto...")
    print(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout
        )

        if result.returncode == 0:
            if Path(temp_output).exists():
                # Move to final location
                import shutil

                shutil.move(temp_output, output_file)
                print("\n[OK] SUCCESS!")
                print(f"[OK] Report saved: {output_file}")
                print(f"[OK] File size: {output_file.stat().st_size // 1024} KB")
                return True
            else:
                print("\n[ERROR] Output file not found after successful render")
                print(f"stdout: {result.stdout[-500:]}" if result.stdout else "")
                print(f"stderr: {result.stderr[-500:]}" if result.stderr else "")
                return False
        else:
            print(f"\n[ERROR] Quarto render failed (exit code: {result.returncode})")
            print("\nError output:")
            if result.stderr:
                print(result.stderr[-1000:])
            if result.stdout:
                print("\nStdout:")
                print(result.stdout[-1000:])
            return False

    except subprocess.TimeoutExpired:
        print("\n[ERROR] Timeout after 180 seconds")
        return False
    except Exception as e:
        print(f"\n[ERROR] Exception: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    import sys

    # Check for command line arguments
    if len(sys.argv) > 1:
        company_name = sys.argv[1]
        person_name = sys.argv[2] if len(sys.argv) > 2 else ""
    else:
        # Default: Generate report for Suplacon
        company_name = "Suplacon"
        person_name = "Pim Jansen"

    success = generate_single_report(company_name, person_name)

    print("\n" + "=" * 70)
    if success:
        print("[DONE] Report generation completed successfully")
    else:
        print("[FAILED] Report generation failed")
    print("=" * 70)

    exit(0 if success else 1)
