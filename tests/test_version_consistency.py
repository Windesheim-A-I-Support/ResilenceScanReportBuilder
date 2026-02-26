"""
Tests that pinned dependency versions and package lists stay in sync across all
installer/CI files.

Drift between these files means the end-user installer and the CI test
environment use different versions, making CI results unreliable.

Covers:
- Quarto version: setup_linux.sh, setup_dependencies.ps1, e2e.yml
- setup_linux.sh: ASCII-only, references R/Quarto/TinyTeX
- setup_linux.sh R package list vs e2e.yml and setup_dependencies.ps1
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINUX_SH = ROOT / "packaging" / "setup_linux.sh"
PS1 = ROOT / "packaging" / "setup_dependencies.ps1"
E2E = ROOT / ".github" / "workflows" / "e2e.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quarto_version_linux_sh() -> str:
    """Extract QUARTO_VERSION from setup_linux.sh."""
    text = LINUX_SH.read_text(encoding="utf-8")
    m = re.search(r'QUARTO_VERSION="([^"]+)"', text)
    return m.group(1) if m else ""


def _quarto_version_ps1() -> str:
    """Extract $QUARTO_VERSION from setup_dependencies.ps1."""
    text = PS1.read_text(encoding="utf-8")
    m = re.search(r'\$QUARTO_VERSION\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def _quarto_version_e2e() -> str:
    """Extract Quarto version from quarto_url in e2e.yml."""
    text = E2E.read_text(encoding="utf-8")
    # Matches e.g. quarto-cli/releases/download/v1.6.39/quarto-1.6.39-linux
    m = re.search(r"quarto-cli/releases/download/v([0-9]+\.[0-9]+\.[0-9]+)/", text)
    return m.group(1) if m else ""


def _linux_sh_r_packages() -> set[str]:
    """Extract R package names from setup_linux.sh R_PKGS variable."""
    text = LINUX_SH.read_text(encoding="utf-8")
    m = re.search(r"R_PKGS=\"(.*?)\"", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r"'([A-Za-z][A-Za-z0-9.]+)'", m.group(1)))


def _e2e_r_packages() -> set[str]:
    """Extract R package names from the install.packages() call in e2e.yml."""
    import yaml

    data = yaml.safe_load(E2E.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    for job in jobs.values():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "install.packages" in run and "shell" in step:
                return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', run))
    return set()


def _ps1_r_packages() -> set[str]:
    """Extract R package names from $R_PACKAGES array in setup_dependencies.ps1."""
    text = PS1.read_text(encoding="utf-8")
    m = re.search(r"\$R_PACKAGES\s*=\s*@\((.*?)\)", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([A-Za-z][A-Za-z0-9.]+)"', m.group(1)))


# ---------------------------------------------------------------------------
# Quarto version sync
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_quarto_version_linux_sh_matches_ps1():
    """Quarto version in setup_linux.sh must match setup_dependencies.ps1."""
    linux_ver = _quarto_version_linux_sh()
    ps1_ver = _quarto_version_ps1()
    assert linux_ver, "Could not parse QUARTO_VERSION from setup_linux.sh"
    assert ps1_ver, "Could not parse $QUARTO_VERSION from setup_dependencies.ps1"
    assert linux_ver == ps1_ver, (
        f"Quarto version mismatch: setup_linux.sh={linux_ver!r}, "
        f"setup_dependencies.ps1={ps1_ver!r}"
    )


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_quarto_version_linux_sh_matches_e2e():
    """Quarto version in setup_linux.sh must match the quarto_url in e2e.yml."""
    linux_ver = _quarto_version_linux_sh()
    e2e_ver = _quarto_version_e2e()
    assert linux_ver, "Could not parse QUARTO_VERSION from setup_linux.sh"
    assert e2e_ver, "Could not parse Quarto version from e2e.yml quarto_url"
    assert linux_ver == e2e_ver, (
        f"Quarto version mismatch: setup_linux.sh={linux_ver!r}, "
        f"e2e.yml quarto_url={e2e_ver!r}"
    )


@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_quarto_version_ps1_matches_e2e():
    """Quarto version in setup_dependencies.ps1 must match e2e.yml."""
    ps1_ver = _quarto_version_ps1()
    e2e_ver = _quarto_version_e2e()
    assert ps1_ver, "Could not parse $QUARTO_VERSION from setup_dependencies.ps1"
    assert e2e_ver, "Could not parse Quarto version from e2e.yml quarto_url"
    assert ps1_ver == e2e_ver, (
        f"Quarto version mismatch: setup_dependencies.ps1={ps1_ver!r}, "
        f"e2e.yml quarto_url={e2e_ver!r}"
    )


# ---------------------------------------------------------------------------
# setup_linux.sh safety
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
def test_setup_linux_sh_ascii_only():
    """setup_linux.sh must contain only ASCII characters.

    Non-ASCII chars in a shell script can cause encoding issues on systems
    with non-UTF-8 locales or when the file is embedded in a .deb package.
    """
    text = LINUX_SH.read_text(encoding="utf-8")
    non_ascii = [(i, ch) for i, ch in enumerate(text) if ord(ch) > 127]
    if non_ascii:
        samples = non_ascii[:5]
        detail = ", ".join(f"offset {i} U+{ord(ch):04X} ({ch!r})" for i, ch in samples)
        pytest.fail(
            f"setup_linux.sh contains {len(non_ascii)} non-ASCII char(s): {detail}"
        )


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
def test_setup_linux_sh_references_r():
    """setup_linux.sh must reference R installation."""
    text = LINUX_SH.read_text(encoding="utf-8")
    assert "r-base" in text.lower() or "rscript" in text.lower(), (
        "setup_linux.sh does not reference R (r-base or Rscript)"
    )


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
def test_setup_linux_sh_references_quarto():
    """setup_linux.sh must reference Quarto."""
    text = LINUX_SH.read_text(encoding="utf-8")
    assert "quarto" in text.lower(), "setup_linux.sh does not mention quarto"


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
def test_setup_linux_sh_references_tinytex():
    """setup_linux.sh must reference TinyTeX."""
    text = LINUX_SH.read_text(encoding="utf-8")
    assert "tinytex" in text.lower(), "setup_linux.sh does not mention tinytex"


# ---------------------------------------------------------------------------
# Linux installer R package sync
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
@pytest.mark.skipif(not E2E.exists(), reason="e2e.yml not found")
def test_linux_sh_r_packages_match_e2e():
    """R packages in setup_linux.sh must match the e2e.yml install list."""
    linux_pkgs = _linux_sh_r_packages()
    e2e_pkgs = _e2e_r_packages()
    assert linux_pkgs, "Could not parse R packages from setup_linux.sh"
    assert e2e_pkgs, "Could not parse R packages from e2e.yml"

    only_linux = linux_pkgs - e2e_pkgs
    only_e2e = e2e_pkgs - linux_pkgs

    errors = []
    if only_linux:
        errors.append(f"In setup_linux.sh but NOT in e2e.yml: {sorted(only_linux)}")
    if only_e2e:
        errors.append(f"In e2e.yml but NOT in setup_linux.sh: {sorted(only_e2e)}")

    if errors:
        pytest.fail(
            "R package lists are out of sync between setup_linux.sh and e2e.yml:\n"
            + "\n".join(errors)
        )


@pytest.mark.skipif(not LINUX_SH.exists(), reason="setup_linux.sh not found")
@pytest.mark.skipif(not PS1.exists(), reason="setup_dependencies.ps1 not found")
def test_linux_sh_r_packages_match_ps1():
    """R packages in setup_linux.sh must match setup_dependencies.ps1."""
    linux_pkgs = _linux_sh_r_packages()
    ps1_pkgs = _ps1_r_packages()
    assert linux_pkgs, "Could not parse R packages from setup_linux.sh"
    assert ps1_pkgs, "Could not parse R packages from setup_dependencies.ps1"

    only_linux = linux_pkgs - ps1_pkgs
    only_ps1 = ps1_pkgs - linux_pkgs

    errors = []
    if only_linux:
        errors.append(
            f"In setup_linux.sh but NOT in setup_dependencies.ps1: {sorted(only_linux)}"
        )
    if only_ps1:
        errors.append(
            f"In setup_dependencies.ps1 but NOT in setup_linux.sh: {sorted(only_ps1)}"
        )

    if errors:
        pytest.fail(
            "R package lists are out of sync between setup_linux.sh and "
            "setup_dependencies.ps1:\n" + "\n".join(errors)
        )
