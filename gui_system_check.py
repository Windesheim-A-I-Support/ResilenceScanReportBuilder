"""
gui_system_check.py — stub (full implementation: Milestone 7)
Checks that R, Quarto, and TinyTeX are available on PATH.
"""

import shutil


class SystemChecker:
    """Verifies runtime dependencies are installed."""

    def check_all(self) -> dict:
        """
        Check R, Quarto, and TinyTeX availability.
        Returns a dict: {component: {"ok": bool, "version": str|None}}.
        Full implementation added in Milestone 7.
        """
        return {
            "python": {"ok": True, "version": None},
            "R": {
                "ok": bool(shutil.which("R") or shutil.which("Rscript")),
                "version": None,
            },
            "quarto": {"ok": bool(shutil.which("quarto")), "version": None},
            "tinytex": {"ok": bool(shutil.which("tlmgr")), "version": None},
        }
