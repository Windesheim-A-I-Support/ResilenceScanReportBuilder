"""
gui_system_check.py — verifies R, Quarto, and TinyTeX are available at runtime.

Called by the GUI at startup and via the System Check button.  Returns a
structured result so the GUI can display per-component pass/fail details.
"""

import shutil
import subprocess
import sys

# All R packages required by ResilienceReport.qmd
_R_PACKAGES = [
    "readr",
    "dplyr",
    "stringr",
    "tidyr",
    "ggplot2",
    "knitr",
    "fmsb",
    "scales",
    "viridis",
    "patchwork",
    "RColorBrewer",
    "gridExtra",
    "png",
    "lubridate",
    "kableExtra",
    "rmarkdown",
    "jsonlite",
    "ggrepel",
    "cowplot",
]


def _run(cmd: list) -> tuple:
    """Run a command and return (returncode, combined stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


class SystemChecker:
    """Verifies runtime dependencies (R, Quarto, TinyTeX, R packages).

    Usage::

        checker = SystemChecker()
        result = checker.check_all()   # dict: {component: {"ok": bool, "version": str|None}}
        # checker.checks, checker.errors, checker.warnings populated as side-effects
    """

    def __init__(self, root_dir=None) -> None:
        # root_dir accepted for GUI compatibility but not required
        self.checks: list = []  # [{"item": str, "status": str, "description": str}]
        self.errors: list = []  # critical failures
        self.warnings: list = []  # non-critical issues

    # ------------------------------------------------------------------ public

    def check_all(self) -> dict:
        """Run all checks.

        Returns a dict compatible with the smoke test::

            {"python": {"ok": bool, "version": str|None}, "R": ..., ...}

        Also populates ``self.checks``, ``self.errors``, ``self.warnings``
        for the GUI system-check report.
        """
        self.checks = []
        self.errors = []
        self.warnings = []

        result = {}
        result["python"] = self._check_python()
        result["R"] = self._check_r()
        result["quarto"] = self._check_quarto()
        result["tinytex"] = self._check_tinytex()
        result["r_packages"] = self._check_r_packages()
        return result

    # ----------------------------------------------------------------- private

    def _record(
        self,
        item: str,
        ok: bool,
        status: str,
        description: str = "",
        warning_only: bool = False,
    ) -> dict:
        """Append to self.checks and self.errors/warnings; return component dict."""
        self.checks.append({"item": item, "status": status, "description": description})
        if not ok:
            msg = f"{' '.join(item.split()[1:])}: {description or status}"
            if warning_only:
                self.warnings.append(msg)
            else:
                self.errors.append(msg)
        version = status if ok else None
        return {"ok": ok, "version": version}

    def _check_python(self) -> dict:
        ver = (
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )
        return self._record(
            "[OK] Python",
            ok=True,
            status=f"Python {ver}",
        )

    def _check_r(self) -> dict:
        rscript = shutil.which("Rscript") or shutil.which("R")
        if not rscript:
            return self._record(
                "[ERROR] R",
                ok=False,
                status="NOT FOUND",
                description="Rscript is not on PATH — R must be installed",
            )
        _, out = _run([rscript, "--version"])
        version = out.splitlines()[0] if out else "unknown"
        return self._record("[OK] R", ok=True, status=version)

    def _check_quarto(self) -> dict:
        if not shutil.which("quarto"):
            return self._record(
                "[ERROR] Quarto",
                ok=False,
                status="NOT FOUND",
                description="quarto is not on PATH — Quarto must be installed",
            )
        _, out = _run(["quarto", "--version"])
        version = out.strip() if out else "unknown"
        return self._record("[OK] Quarto", ok=True, status=f"Quarto {version}")

    def _check_tinytex(self) -> dict:
        if not shutil.which("tlmgr"):
            return self._record(
                "[ERROR] TinyTeX",
                ok=False,
                status="NOT FOUND",
                description="tlmgr is not on PATH — run: quarto install tinytex",
            )
        _, out = _run(["tlmgr", "--version"])
        version = out.splitlines()[0] if out else "unknown"
        return self._record("[OK] TinyTeX", ok=True, status=version)

    def _check_r_packages(self) -> dict:
        rscript = shutil.which("Rscript")
        if not rscript:
            self.checks.append(
                {
                    "item": "[SKIP] R packages",
                    "status": "SKIPPED — R not available",
                    "description": "",
                }
            )
            self.warnings.append("R packages not checked (R not available)")
            return {"ok": False, "version": None}

        pkg_list = ", ".join(f'"{p}"' for p in _R_PACKAGES)
        script = (
            f"pkgs <- c({pkg_list}); "
            "missing <- pkgs[!pkgs %in% rownames(installed.packages())]; "
            "if (length(missing) == 0) cat('OK') "
            "else cat('MISSING:', paste(missing, collapse=', '))"
        )
        _, out = _run([rscript, "-e", script])
        ok = out.strip() == "OK"
        if ok:
            return self._record(
                "[OK] R packages",
                ok=True,
                status=f"All {len(_R_PACKAGES)} required packages installed",
            )
        missing = out.replace("MISSING:", "").strip()
        return self._record(
            "[WARNING] R packages",
            ok=False,
            status="Missing packages",
            description=f"Missing: {missing}",
            warning_only=True,
        )
