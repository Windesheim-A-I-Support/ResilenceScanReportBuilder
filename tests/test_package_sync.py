"""
Tests that R package and LaTeX package lists are consistent across files.

The same packages must appear in both the e2e.yml CI workflow (which tests
the pipeline) and in setup_dependencies.ps1 (which installs them for end
users).  Drift between these two lists means CI tests a different environment
than users get.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
E2E = ROOT / ".github" / "workflows" / "e2e.yml"
PS1 = ROOT / "packaging" / "setup_dependencies.ps1"


# ---------------------------------------------------------------------------
# Helpers to extract package lists from each file
# ---------------------------------------------------------------------------


def _e2e_r_packages() -> set[str]:
    """Extract R package names from the Rscript install.packages() call in e2e.yml."""
    data = yaml.safe_load(E2E.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    for job in jobs.values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "install.packages" in run and "shell" in step:
                # Extract quoted names from c("readr", "dplyr", ...)
                return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', run))
    return set()


def _e2e_latex_packages() -> set[str]:
    """Extract LaTeX package names from the tlmgr install line in e2e.yml."""
    text = E2E.read_text(encoding="utf-8")
    # Match the block: '"$TLMGR" install \' ... until next blank line or non-pkg line
    m = re.search(
        r'"\$TLMGR"\s+install\s+\\(.*?)(?=\n\s*\n|\n\s*#|\n\s*TEXMF)',
        text,
        re.DOTALL,
    )
    if not m:
        return set()
    block = m.group(1)
    # Extract word tokens (package names are simple alphanumeric with hyphens)
    return set(re.findall(r"\b([a-z][a-z0-9\-]+)\b", block))


def _ps1_r_packages() -> set[str]:
    """Extract R package names from $R_PACKAGES array in setup_dependencies.ps1."""
    text = PS1.read_text(encoding="utf-8")
    m = re.search(r"\$R_PACKAGES\s*=\s*@\((.*?)\)", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', m.group(1)))


def _ps1_latex_packages() -> set[str]:
    """Extract LaTeX package names from $LATEX_PACKAGES array in setup_dependencies.ps1."""
    text = PS1.read_text(encoding="utf-8")
    m = re.search(r"\$LATEX_PACKAGES\s*=\s*@\((.*?)\)", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([a-z][a-z0-9\-]+)"', m.group(1)))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_r_packages_in_sync():
    """R packages in e2e.yml and setup_dependencies.ps1 must match exactly."""
    e2e = _e2e_r_packages()
    ps1 = _ps1_r_packages()
    assert e2e, "Could not parse R packages from e2e.yml"
    assert ps1, "Could not parse R packages from setup_dependencies.ps1"

    only_e2e = e2e - ps1
    only_ps1 = ps1 - e2e

    errors = []
    if only_e2e:
        errors.append(
            f"In e2e.yml but NOT in setup_dependencies.ps1: {sorted(only_e2e)}"
        )
    if only_ps1:
        errors.append(
            f"In setup_dependencies.ps1 but NOT in e2e.yml: {sorted(only_ps1)}"
        )

    if errors:
        pytest.fail(
            "R package lists are out of sync between e2e.yml and setup_dependencies.ps1:\n"
            + "\n".join(errors)
        )


@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_latex_packages_in_sync():
    """LaTeX packages in e2e.yml and setup_dependencies.ps1 must match exactly."""
    e2e = _e2e_latex_packages()
    ps1 = _ps1_latex_packages()
    assert e2e, "Could not parse LaTeX packages from e2e.yml"
    assert ps1, "Could not parse LaTeX packages from setup_dependencies.ps1"

    only_e2e = e2e - ps1
    only_ps1 = ps1 - e2e

    errors = []
    if only_e2e:
        errors.append(
            f"In e2e.yml but NOT in setup_dependencies.ps1: {sorted(only_e2e)}"
        )
    if only_ps1:
        errors.append(
            f"In setup_dependencies.ps1 but NOT in e2e.yml: {sorted(only_ps1)}"
        )

    if errors:
        pytest.fail(
            "LaTeX package lists are out of sync between e2e.yml and setup_dependencies.ps1:\n"
            + "\n".join(errors)
        )


@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_e2e_r_packages_not_empty():
    """e2e.yml must define at least 15 R packages (sanity check on parser)."""
    pkgs = _e2e_r_packages()
    assert len(pkgs) >= 15, f"Only {len(pkgs)} R packages parsed from e2e.yml: {pkgs}"


@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_ps1_r_packages_not_empty():
    """setup_dependencies.ps1 must define at least 15 R packages (sanity check on parser)."""
    pkgs = _ps1_r_packages()
    assert len(pkgs) >= 15, f"Only {len(pkgs)} R packages parsed from ps1: {pkgs}"


@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_e2e_latex_packages_not_empty():
    """e2e.yml must define at least 10 LaTeX packages (sanity check on parser)."""
    pkgs = _e2e_latex_packages()
    assert len(pkgs) >= 10, (
        f"Only {len(pkgs)} LaTeX packages parsed from e2e.yml: {pkgs}"
    )


@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_ps1_latex_packages_not_empty():
    """setup_dependencies.ps1 must define at least 10 LaTeX packages (sanity check on parser)."""
    pkgs = _ps1_latex_packages()
    assert len(pkgs) >= 10, f"Only {len(pkgs)} LaTeX packages parsed from ps1: {pkgs}"
