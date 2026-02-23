"""
dependency_manager.py — stub only.
All dependency installation is handled by the platform installer (Milestone 8).
This module exists solely so the GUI import does not fail.
"""


class DependencyManager:
    """
    Stub — installation of R, Quarto, and TinyTeX is performed by the
    NSIS installer (Windows) and post-install script (Linux).
    See Milestone 8 in CLAUDE.md.
    """

    def install_windows(self) -> None:
        """Not implemented — handled by NSIS installer."""

    def install_linux(self) -> None:
        """Not implemented — handled by .deb/.rpm post-install script."""
