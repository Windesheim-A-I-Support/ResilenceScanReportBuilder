"""
M11 — pipeline smoke tests using the anonymised sample fixture.

These tests use tests/fixtures/sample_anonymized.xlsx (committed, no real
data) to verify that the convert_data → clean_data pipeline works end-to-end
without requiring the live MasterDatabase.xlsx.
"""

import pathlib
import shutil
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "sample_anonymized.xlsx"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_SCORE_COLS = [
    "up__r1a",
    "up__r1b",
    "up__r1c",
    "up__r1",
    "up__r",
    "up__c",
    "up__f",
    "up__v",
    "up__a",
    "in__r",
    "in__c",
    "in__f",
    "in__v",
    "in__a",
    "do__r",
    "do__c",
    "do__f",
    "do__v",
    "do__a",
]
EXPECTED_META_COLS = [
    "submitdate",
    "reportsent",
    "name",
    "function",
    "company_name",
    "country",
    "email_address",
]


def test_fixture_exists():
    """The anonymised fixture must be present in the repo."""
    assert FIXTURE.exists(), f"Fixture not found: {FIXTURE}"


def test_convert_produces_csv(tmp_path, monkeypatch):
    """convert_and_save() on the fixture produces a valid cleaned_master.csv."""
    import convert_data

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "sample_anonymized.xlsx")

    monkeypatch.setattr(convert_data, "DATA_DIR", data_dir)
    monkeypatch.setattr(convert_data, "OUTPUT_PATH", data_dir / "cleaned_master.csv")

    assert convert_data.convert_and_save() is True

    out = data_dir / "cleaned_master.csv"
    assert out.exists(), "cleaned_master.csv not created"
    df = pd.read_csv(out)
    assert len(df) == 3, f"Expected 3 rows, got {len(df)}"

    for col in EXPECTED_META_COLS + EXPECTED_SCORE_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_respondent_names_anonymised(tmp_path, monkeypatch):
    """Sample data must contain only the fixture's fictional names."""
    import convert_data

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "sample_anonymized.xlsx")
    monkeypatch.setattr(convert_data, "DATA_DIR", data_dir)
    monkeypatch.setattr(convert_data, "OUTPUT_PATH", data_dir / "cleaned_master.csv")
    convert_data.convert_and_save()

    df = pd.read_csv(data_dir / "cleaned_master.csv")
    names = set(df["name"].tolist())
    expected = {"Alice Bennett", "Bob Hartley", "Carol Diaz"}
    assert names == expected, f"Unexpected names: {names}"


def test_scores_in_valid_range(tmp_path, monkeypatch):
    """All score columns in the converted CSV must be in the 0–5 range."""
    import convert_data

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "sample_anonymized.xlsx")
    monkeypatch.setattr(convert_data, "DATA_DIR", data_dir)
    monkeypatch.setattr(convert_data, "OUTPUT_PATH", data_dir / "cleaned_master.csv")
    convert_data.convert_and_save()

    df = pd.read_csv(data_dir / "cleaned_master.csv")
    score_cols = [c for c in df.columns if c.startswith(("up__", "in__", "do__"))]
    assert score_cols, "No score columns found"
    numeric = df[score_cols].apply(pd.to_numeric, errors="coerce")
    out_of_range = ((numeric < 0) | (numeric > 5)).any()
    bad = out_of_range[out_of_range].index.tolist()
    assert not bad, f"Scores out of 0–5 range in columns: {bad}"


def test_reportsent_defaults_false(tmp_path, monkeypatch):
    """reportsent must default to False for all rows in a fresh fixture."""
    import convert_data

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "sample_anonymized.xlsx")
    monkeypatch.setattr(convert_data, "DATA_DIR", data_dir)
    monkeypatch.setattr(convert_data, "OUTPUT_PATH", data_dir / "cleaned_master.csv")
    convert_data.convert_and_save()

    df = pd.read_csv(data_dir / "cleaned_master.csv")
    assert "reportsent" in df.columns
    # All should be False (not yet sent)
    assert not df["reportsent"].any(), "Expected all reportsent=False"


def test_clean_data_runs_on_fixture(tmp_path, monkeypatch):
    """clean_data.clean_csv() must complete without error on the fixture CSV."""
    import clean_data
    import convert_data

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE, data_dir / "sample_anonymized.xlsx")
    monkeypatch.setattr(convert_data, "DATA_DIR", data_dir)

    csv_path = data_dir / "cleaned_master.csv"
    monkeypatch.setattr(convert_data, "OUTPUT_PATH", csv_path)
    convert_data.convert_and_save()

    # Patch clean_data to use our tmp paths
    monkeypatch.setattr(clean_data, "DATA_DIR", data_dir)
    monkeypatch.setattr(clean_data, "INPUT_PATH", csv_path)

    # clean_data.clean_and_fix() should not raise
    try:
        clean_data.clean_and_fix()
    except Exception as exc:
        pytest.fail(f"clean_data.clean_and_fix() raised: {exc}")

    # CSV must still exist and have rows
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) >= 1
