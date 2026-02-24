<#
.SYNOPSIS
    Silently installs R, Quarto, TinyTeX and required R packages.
    Called by the NSIS installer at the end of installation.
    Runs in the background — progress logged to %ProgramData%\ResilienceScan\setup.log

.PARAMETER InstallDir
    Installation directory (default: directory containing this script).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

# PS 5.1 compatible — do NOT use ?. null-conditional operator (PS 7+ only)
$ProgressPreference = "SilentlyContinue"   # suppress slow progress bars

$R_VERSION      = "4.3.2"
$QUARTO_VERSION = "1.6.39"
$R_LIB          = "$InstallDir\r-library"
$LOG_DIR        = "$env:ProgramData\ResilienceScan"
$LOG_FILE       = "$LOG_DIR\setup.log"

$R_PACKAGES = @(
    "readr", "dplyr", "stringr", "tidyr", "ggplot2", "knitr",
    "fmsb", "scales", "viridis", "patchwork", "RColorBrewer",
    "gridExtra", "png", "lubridate", "kableExtra", "rmarkdown",
    "jsonlite", "ggrepel", "cowplot"
)

# ── Logging ──────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null
function Write-Log {
    param($msg)
    $line = "[SETUP $(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

Write-Log "=== ResilienceScan dependency setup started ==="
Write-Log "InstallDir: $InstallDir"
Write-Log "R_LIB:      $R_LIB"
Write-Log "Log:        $LOG_FILE"

# ── Helper: find Rscript.exe (PS 5.1 compatible) ─────────────────────────────
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
    # Try any installed R version
    $found = Get-ChildItem "C:\Program Files\R" -Filter "Rscript.exe" -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty FullName
    return $found
}

# ── R ────────────────────────────────────────────────────────────────────────
if (-not (Find-Rscript)) {
    Write-Log "Downloading R $R_VERSION..."
    $rUrl = "https://cran.r-project.org/bin/windows/base/R-$R_VERSION-win.exe"
    $rTmp = "$env:TEMP\R-$R_VERSION-win.exe"
    try {
        Invoke-WebRequest -Uri $rUrl -OutFile $rTmp -UseBasicParsing
        Write-Log "Installing R $R_VERSION (silent)..."
        Start-Process -FilePath $rTmp -ArgumentList "/VERYSILENT", "/NORESTART", "/ALLUSERS" -Wait
        Remove-Item $rTmp -Force -ErrorAction SilentlyContinue
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
    $qTmp = "$env:TEMP\quarto-$QUARTO_VERSION.msi"
    try {
        Invoke-WebRequest -Uri $qUrl -OutFile $qTmp -UseBasicParsing
        Write-Log "Installing Quarto $QUARTO_VERSION (silent)..."
        Start-Process -FilePath msiexec -ArgumentList "/i", $qTmp, "/qn", "/norestart" -Wait
        Remove-Item $qTmp -Force -ErrorAction SilentlyContinue
        # Refresh PATH so quarto is available for tinytex install
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        Write-Log "Quarto installed."
    } catch {
        Write-Log "ERROR installing Quarto: $_"
    }
} else {
    Write-Log "Quarto already present — skipping."
}

# ── TinyTeX ──────────────────────────────────────────────────────────────────
$tlmgr = Get-Command tlmgr -ErrorAction SilentlyContinue
if (-not $tlmgr) {
    Write-Log "Installing TinyTeX via Quarto..."
    try {
        & quarto install tinytex --no-prompt 2>&1 | ForEach-Object { Write-Log "  $_" }
        Write-Log "TinyTeX installed."
    } catch {
        Write-Log "ERROR installing TinyTeX: $_"
    }
} else {
    Write-Log "TinyTeX already present — skipping."
}

# ── R packages ───────────────────────────────────────────────────────────────
$rscript = Find-Rscript
if ($rscript) {
    Write-Log "Installing R packages into $R_LIB..."
    New-Item -ItemType Directory -Force -Path $R_LIB | Out-Null
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
