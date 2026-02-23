"""Smoke tests for the ResilienceScan GUI and stub modules."""

import pathlib
import sys

import yaml

# Ensure repo root is on sys.path so stub modules are importable in tests
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_stub_modules_importable():
    """All stub modules should import without error."""
    import convert_data
    import dependency_manager
    import email_tracker
    import gui_system_check

    assert callable(convert_data.convert_and_save)
    assert hasattr(email_tracker, "EmailTracker")
    assert hasattr(gui_system_check, "SystemChecker")
    assert hasattr(dependency_manager, "DependencyManager")


def test_email_tracker_interface():
    """EmailTracker stub should implement the expected interface."""
    from email_tracker import EmailTracker

    tracker = EmailTracker()
    stats = tracker.get_statistics()
    assert stats == {"total": 0, "sent": 0, "pending": 0, "failed": 0}
    imported, skipped = tracker.import_from_csv("/nonexistent.csv")
    assert imported == 0
    assert skipped == 0


def test_system_checker_returns_dict():
    """SystemChecker.check_all() should return a dict with expected keys."""
    from gui_system_check import SystemChecker

    result = SystemChecker().check_all()
    for key in ("python", "R", "quarto", "tinytex"):
        assert key in result
        assert "ok" in result[key]


def test_import_main_module():
    """app.main should be importable without starting a GUI window."""
    import importlib

    mod = importlib.import_module("app.main")
    assert hasattr(mod, "ResilienceScanGUI")
    assert hasattr(mod, "main")


def test_nfpm_config_valid():
    """nfpm.yaml must exist and have required fields."""
    nfpm_path = ROOT / "nfpm.yaml"
    assert nfpm_path.exists(), "nfpm.yaml not found"

    config = yaml.safe_load(nfpm_path.read_text())
    assert "name" in config
    assert "contents" in config
    assert isinstance(config["contents"], list)
    assert len(config["contents"]) > 0


def test_desktop_file_exists():
    """Desktop template must exist with required keys."""
    desktop = ROOT / "packaging" / "template.desktop"
    assert desktop.exists(), "packaging/template.desktop not found"

    text = desktop.read_text()
    assert "[Desktop Entry]" in text
    assert "Name=" in text
    assert "Exec=" in text
    assert "Type=Application" in text
