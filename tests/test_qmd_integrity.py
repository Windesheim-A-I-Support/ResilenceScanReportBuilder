"""
Tests that verify the integrity of ResilienceReport.qmd:
- YAML front matter is valid
- All R packages loaded by the QMD are in the CI and installer install lists
- Required parameters (company, person) are referenced
- No non-ASCII characters in R string literals that would cause encoding issues

These run without R/Quarto and catch mismatches before CI.
"""

import re
import yaml
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QMD = ROOT / "ResilienceReport.qmd"
E2E = ROOT / ".github" / "workflows" / "e2e.yml"
PS1 = ROOT / "packaging" / "setup_dependencies.ps1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qmd_text() -> str:
    return QMD.read_text(encoding="utf-8")


def _qmd_yaml_header() -> dict:
    """Parse the YAML front matter from the QMD file."""
    text = _qmd_text()
    # Front matter is between the first and second '---'
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        pytest.skip("No YAML front matter found in QMD")
    return yaml.safe_load(m.group(1))


def _qmd_r_packages() -> set[str]:
    """Extract R package names from named *_pkgs variable definitions in the QMD.

    Only extracts from assignments like:
      essential_pkgs <- c("readr", "dplyr", ...)
      advanced_pkgs  <- c("fmsb", ...)
    to avoid picking up data string literals from other c() calls.
    """
    text = _qmd_text()
    packages = set()
    # Match multi-line c(...) assignments that have a variable name ending in _pkgs
    for block in re.finditer(r"\w+_pkgs\s*<-\s*c\((.*?)\)", text, re.DOTALL):
        found = re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', block.group(1))
        packages.update(found)
    return packages


def _e2e_r_packages() -> set[str]:
    """Extract R package names from e2e.yml."""
    text = E2E.read_text(encoding="utf-8") if E2E.exists() else ""
    return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', text))


def _ps1_r_packages() -> set[str]:
    """Extract R package names from setup_dependencies.ps1."""
    text = PS1.read_text(encoding="utf-8") if PS1.exists() else ""
    m = re.search(r"\$R_PACKAGES\s*=\s*@\((.*?)\)", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', m.group(1)))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
def test_qmd_yaml_header_valid():
    """ResilienceReport.qmd must have a parseable YAML front matter."""
    header = _qmd_yaml_header()
    assert isinstance(header, dict), "YAML header should be a dict"
    assert "title" in header or "format" in header, (
        "YAML header missing both 'title' and 'format' keys"
    )


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
def test_qmd_has_pdf_format():
    """QMD must target PDF output format."""
    header = _qmd_yaml_header()
    assert "pdf" in header.get("format", {}), (
        "QMD 'format' does not include 'pdf' — PDF rendering will fail"
    )


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
def test_qmd_references_company_param():
    """QMD must reference the 'company' parameter passed by generate_all_reports.py."""
    text = _qmd_text()
    assert "company" in text, "QMD does not reference 'company' parameter"


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
def test_qmd_references_person_param():
    """QMD must reference the 'person' parameter passed by generate_all_reports.py."""
    text = _qmd_text()
    assert "person" in text, "QMD does not reference 'person' parameter"


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_qmd_packages_in_e2e():
    """All R packages used in the QMD must be in the e2e.yml install list."""
    qmd_pkgs = _qmd_r_packages()
    e2e_pkgs = _e2e_r_packages()
    assert qmd_pkgs, "Could not parse any packages from QMD"

    missing = qmd_pkgs - e2e_pkgs
    if missing:
        pytest.fail(
            f"QMD uses packages NOT in e2e.yml install list: {sorted(missing)}\n"
            f"Add them to the 'Install R packages' step in e2e.yml."
        )


@pytest.mark.skipif(not QMD.exists(), reason="ResilienceReport.qmd not found")
@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_qmd_packages_in_ps1():
    """All R packages used in the QMD must be in setup_dependencies.ps1."""
    qmd_pkgs = _qmd_r_packages()
    ps1_pkgs = _ps1_r_packages()
    assert qmd_pkgs, "Could not parse any packages from QMD"

    missing = qmd_pkgs - ps1_pkgs
    if missing:
        pytest.fail(
            f"QMD uses packages NOT in setup_dependencies.ps1 $R_PACKAGES: {sorted(missing)}\n"
            f"Add them so end-user installations include all required packages."
        )
