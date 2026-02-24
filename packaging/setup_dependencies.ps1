<#
.SYNOPSIS
    Silently installs R, Quarto, TinyTeX and required R/LaTeX packages.
    Runs as SYSTEM via Task Scheduler — no UAC prompts, no execution-policy blocks.
    Progress is logged to C:\ProgramData\ResilienceScan\setup.log

.PARAMETER InstallDir
    Installation directory (default: directory containing this script).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

# PS 5.1 compatible — do NOT use ?. null-conditional operator (PS 7+ only).
$ProgressPreference = "SilentlyContinue"   # suppress slow progress bars

$R_VERSION      = "4.3.2"
$QUARTO_VERSION = "1.6.39"
$R_LIB          = "$InstallDir\r-library"
$TMP            = "C:\Windows\Temp"        # reliable under SYSTEM account
$LOG_FILE       = "C:\ProgramData\ResilienceScan\setup.log"

$R_PACKAGES = @(
    "readr", "dplyr", "stringr", "tidyr", "ggplot2", "knitr",
    "fmsb", "scales", "viridis", "patchwork", "RColorBrewer",
    "gridExtra", "png", "lubridate", "kableExtra", "rmarkdown",
    "jsonlite", "ggrepel", "cowplot"
)

# LaTeX packages required by ResilienceReport.qmd + kableExtra dependencies
$LATEX_PACKAGES = @(
    "pgf", "xcolor", "colortbl", "booktabs", "longtable", "multirow",
    "float", "wrapfig", "pdflscape", "geometry", "afterpage", "graphicx",
    "array", "tabu", "threeparttable", "threeparttablex", "ulem", "makecell",
    "tikz", "environ", "trimspaces", "capt-of", "caption", "hyperref",
    "setspace", "fancyhdr", "microtype", "lm", "needspace", "varwidth",
    "mdwtools", "xstring", "tools"
)

# ── Logging ──────────────────────────────────────────────────────────────────
function Write-Log {
    param($msg)
    $line = "[SETUP $(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

Write-Log "=== ResilienceScan dependency setup started (running as SYSTEM) ==="
Write-Log "InstallDir : $InstallDir"
Write-Log "R_LIB      : $R_LIB"

# ── Helper: find Rscript.exe (PS 5.1 compatible — no ?. operator) ─────────────
function Find-Rscript {
    $cmd = Get-Command Rscript -ErrorAction SilentlyContinue
    $fromPath = if ($cmd) { $cmd.Source } else { $null }
    $candidates = @(
        $fromPath,
        "C:\Program Files\R\R-$R_VERSION\bin\Rscript.exe",
        "C:\Program Files\R\R-$R_VERSION\bin\x64\Rscript.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    # Fall back to any installed R version
    $found = Get-ChildItem "C:\Program Files\R" -Filter "Rscript.exe" -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty FullName
    return $found
}

function Refresh-Path {
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
}

# ── R ────────────────────────────────────────────────────────────────────────
if (-not (Find-Rscript)) {
    Write-Log "Downloading R $R_VERSION..."
    $rUrl = "https://cran.r-project.org/bin/windows/base/R-$R_VERSION-win.exe"
    $rTmp = "$TMP\R-$R_VERSION-win.exe"
    try {
        Invoke-WebRequest -Uri $rUrl -OutFile $rTmp -UseBasicParsing
        Write-Log "Installing R $R_VERSION (silent, all users)..."
        Start-Process -FilePath $rTmp -ArgumentList "/VERYSILENT", "/NORESTART", "/ALLUSERS" -Wait
        Remove-Item $rTmp -Force -ErrorAction SilentlyContinue
        Refresh-Path
        Write-Log "R installed."
    } catch {
        Write-Log "ERROR installing R: $_"
    }
} else {
    Write-Log "R already present — skipping."
}

# ── Quarto ───────────────────────────────────────────────────────────────────
$quartoCmd  = Get-Command quarto -ErrorAction SilentlyContinue
$quartoPath = if ($quartoCmd) { $quartoCmd.Source } else { $null }
if (-not $quartoPath) {
    Write-Log "Downloading Quarto $QUARTO_VERSION..."
    $qUrl = "https://github.com/quarto-dev/quarto-cli/releases/download/v$QUARTO_VERSION/quarto-$QUARTO_VERSION-win.msi"
    $qTmp = "$TMP\quarto-$QUARTO_VERSION.msi"
    try {
        Invoke-WebRequest -Uri $qUrl -OutFile $qTmp -UseBasicParsing
        Write-Log "Installing Quarto $QUARTO_VERSION (silent)..."
        Start-Process -FilePath msiexec -ArgumentList "/i", $qTmp, "/qn", "/norestart" -Wait
        Remove-Item $qTmp -Force -ErrorAction SilentlyContinue
        Refresh-Path
        Write-Log "Quarto installed."
    } catch {
        Write-Log "ERROR installing Quarto: $_"
    }
} else {
    Write-Log "Quarto already present — skipping."
}

# ── TinyTeX ──────────────────────────────────────────────────────────────────
# quarto install tinytex installs to the current user's (SYSTEM's) APPDATA.
# After install we locate the bin dir, grant other users read+execute access,
# and add it to the machine-wide PATH so regular users find tlmgr/pdflatex.
$tlmgr = Get-Command tlmgr -ErrorAction SilentlyContinue
if (-not $tlmgr) {
    Write-Log "Installing TinyTeX via Quarto..."
    try {
        & quarto install tinytex --no-prompt 2>&1 | ForEach-Object { Write-Log "  $_" }

        # Find where quarto put TinyTeX (varies by account)
        $tinyTexBin = $null
        $candidates = @(
            "$env:LOCALAPPDATA\TinyTeX\bin\windows",
            "$env:APPDATA\TinyTeX\bin\windows",
            "C:\Windows\system32\config\systemprofile\AppData\Local\TinyTeX\bin\windows",
            "C:\Windows\system32\config\systemprofile\AppData\Roaming\TinyTeX\bin\windows"
        )
        foreach ($c in $candidates) {
            if (Test-Path $c) { $tinyTexBin = $c; break }
        }

        if ($tinyTexBin) {
            Write-Log "TinyTeX found at: $tinyTexBin"
            $tinyTexRoot = Split-Path (Split-Path $tinyTexBin -Parent) -Parent

            # Grant all users read+execute so the binaries are usable system-wide
            Write-Log "Granting read+execute to Users on TinyTeX..."
            icacls $tinyTexRoot /grant "BUILTIN\Users:(OI)(CI)RX" /T /Q 2>&1 | Out-Null

            # Add TinyTeX bin to machine-wide PATH
            $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
            if ($machinePath -notlike "*$tinyTexBin*") {
                [System.Environment]::SetEnvironmentVariable("PATH", "$machinePath;$tinyTexBin", "Machine")
                Write-Log "TinyTeX added to system PATH."
            }
            $env:PATH = "$env:PATH;$tinyTexBin"
        } else {
            Write-Log "WARNING: TinyTeX bin dir not found after install."
        }
    } catch {
        Write-Log "ERROR installing TinyTeX: $_"
    }
} else {
    Write-Log "TinyTeX already present — skipping."
}

# ── LaTeX packages ────────────────────────────────────────────────────────────
$tlmgr = Get-Command tlmgr -ErrorAction SilentlyContinue
if ($tlmgr) {
    Write-Log "Installing LaTeX packages..."
    try {
        & tlmgr install @LATEX_PACKAGES 2>&1 | ForEach-Object { Write-Log "  $_" }
        Write-Log "LaTeX packages installed."
    } catch {
        Write-Log "ERROR installing LaTeX packages: $_"
    }
} else {
    Write-Log "WARNING: tlmgr not found — LaTeX packages skipped."
}

# ── R packages ───────────────────────────────────────────────────────────────
$rscript = Find-Rscript
if ($rscript) {
    Write-Log "Installing R packages into $R_LIB..."
    New-Item -ItemType Directory -Force -Path $R_LIB | Out-Null
    # Grant Users read access to the R library so the app can load packages
    icacls $R_LIB /grant "BUILTIN\Users:(OI)(CI)RX" /T /Q 2>&1 | Out-Null
    $pkgList = ($R_PACKAGES | ForEach-Object { '"' + $_ + '"' }) -join ", "
    try {
        & $rscript -e "install.packages(c($pkgList), lib='$R_LIB', repos='https://cloud.r-project.org', quiet=TRUE)" 2>&1 |
            ForEach-Object { Write-Log "  $_" }
        Write-Log "R packages installed."
    } catch {
        Write-Log "ERROR installing R packages: $_"
    }
} else {
    Write-Log "WARNING: Rscript not found — R packages not installed."
}

Write-Log "=== Dependency setup complete ==="

# Self-delete the scheduled task now that setup is done
Unregister-ScheduledTask -TaskName "ResilienceScanSetup" -Confirm:$false -ErrorAction SilentlyContinue
