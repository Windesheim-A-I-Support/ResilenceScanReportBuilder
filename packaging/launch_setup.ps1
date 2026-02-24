<#
.SYNOPSIS
    Registers a Task Scheduler task that runs setup_dependencies.ps1 as SYSTEM
    and starts it immediately. Called synchronously from the NSIS installer;
    returns in < 1 second.

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

Register-ScheduledTask -TaskName "ResilienceScanSetup" `
    -Action $action -Principal $principal -Settings $settings -Force | Out-Null

Start-ScheduledTask -TaskName "ResilienceScanSetup"

"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Task started. Monitor this file for progress." |
    Add-Content $logFile -Encoding UTF8

Write-Host "[SETUP] Background dependency setup started."
Write-Host "[SETUP] Monitor : $logFile"
Write-Host "[SETUP] Errors  : C:\ProgramData\ResilienceScan\setup_error.log"
