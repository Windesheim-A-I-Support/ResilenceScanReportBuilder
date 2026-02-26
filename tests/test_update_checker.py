"""
Unit tests for update_checker.py.

Tests the semver parsing, version comparison logic, check_for_update() with
mocked network responses, and the background check thread callback mechanism.
No real network calls are made.
"""

import json
import sys
import threading
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import update_checker  # noqa: E402


# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    def test_simple_semver(self):
        assert update_checker._parse_version("1.2.3") == (1, 2, 3)

    def test_current_app_version_format(self):
        assert update_checker._parse_version("0.21.17") == (0, 21, 17)

    def test_strips_v_prefix(self):
        assert update_checker._parse_version("v1.2.3") == (1, 2, 3)

    def test_two_part_version(self):
        assert update_checker._parse_version("1.2") == (1, 2)

    def test_zero_version(self):
        assert update_checker._parse_version("0.0.0") == (0, 0, 0)

    def test_large_minor(self):
        assert update_checker._parse_version("0.100.0") == (0, 100, 0)

    def test_non_numeric_parts_become_zero(self):
        # "1.2.3alpha" → strip non-numeric → "1.2.3" → (1, 2, 3)
        result = update_checker._parse_version("1.2.3-alpha")
        # non-numeric parts after stripping become 0 or are ignored
        assert result[0] == 1
        assert result[1] == 2


# ---------------------------------------------------------------------------
# Version comparison (via _parse_version tuples)
# ---------------------------------------------------------------------------


class TestVersionComparison:
    def test_newer_patch_is_greater(self):
        assert update_checker._parse_version("1.2.4") > update_checker._parse_version(
            "1.2.3"
        )

    def test_newer_minor_is_greater(self):
        assert update_checker._parse_version("1.3.0") > update_checker._parse_version(
            "1.2.9"
        )

    def test_newer_major_is_greater(self):
        assert update_checker._parse_version("2.0.0") > update_checker._parse_version(
            "1.99.99"
        )

    def test_same_version_not_greater(self):
        assert not (
            update_checker._parse_version("1.2.3")
            > update_checker._parse_version("1.2.3")
        )

    def test_older_version_not_greater(self):
        assert not (
            update_checker._parse_version("1.2.2")
            > update_checker._parse_version("1.2.3")
        )

    def test_0_21_17_vs_0_21_16(self):
        """Realistic version comparison for this app."""
        assert update_checker._parse_version("0.21.17") > update_checker._parse_version(
            "0.21.16"
        )


# ---------------------------------------------------------------------------
# _current_version
# ---------------------------------------------------------------------------


def test_current_version_returns_semver():
    """_current_version() must return something matching X.Y.Z."""
    import re

    ver = update_checker._current_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", ver), (
        f"_current_version() returned {ver!r}, expected X.Y.Z format"
    )


def test_current_version_matches_pyproject():
    """_current_version() must return the version from pyproject.toml."""
    import tomllib

    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    expected = data["project"]["version"]
    assert update_checker._current_version() == expected


# ---------------------------------------------------------------------------
# check_for_update — mocked network
# ---------------------------------------------------------------------------


def _make_mock_response(tag_name: str, html_url: str) -> mock.Mock:
    """Build a fake urllib response that returns the given GitHub JSON payload."""
    payload = json.dumps({"tag_name": tag_name, "html_url": html_url}).encode("utf-8")
    ctx = mock.MagicMock()
    ctx.__enter__ = mock.Mock(return_value=ctx)
    ctx.__exit__ = mock.Mock(return_value=False)
    ctx.read.return_value = payload
    return ctx


def test_check_for_update_returns_none_when_already_latest(monkeypatch):
    """check_for_update() must return None when the latest release == current."""
    current = update_checker._current_version()

    def fake_urlopen(req, timeout=None):
        return _make_mock_response(
            f"v{current}", f"https://github.com/example/releases/tag/v{current}"
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = update_checker.check_for_update()
    assert result is None


def test_check_for_update_returns_none_when_older_release(monkeypatch):
    """check_for_update() returns None when the latest release is older than current."""

    def fake_urlopen(req, timeout=None):
        return _make_mock_response(
            "v0.1.0", "https://github.com/example/releases/tag/v0.1.0"
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = update_checker.check_for_update()
    assert result is None


def test_check_for_update_returns_dict_when_newer(monkeypatch):
    """check_for_update() returns {version, url} when a newer release exists."""

    def fake_urlopen(req, timeout=None):
        return _make_mock_response(
            "v99.99.99", "https://github.com/example/releases/tag/v99.99.99"
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = update_checker.check_for_update()
    assert result is not None
    assert result["version"] == "99.99.99"
    assert "url" in result
    assert result["url"].startswith("https://")


def test_check_for_update_returns_none_on_network_error(monkeypatch):
    """check_for_update() must return None if the network request fails."""

    def fake_urlopen(req, timeout=None):
        raise OSError("network unreachable")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = update_checker.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_bad_json(monkeypatch):
    """check_for_update() returns None if the response is invalid JSON."""
    ctx = mock.MagicMock()
    ctx.__enter__ = mock.Mock(return_value=ctx)
    ctx.__exit__ = mock.Mock(return_value=False)
    ctx.read.return_value = b"not json {{{{"
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: ctx)
    result = update_checker.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_missing_tag(monkeypatch):
    """check_for_update() returns None if tag_name is absent from the response."""
    payload = json.dumps({"html_url": "https://github.com/example"}).encode("utf-8")
    ctx = mock.MagicMock()
    ctx.__enter__ = mock.Mock(return_value=ctx)
    ctx.__exit__ = mock.Mock(return_value=False)
    ctx.read.return_value = payload
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: ctx)
    result = update_checker.check_for_update()
    assert result is None


# ---------------------------------------------------------------------------
# start_background_check
# ---------------------------------------------------------------------------


def test_start_background_check_calls_callback(monkeypatch):
    """start_background_check() must invoke the callback (no Tk root)."""
    collected = []
    event = threading.Event()

    def fake_check():
        return {"version": "99.0.0", "url": "https://example.com"}

    monkeypatch.setattr(update_checker, "check_for_update", fake_check)

    def callback(result):
        collected.append(result)
        event.set()

    update_checker.start_background_check(callback, tk_root=None)
    event.wait(timeout=3)
    assert collected, "callback was never invoked"
    assert collected[0] is not None
    assert collected[0]["version"] == "99.0.0"


def test_start_background_check_none_result(monkeypatch):
    """start_background_check() passes None to callback when no update found."""
    collected = []
    event = threading.Event()

    monkeypatch.setattr(update_checker, "check_for_update", lambda: None)

    def callback(result):
        collected.append(result)
        event.set()

    update_checker.start_background_check(callback, tk_root=None)
    event.wait(timeout=3)
    assert event.is_set(), "callback was never invoked"
    assert collected[0] is None
