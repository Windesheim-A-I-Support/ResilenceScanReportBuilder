"""
Tests for generate_all_reports.py without needing R/Quarto/TinyTeX.

Verifies that the command arguments are built correctly, filenames are safe,
and the pipeline behaviour is correct via mocking subprocess.run.
"""

import pathlib
import sys
import unittest.mock as mock

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import generate_all_reports as gar  # noqa: E402


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


class TestSafeFilename:
    def test_alphanumeric_passthrough(self):
        assert gar.safe_filename("AcmeCorp") == "AcmeCorp"

    def test_spaces_become_underscores(self):
        assert gar.safe_filename("Acme Corp") == "Acme_Corp"

    def test_slashes_become_underscores(self):
        result = gar.safe_filename("Org/Division")
        assert "/" not in result

    def test_nan_returns_unknown(self):
        assert gar.safe_filename(float("nan")) == "Unknown"

    def test_empty_returns_unknown(self):
        assert gar.safe_filename("") == "Unknown"


class TestSafeDisplayName:
    def test_simple_name_unchanged(self):
        assert gar.safe_display_name("Acme Logistics BV") == "Acme Logistics BV"

    def test_forward_slash_replaced(self):
        result = gar.safe_display_name("Org/Division")
        assert "/" not in result

    def test_backslash_replaced(self):
        result = gar.safe_display_name("Org\\Division")
        assert "\\" not in result

    def test_colon_replaced(self):
        result = gar.safe_display_name("Company: Premium")
        assert ":" not in result

    def test_illegal_chars_absent(self):
        """No Windows-illegal filename characters should survive."""
        illegal = set('/\\:*?"<>|')
        nasty = 'A/B\\C:D*E?F"G<H>I|J'
        result = gar.safe_display_name(nasty)
        assert not any(c in illegal for c in result)


# ---------------------------------------------------------------------------
# Quarto command structure
# ---------------------------------------------------------------------------


def _make_dummy_csv(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal cleaned_master.csv in tmp_path/data/.

    Column order matters: generate_all_reports uses substring matching
    ('name' in col_name), so 'name' must appear before 'company_name' in the
    iteration order, otherwise person_col gets matched to 'company_name'.
    This mirrors the actual column order produced by clean_data.py.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # 'name' MUST come before 'company_name' to avoid substring collision
    df = pd.DataFrame(
        {
            "submitdate": ["2024-01-01"],
            "reportsent": [False],
            "name": ["Alice Test"],
            "company_name": ["Acme Corp"],
        }
    )
    csv_path = data_dir / "cleaned_master.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def test_quarto_command_no_path_separators_in_output(tmp_path, monkeypatch):
    """
    The --output argument passed to quarto must be a bare filename with no
    path separators.  Quarto 1.6.x rejects paths with separators there.
    """
    csv_path = _make_dummy_csv(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    monkeypatch.setattr(gar, "DATA", csv_path)
    monkeypatch.setattr(gar, "OUTPUT_DIR", reports_dir)
    # Use a dummy QMD path (subprocess will be mocked)
    monkeypatch.setattr(gar, "TEMPLATE", ROOT / "ResilienceReport.qmd")

    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        # Simulate quarto writing the temp PDF
        cwd = kwargs.get("cwd", ROOT)
        temp_name = cmd[cmd.index("--output") + 1]
        (pathlib.Path(cwd) / temp_name).write_bytes(b"%PDF-1.4 fake")
        return mock.Mock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    gar.generate_reports()

    assert captured_cmds, "quarto was never called"
    for cmd in captured_cmds:
        assert "--output" in cmd
        output_idx = cmd.index("--output") + 1
        output_arg = cmd[output_idx]
        # Must be a bare filename — no path separator
        assert "/" not in output_arg, f"'/' in --output arg: {output_arg!r}"
        assert "\\" not in output_arg, f"'\\\\' in --output arg: {output_arg!r}"


def test_quarto_command_includes_company_and_person(tmp_path, monkeypatch):
    """
    The quarto render command must pass company and person as -P parameters.
    """
    csv_path = _make_dummy_csv(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    monkeypatch.setattr(gar, "DATA", csv_path)
    monkeypatch.setattr(gar, "OUTPUT_DIR", reports_dir)
    monkeypatch.setattr(gar, "TEMPLATE", ROOT / "ResilienceReport.qmd")

    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        cwd = kwargs.get("cwd", ROOT)
        temp_name = cmd[cmd.index("--output") + 1]
        (pathlib.Path(cwd) / temp_name).write_bytes(b"%PDF-1.4 fake")
        return mock.Mock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    gar.generate_reports()

    assert captured_cmds
    cmd = captured_cmds[0]
    joined = " ".join(cmd)
    assert "company=Acme Corp" in joined, f"company param missing in: {joined}"
    assert "person=Alice Test" in joined, f"person param missing in: {joined}"


def test_generate_reports_skips_existing(tmp_path, monkeypatch):
    """
    generate_reports() must skip PDFs that already exist in the output dir.
    """
    csv_path = _make_dummy_csv(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    monkeypatch.setattr(gar, "DATA", csv_path)
    monkeypatch.setattr(gar, "OUTPUT_DIR", reports_dir)
    monkeypatch.setattr(gar, "TEMPLATE", ROOT / "ResilienceReport.qmd")

    # Pre-create the output PDF so the file already exists
    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d")
    existing = (
        reports_dir / f"{date_str} ResilienceScanReport (Acme Corp - Alice Test).pdf"
    )
    existing.write_bytes(b"%PDF-1.4 existing")

    call_count = {"n": 0}

    def fake_run(cmd, **kwargs):
        call_count["n"] += 1
        return mock.Mock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    gar.generate_reports()

    assert call_count["n"] == 0, "quarto was called even though PDF already existed"
