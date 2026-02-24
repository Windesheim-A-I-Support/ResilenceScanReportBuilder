<#
.SYNOPSIS
    Silently installs R, Quarto, TinyTeX and required R/LaTeX packages.
    Runs as SYSTEM via Task Scheduler -- no UAC prompts, no execution-policy blocks.
    Progress is logged to C:\ProgramData\ResilienceScan\setup.log
    Full transcript (all output + errors) at C:\ProgramData\ResilienceScan\setup_transcript.log

.PARAMETER InstallDir
    Installation directory (default: directory containing this script).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

# PS 5.1 compatible -- do NOT use ?. null-conditional operator (PS 7+ only).
$ProgressPreference    = "SilentlyContinue"   # suppress slow progress bars
$ErrorActionPreference = "Continue"           # don't silently swallow errors

$LOG_DIR    = "C:\ProgramData\ResilienceScan"
$LOG_FILE   = "$LOG_DIR\setup.log"
$TRANSCRIPT = "$LOG_DIR\setup_transcript.log"
$ERROR_LOG  = "$LOG_DIR\setup_error.log"

# Ensure log directory exists before anything else
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

# Capture EVERYTHING (stdout + stderr + errors) to the transcript
Start-Transcript -Path $TRANSCRIPT -Append -Force | Out-Null

# Global trap: any terminating error writes to setup_error.log + setup.log
trap {
    $errMsg  = $_.Exception.Message
    $errStk  = $_.ScriptStackTrace
    $fatLine = "[FATAL $(Get-Date -Format 'HH:mm:ss')] Unhandled error: $errMsg"
    Write-Host $fatLine
    Add-Content -Path $ERROR_LOG -Value $fatLine           -Encoding UTF8
    Add-Content -Path $ERROR_LOG -Value $errStk            -Encoding UTF8
    Add-Content -Path $LOG_FILE  -Value $fatLine           -Encoding UTF8
    Add-Content -Path $LOG_FILE  -Value $errStk            -Encoding UTF8
    Stop-Transcript | Out-Null
    exit 1
}

$R_VERSION      = "4.3.2"
$QUARTO_VERSION = "1.6.39"
$R_LIB          = "$InstallDir\r-library"
$TMP            = "C:\Windows\Temp"        # reliable under SYSTEM account

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

# ---- Logging ----------------------------------------------------------------
function Write-Log {
    param($msg)
    $line = "[SETUP $(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

Write-Log "=== ResilienceScan dependency setup started (running as SYSTEM) ==="
Write-Log "InstallDir : $InstallDir"
Write-Log "R_LIB      : $R_LIB"
Write-Log "Transcript : $TRANSCRIPT"
Write-Log "PS version : $($PSVersionTable.PSVersion)"
Write-Log "Running as : $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

# ---- Helper: find Rscript.exe (PS 5.1 compatible -- no ?. operator) ---------
function Find-Rscript {
    $cmd      = Get-Command Rscript -ErrorAction SilentlyContinue
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
    $found = Get-ChildItem "C:\Program Files\R" -Filter "Rscript.exe" `
                 -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1 -ExpandProperty FullName
    return $found
}

function Refresh-Path {
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
}

# ---- R ----------------------------------------------------------------------
$rscriptBefore = Find-Rscript
if (-not $rscriptBefore) {
    Write-Log "Downloading R $R_VERSION..."
    # CRAN moves installers to /old/{ver}/ once a new minor series ships
    $rUrl = "https://cran.r-project.org/bin/windows/base/old/$R_VERSION/R-$R_VERSION-win.exe"
    $rTmp = "$TMP\R-$R_VERSION-win.exe"
    try {
        Write-Log "  URL: $rUrl"
        Invoke-WebRequest -Uri $rUrl -OutFile $rTmp -UseBasicParsing
        $sizeMB = [math]::Round((Get-Item $rTmp).Length / 1MB, 1)
        Write-Log "  Download complete ($sizeMB MB)"
        Write-Log "Installing R $R_VERSION (silent, all users)..."
        $proc = Start-Process -FilePath $rTmp `
                    -ArgumentList "/VERYSILENT", "/NORESTART", "/ALLUSERS" `
                    -Wait -PassThru
        Write-Log "  R installer exit code: $($proc.ExitCode)"
        Remove-Item $rTmp -Force -ErrorAction SilentlyContinue
        Refresh-Path
        $rAfter = Find-Rscript
        if ($rAfter) {
            Write-Log "R installed successfully: $rAfter"
        } else {
            Write-Log "WARNING: R installer finished but Rscript.exe not found - check exit code above."
        }
    } catch {
        $errMsg = $_.Exception.Message
        $errStk = $_.ScriptStackTrace
        Write-Log "ERROR installing R: $errMsg"
        Write-Log "  Stack: $errStk"
        Add-Content -Path $ERROR_LOG -Value "[R install] $errMsg"  -Encoding UTF8
        Add-Content -Path $ERROR_LOG -Value $errStk                -Encoding UTF8
    }
} else {
    Write-Log "R already present: $rscriptBefore - skipping."
}

# ---- Quarto -----------------------------------------------------------------
$quartoCmd  = Get-Command quarto -ErrorAction SilentlyContinue
$quartoPath = if ($quartoCmd) { $quartoCmd.Source } else { $null }
if (-not $quartoPath) {
    Write-Log "Downloading Quarto $QUARTO_VERSION..."
    $qUrl = "https://github.com/quarto-dev/quarto-cli/releases/download/v$QUARTO_VERSION/quarto-$QUARTO_VERSION-win.msi"
    $qTmp = "$TMP\quarto-$QUARTO_VERSION.msi"
    try {
        Write-Log "  URL: $qUrl"
        Invoke-WebRequest -Uri $qUrl -OutFile $qTmp -UseBasicParsing
        $sizeMB = [math]::Round((Get-Item $qTmp).Length / 1MB, 1)
        Write-Log "  Download complete ($sizeMB MB)"
        Write-Log "Installing Quarto $QUARTO_VERSION (silent)..."
        $proc = Start-Process -FilePath msiexec `
                    -ArgumentList "/i", $qTmp, "/qn", "/norestart" `
                    -Wait -PassThru
        Write-Log "  msiexec exit code: $($proc.ExitCode)"
        Remove-Item $qTmp -Force -ErrorAction SilentlyContinue
        Refresh-Path
        $quartoAfter = Get-Command quarto -ErrorAction SilentlyContinue
        if ($quartoAfter) {
            Write-Log "Quarto installed successfully: $($quartoAfter.Source)"
        } else {
            Write-Log "WARNING: Quarto installer finished but quarto not found on PATH."
        }
    } catch {
        $errMsg = $_.Exception.Message
        $errStk = $_.ScriptStackTrace
        Write-Log "ERROR installing Quarto: $errMsg"
        Write-Log "  Stack: $errStk"
        Add-Content -Path $ERROR_LOG -Value "[Quarto install] $errMsg" -Encoding UTF8
        Add-Content -Path $ERROR_LOG -Value $errStk                    -Encoding UTF8
    }
} else {
    Write-Log "Quarto already present: $quartoPath - skipping."
}

# ---- TinyTeX ----------------------------------------------------------------
# quarto install tinytex installs to the current user's (SYSTEM's) APPDATA.
# After install we locate the bin dir, grant other users read+execute access,
# and add it to the machine-wide PATH so regular users find tlmgr/pdflatex.
$tlmgr = Get-Command tlmgr -ErrorAction SilentlyContinue
if (-not $tlmgr) {
    Write-Log "Installing TinyTeX via Quarto..."
    try {
        & quarto install tinytex --no-prompt 2>&1 | ForEach-Object { Write-Log "  [quarto] $_" }

        # Find where quarto put TinyTeX (varies by account)
        $tinyTexBin = $null
        $candidates = @(
            "$env:LOCALAPPDATA\TinyTeX\bin\windows",
            "$env:APPDATA\TinyTeX\bin\windows",
            "C:\Windows\system32\config\systemprofile\AppData\Local\TinyTeX\bin\windows",
            "C:\Windows\system32\config\systemprofile\AppData\Roaming\TinyTeX\bin\windows"
        )
        Write-Log "Searching for TinyTeX bin directory..."
        foreach ($c in $candidates) {
            $exists = if (Test-Path $c) { "FOUND" } else { "not found" }
            Write-Log "  Checking: $c -- $exists"
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
                [System.Environment]::SetEnvironmentVariable(
                    "PATH", "$machinePath;$tinyTexBin", "Machine")
                Write-Log "TinyTeX added to system PATH."
            } else {
                Write-Log "TinyTeX already in system PATH."
            }
            $env:PATH = "$env:PATH;$tinyTexBin"
        } else {
            Write-Log "WARNING: TinyTeX bin dir not found after install - tlmgr will be unavailable."
        }
    } catch {
        $errMsg = $_.Exception.Message
        $errStk = $_.ScriptStackTrace
        Write-Log "ERROR installing TinyTeX: $errMsg"
        Write-Log "  Stack: $errStk"
        Add-Content -Path $ERROR_LOG -Value "[TinyTeX install] $errMsg" -Encoding UTF8
        Add-Content -Path $ERROR_LOG -Value $errStk                     -Encoding UTF8
    }
} else {
    Write-Log "TinyTeX already present: $($tlmgr.Source) - skipping."
}

# ---- LaTeX packages ---------------------------------------------------------
$tlmgr = Get-Command tlmgr -ErrorAction SilentlyContinue
if ($tlmgr) {
    Write-Log "Installing LaTeX packages via tlmgr: $($tlmgr.Source)"
    try {
        & tlmgr install @LATEX_PACKAGES 2>&1 | ForEach-Object { Write-Log "  [tlmgr] $_" }
        Write-Log "LaTeX packages installed."
    } catch {
        $errMsg = $_.Exception.Message
        $errStk = $_.ScriptStackTrace
        Write-Log "ERROR installing LaTeX packages: $errMsg"
        Write-Log "  Stack: $errStk"
        Add-Content -Path $ERROR_LOG -Value "[LaTeX packages] $errMsg" -Encoding UTF8
        Add-Content -Path $ERROR_LOG -Value $errStk                    -Encoding UTF8
    }
} else {
    Write-Log "WARNING: tlmgr not found - LaTeX packages skipped."
}

# ---- R packages -------------------------------------------------------------
$rscript = Find-Rscript
if ($rscript) {
    Write-Log "Installing R packages into $R_LIB (using $rscript)..."
    New-Item -ItemType Directory -Force -Path $R_LIB | Out-Null
    # Grant Users read access to the R library so the app can load packages
    icacls $R_LIB /grant "BUILTIN\Users:(OI)(CI)RX" /T /Q 2>&1 | Out-Null
    $pkgList = ($R_PACKAGES | ForEach-Object { '"' + $_ + '"' }) -join ", "
    try {
        & $rscript -e "install.packages(c($pkgList), lib='$R_LIB', repos='https://cloud.r-project.org', quiet=TRUE)" 2>&1 |
            ForEach-Object { Write-Log "  [R] $_" }
        Write-Log "R packages installed."
    } catch {
        $errMsg = $_.Exception.Message
        $errStk = $_.ScriptStackTrace
        Write-Log "ERROR installing R packages: $errMsg"
        Write-Log "  Stack: $errStk"
        Add-Content -Path $ERROR_LOG -Value "[R packages] $errMsg" -Encoding UTF8
        Add-Content -Path $ERROR_LOG -Value $errStk                -Encoding UTF8
    }
} else {
    Write-Log "WARNING: Rscript not found - R packages not installed."
}

Write-Log "=== Dependency setup complete ==="
Write-Log "Log files:"
Write-Log "  Main log   : $LOG_FILE"
Write-Log "  Transcript : $TRANSCRIPT"
Write-Log "  Error log  : $ERROR_LOG"

Stop-Transcript | Out-Null

# Self-delete the scheduled task now that setup is done
Unregister-ScheduledTask -TaskName "ResilienceScanSetup" -Confirm:$false -ErrorAction SilentlyContinue
