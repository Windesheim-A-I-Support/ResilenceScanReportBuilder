#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Silently installs R, Quarto, TinyTeX and required R packages.
    Called by the NSIS installer at the end of installation.

.PARAMETER InstallDir
    Installation directory (default: $PSScriptRoot parent).
#>
param(
    [string]$InstallDir = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # suppress slow progress bars

$R_VERSION     = "4.3.2"
$QUARTO_VERSION = "1.6.39"
$R_LIB         = "$InstallDir\r-library"

$R_PACKAGES = @(
    "readr", "dplyr", "stringr", "tidyr", "ggplot2", "knitr",
    "fmsb", "scales", "viridis", "patchwork", "RColorBrewer",
    "gridExtra", "png", "lubridate", "kableExtra", "rmarkdown",
    "jsonlite", "ggrepel", "cowplot"
)

function Write-Log { param($msg) Write-Host "[SETUP] $msg" }

function Find-Rscript {
    $candidates = @(
        (Get-Command Rscript -ErrorAction SilentlyContinue)?.Source,
        "C:\Program Files\R\R-$R_VERSION\bin\Rscript.exe",
        "C:\Program Files\R\R-$R_VERSION\bin\x64\Rscript.exe"
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    # Try any installed R version
    $found = Get-ChildItem "C:\Program Files\R" -Filter "Rscript.exe" -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty FullName
    return $found
}

# ── R ────────────────────────────────────────────────────────────────────────
if (-not (Find-Rscript)) {
    Write-Log "Downloading R $R_VERSION..."
    $rUrl  = "https://cran.r-project.org/bin/windows/base/R-$R_VERSION-win.exe"
    $rTmp  = "$env:TEMP\R-$R_VERSION-win.exe"
    Invoke-WebRequest -Uri $rUrl -OutFile $rTmp -UseBasicParsing
    Write-Log "Installing R $R_VERSION (silent)..."
    Start-Process -FilePath $rTmp -ArgumentList "/VERYSILENT", "/NORESTART", "/ALLUSERS" -Wait
    Remove-Item $rTmp -Force -ErrorAction SilentlyContinue
} else {
    Write-Log "R already present — skipping."
}

# ── Quarto ───────────────────────────────────────────────────────────────────
$quartoPath = (Get-Command quarto -ErrorAction SilentlyContinue)?.Source
if (-not $quartoPath) {
    Write-Log "Downloading Quarto $QUARTO_VERSION..."
    $qUrl = "https://github.com/quarto-dev/quarto-cli/releases/download/v$QUARTO_VERSION/quarto-$QUARTO_VERSION-win.msi"
    $qTmp = "$env:TEMP\quarto-$QUARTO_VERSION.msi"
    Invoke-WebRequest -Uri $qUrl -OutFile $qTmp -UseBasicParsing
    Write-Log "Installing Quarto $QUARTO_VERSION (silent)..."
    Start-Process -FilePath msiexec -ArgumentList "/i", $qTmp, "/qn", "/norestart" -Wait
    Remove-Item $qTmp -Force -ErrorAction SilentlyContinue
    # Refresh PATH for this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
} else {
    Write-Log "Quarto already present — skipping."
}

# ── TinyTeX ──────────────────────────────────────────────────────────────────
if (-not (Get-Command tlmgr -ErrorAction SilentlyContinue)) {
    Write-Log "Installing TinyTeX via Quarto..."
    & quarto install tinytex --no-prompt 2>&1 | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Log "TinyTeX already present — skipping."
}

# ── R packages ───────────────────────────────────────────────────────────────
$rscript = Find-Rscript
if ($rscript) {
    Write-Log "Installing R packages into $R_LIB..."
    New-Item -ItemType Directory -Force -Path $R_LIB | Out-Null
    $pkgList = ($R_PACKAGES | ForEach-Object { '"' + $_ + '"' }) -join ", "
    & $rscript -e "install.packages(c($pkgList), lib='$R_LIB', repos='https://cloud.r-project.org', quiet=TRUE)" 2>&1 |
        ForEach-Object { Write-Host "  $_" }
    Write-Log "R packages installed."
} else {
    Write-Log "WARNING: Rscript not found — R packages not installed."
}

Write-Log "Dependency setup complete."
