<#
.SYNOPSIS
    Registers a Task Scheduler task that runs setup_dependencies.ps1 as SYSTEM,
    starts it, then blocks until setup_complete.flag is written (or timeout).
    Called synchronously from the NSIS installer so the installer only shows
    "Installation Complete" once R/Quarto/TinyTeX are actually installed.

    Exit code: 0 = setup finished with PASS, 1 = setup finished with FAIL or timed out.

.PARAMETER InstallDir
    Installation directory (e.g. C:\Program Files\ResilenceScanReportBuilder).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

$logDir  = "C:\ProgramData\ResilienceScan"
$logFile = "$logDir\setup.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Registering background setup task (SYSTEM)..." |
    Set-Content $logFile -Encoding UTF8

$setupScript = Join-Path $InstallDir "_internal\setup_dependencies.ps1"

# Verify the script file exists before scheduling
if (-not (Test-Path $setupScript)) {
    "[LAUNCHER] ERROR: Script not found at: $setupScript" | Add-Content $logFile -Encoding UTF8
    "[LAUNCHER] Contents of InstallDir:" | Add-Content $logFile -Encoding UTF8
    (Get-ChildItem $InstallDir -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name) -join ", " |
        Add-Content $logFile -Encoding UTF8
    Write-Host "[SETUP] ERROR: Setup script not found. See $logFile"
    exit 1
}

"[LAUNCHER] Script found: $setupScript" | Add-Content $logFile -Encoding UTF8

# Use -EncodedCommand to avoid all quoting/space issues in the task argument.
# Wrap in try/catch so any error (parse, runtime) is written to setup_error.log.
$escapedScript  = $setupScript  -replace "'", "''"
$escapedInstDir = $InstallDir   -replace "'", "''"
$cmd = @"
try {
    & '$escapedScript' -InstallDir '$escapedInstDir'
} catch {
    `$msg = "[ERROR] `$(`$_.Exception.Message)`n`$(`$_.ScriptStackTrace)"
    `$msg | Out-File 'C:\ProgramData\ResilienceScan\setup_error.log' -Encoding UTF8 -Append
    `$msg | Add-Content 'C:\ProgramData\ResilienceScan\setup.log' -Encoding UTF8
}
"@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))

$psExe   = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$action  = New-ScheduledTaskAction `
    -Execute  $psExe `
    -Argument "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -EncodedCommand $encoded"

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest -LogonType ServiceAccount
$settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$flagFile = "$logDir\setup_complete.flag"

# Remove any stale flag from a previous run before starting the task.
# Without this, a previous FAIL flag is found instantly on the next run.
# Use a robust removal: try Remove-Item; if the file persists (e.g., SYSTEM
# owner with no delete permission), overwrite with a sentinel so the polling
# loop cannot mistake it for a completed run.
if (Test-Path $flagFile) {
    Remove-Item $flagFile -Force -ErrorAction SilentlyContinue
    if (Test-Path $flagFile) {
        # Removal failed (permission / lock) -- overwrite with STALE marker so
        # the polling loop does not treat it as a valid completion signal.
        "[LAUNCHER] WARNING: Could not delete stale flag -- overwriting with STALE marker." |
            Add-Content $logFile -Encoding UTF8
        "STALE" | Set-Content $flagFile -Encoding UTF8
    } else {
        "[LAUNCHER] Removed stale setup_complete.flag from previous run." |
            Add-Content $logFile -Encoding UTF8
    }
}

Register-ScheduledTask -TaskName "ResilienceScanSetup" `
    -Action $action -Principal $principal -Settings $settings -Force | Out-Null

Start-ScheduledTask -TaskName "ResilienceScanSetup"

"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Task started. Waiting for completion..." |
    Add-Content $logFile -Encoding UTF8

Write-Host "[SETUP] Dependency setup running - please wait (this may take 5-20 minutes)..."
Write-Host "[SETUP] Progress: $logFile"

# ------------------------------------------------------------------
# Block until setup_complete.flag is written by setup_dependencies.ps1.
# Timeout matches the Task Scheduler execution time limit (2 hours).
# ------------------------------------------------------------------
$timeoutSecs = 7200   # 2 hours
$pollSecs    = 5
$elapsed     = 0

:waitLoop while ($true) {
    if (Test-Path $flagFile) {
        $flagContent = (Get-Content $flagFile -Raw -ErrorAction SilentlyContinue) -replace '\s', ''
        # Skip STALE markers written by our own cleanup above; wait for a real result.
        if ($flagContent -match "PASS|FAIL") { break waitLoop }
    }
    Start-Sleep -Seconds $pollSecs
    $elapsed += $pollSecs
    if ($elapsed % 60 -eq 0) {
        Write-Host "[SETUP] Still running... ($([int]($elapsed/60)) min elapsed)"
    }
    if ($elapsed -ge $timeoutSecs) {
        "[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] TIMEOUT waiting for setup_complete.flag after $($timeoutSecs)s." |
            Add-Content $logFile -Encoding UTF8
        Write-Host "[SETUP] ERROR: Setup timed out after $([int]($timeoutSecs/60)) minutes."
        exit 1
    }
}

# Flag content already read inside the loop above
$flagContent = (Get-Content $flagFile -Raw -ErrorAction SilentlyContinue) -replace '\s', ''
"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Setup finished with result: $flagContent" |
    Add-Content $logFile -Encoding UTF8

if ($flagContent -match "PASS") {
    Write-Host "[SETUP] Dependency setup completed successfully."
    exit 0
} else {
    Write-Host "[SETUP] ERROR: Dependency setup finished with errors. Check $logFile"
    exit 1
}
