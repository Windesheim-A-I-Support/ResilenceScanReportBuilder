<#
.SYNOPSIS
    Registers a Task Scheduler task that runs setup_dependencies.ps1 as SYSTEM
    and starts it immediately. Called synchronously from the NSIS installer;
    returns in < 1 second. The heavy setup (R, Quarto, TinyTeX) runs in the
    background with full SYSTEM privileges — no UAC prompts needed.

.PARAMETER InstallDir
    Installation directory (default: directory containing this script).
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

$logDir  = "C:\ProgramData\ResilienceScan"
$logFile = "$logDir\setup.log"

# Create log dir and write first entry — this confirms the launcher ran.
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Registering background setup task (SYSTEM)..." |
    Set-Content $logFile -Encoding UTF8

$setupScript = Join-Path $InstallDir "_internal\setup_dependencies.ps1"

$action = New-ScheduledTaskAction `
    -Execute  "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File `"$setupScript`" -InstallDir `"$InstallDir`""

$principal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -RunLevel  Highest `
    -LogonType ServiceAccount

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "ResilienceScanSetup" `
    -Action   $action `
    -Principal $principal `
    -Settings  $settings `
    -Force | Out-Null

Start-ScheduledTask -TaskName "ResilienceScanSetup"

"[LAUNCHER $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Task started. Monitor this file for progress." |
    Add-Content $logFile -Encoding UTF8

Write-Host "[SETUP] Background dependency setup started."
Write-Host "[SETUP] Monitor: $logFile"
