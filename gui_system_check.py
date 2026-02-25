"""
gui_system_check.py — verifies R, Quarto, and TinyTeX are available at runtime.

Called by the GUI at startup and via the System Check button.  Returns a
structured result so the GUI can display per-component pass/fail details.
"""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# PATH helpers — the frozen app inherits PATH from the Windows Explorer process
# that was running at login, *before* the setup script updated the machine PATH.
# ---------------------------------------------------------------------------


def _refresh_windows_path() -> None:
    """Re-read machine + user PATH from the Windows registry and patch os.environ.

    The installer's setup script runs as SYSTEM *after* the user session has
    already started, so R and TinyTeX bin dirs added to the machine PATH are
    invisible to the running process.  Reading the registry directly picks them
    up without requiring a reboot or re-login.
    """
    if sys.platform != "win32":
        return
    try:
        import winreg  # noqa: PLC0415

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as k:
            machine_path, _ = winreg.QueryValueEx(k, "PATH")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                user_path, _ = winreg.QueryValueEx(k, "PATH")
        except OSError:
            user_path = ""
        # Registry values may contain unexpanded %vars%
        machine_path = os.path.expandvars(machine_path)
        user_path = os.path.expandvars(user_path)
        os.environ["PATH"] = machine_path + ";" + user_path
    except Exception:
        pass  # non-Windows or registry unavailable — leave PATH unchanged


def _find_rscript() -> str | None:
    """Find Rscript.exe via PATH, then well-known install locations."""
    exe = shutil.which("Rscript") or shutil.which("R")
    if exe:
        return exe
    if sys.platform == "win32":
        for pattern in [
            r"C:\Program Files\R\R-*\bin\Rscript.exe",
            r"C:\Program Files\R\R-*\bin\x64\Rscript.exe",
        ]:
            matches = sorted(glob.glob(pattern), reverse=True)  # newest first
            if matches:
                return matches[0]
    return None


def _find_quarto() -> str | None:
    """Find quarto via PATH, then well-known install location."""
    exe = shutil.which("quarto")
    if exe:
        return exe
    if sys.platform == "win32":
        fixed = r"C:\Program Files\Quarto\bin\quarto.exe"
        if os.path.exists(fixed):
            return fixed
    return None


def _find_tlmgr() -> str | None:
    """Find tlmgr via PATH, then well-known TinyTeX locations.

    TinyTeX is installed into the SYSTEM account's AppData when setup runs as
    SYSTEM, so we check that profile path explicitly alongside the current
    user's profile.

    On Windows, tlmgr is a .bat file.  shutil.which may miss it if PATHEXT
    is not inherited correctly in the frozen app, so we also try the explicit
    .bat extension and a set of hardcoded fallback paths.
    """
    # Try PATH first — explicit .bat extension in case PATHEXT is stripped
    exe = shutil.which("tlmgr") or shutil.which("tlmgr.bat")
    if exe:
        return exe
    if sys.platform == "win32":
        candidates = [
            # SYSTEM profile — where 'quarto install tinytex' lands when run as SYSTEM
            r"C:\Windows\System32\config\systemprofile\AppData\Local\TinyTeX\bin\windows\tlmgr.bat",
            r"C:\Windows\System32\config\systemprofile\AppData\Roaming\TinyTeX\bin\windows\tlmgr.bat",
            # Quarto may nest it under Programs\ in some versions
            r"C:\Windows\System32\config\systemprofile\AppData\Local\Programs\TinyTeX\bin\windows\tlmgr.bat",
            # Current user profiles (LOCALAPPDATA first — Quarto default)
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""), r"TinyTeX\bin\windows\tlmgr.bat"
            ),
            os.path.join(
                os.environ.get("APPDATA", ""), r"TinyTeX\bin\windows\tlmgr.bat"
            ),
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                r"Programs\TinyTeX\bin\windows\tlmgr.bat",
            ),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
    return None


def _r_lib_path() -> Path | None:
    """Return the bundled R library path when frozen (mirrors app/main.py logic)."""
    if getattr(sys, "frozen", False):
        lib = Path(sys.executable).parent / "r-library"
        if lib.exists():
            return lib
    return None


# ---------------------------------------------------------------------------
# Internal runner
# ---------------------------------------------------------------------------


def _run(cmd: list, env: dict | None = None) -> tuple:
    """Run a command and return (returncode, combined stdout+stderr)."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
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
        # Refresh PATH from the Windows registry so that tools installed by
        # the setup script (which runs after user login) are discoverable.
        _refresh_windows_path()

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
        rscript = _find_rscript()
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
        quarto = _find_quarto()
        if not quarto:
            return self._record(
                "[ERROR] Quarto",
                ok=False,
                status="NOT FOUND",
                description="quarto is not on PATH — Quarto must be installed",
            )
        _, out = _run([quarto, "--version"])
        version = out.strip() if out else "unknown"
        return self._record("[OK] Quarto", ok=True, status=f"Quarto {version}")

    def _check_tinytex(self) -> dict:
        tlmgr = _find_tlmgr()
        if not tlmgr:
            return self._record(
                "[ERROR] TinyTeX",
                ok=False,
                status="NOT FOUND",
                description="tlmgr is not on PATH — run: quarto install tinytex",
            )
        # .bat files on Windows need cmd /c to execute correctly via subprocess
        if sys.platform == "win32" and tlmgr.lower().endswith(".bat"):
            cmd = ["cmd", "/c", tlmgr, "--version"]
        else:
            cmd = [tlmgr, "--version"]
        _, out = _run(cmd)
        version = out.splitlines()[0] if out else "unknown"
        return self._record("[OK] TinyTeX", ok=True, status=version)

    def _check_r_packages(self) -> dict:
        rscript = _find_rscript()
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
            "missing <- pkgs[!pkgs %in% rownames(installed.packages())];"
            "if (length(missing) == 0) cat('OK') "
            "else cat('MISSING:', paste(missing, collapse=', '))"
        )

        # Pass the bundled R library path (installed by the setup script) so
        # installed.packages() finds packages even if R_LIBS is not set.
        run_env = None
        r_lib = _r_lib_path()
        if r_lib:
            run_env = os.environ.copy()
            existing = run_env.get("R_LIBS", "")
            run_env["R_LIBS"] = f"{r_lib};{existing}" if existing else str(r_lib)

        _, out = _run([rscript, "-e", script], env=run_env)
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
