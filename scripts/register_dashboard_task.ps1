# Registers the dashboard task: `streamlit run app.py` on http://localhost:8502, started when the
# user logs on (career-search's pattern; no administrator rights needed). run_dashboard.ps1
# restarts Streamlit when it stops, and every 10 minutes Task Scheduler starts the task again if
# it is not running (only while logged on).
# Running this script again replaces the task instead of adding a second one.
param([int]$Port = 8502)
$ErrorActionPreference = 'Stop'

$taskName = 'stock_advisor_dashboard'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repoRoot 'scripts\run_dashboard.ps1'

# Find the conda env's python at registration time; do not hard-code it.
$python = (& conda run -n stock_advisor python -c "import sys; print(sys.executable)" | Select-Object -Last 1).Trim()
if (-not (Test-Path $python)) { throw "Could not find the stock_advisor env python: '$python'" }

# conhost --headless: no window at all (powershell -WindowStyle Hidden still flashes one on Windows 11).
$arguments = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Python `"$python`" -Port $Port"
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument $arguments -WorkingDirectory $repoRoot
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
$watchdog = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 3650)
# Priority 5 = normal: Task Scheduler's default 7 lets the backfill slow the pages down.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -Priority 5 `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($atLogon, $watchdog) -Settings $settings `
    -Principal $principal -Description "Stock Advisor dashboard on http://localhost:$Port, started at logon." `
    -Force | Out-Null
Write-Host "Registered '$taskName' (at logon, port $Port) using $python"
Write-Host "Log file: $(Join-Path $repoRoot 'data\cache\dashboard_log.txt')"
Write-Host 'Start now:   Start-ScheduledTask -TaskName stock_advisor_dashboard'
