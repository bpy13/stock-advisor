# Registers the news watcher task. It starts at user logon and again every 15 minutes if it is
# not running, runs `news_cli --watch` with no time limit, and restarts after a failure. A second
# instance never starts while one runs.
# Running this script again replaces the task instead of adding a second one.
$ErrorActionPreference = 'Stop'

$taskName = 'stock_advisor_news_watcher'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repoRoot 'scripts\run_watcher.ps1'

# Find the conda env's python at registration time; do not hard-code it.
$python = (& conda run -n stock_advisor python -c "import sys; print(sys.executable)" | Select-Object -Last 1).Trim()
if (-not (Test-Path $python)) { throw "Could not find the stock_advisor env python: '$python'" }

# The wrapper script appends the watcher output to data\cache\news\watcher_log.txt.
# conhost --headless: no window at all (powershell -WindowStyle Hidden still flashes one on Windows 11).
$arguments = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Python `"$python`""
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument $arguments -WorkingDirectory $repoRoot
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
# Repeat every 15 minutes, with no end: a watcher whose wrapper died starts again (it died on
# 2026-11-11 and nothing restarted it for six days). While the wrapper runs, IgnoreNew makes
# the repeat do nothing.
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)).Repetition
# Priority 4 = normal CPU and disk priority. The default 7 (below normal) starved the watcher's
# start-up for over 20 minutes while queue jobs used the CPU (2026-11-17).
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -Priority 4 `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description 'Watches news feeds and sends Telegram alerts for high-impact events.' `
    -Force | Out-Null
Write-Host "Registered '$taskName' (at logon of $user) using $python"
Write-Host "Log file: $(Join-Path $repoRoot 'data\cache\news\watcher_log.txt')"
Write-Host ''
Write-Host 'Start now:   Start-ScheduledTask -TaskName stock_advisor_news_watcher'
# Stop-ScheduledTask ends only the outer conhost; the wrapper and python under it keep running
# (seen 2026-11-17), so stop the wrapper's tree as well.
Write-Host 'Stop:        Stop-ScheduledTask -TaskName stock_advisor_news_watcher; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match ''run_watcher.ps1'' } | ForEach-Object { taskkill.exe /T /F /PID $_.ProcessId }'
Write-Host 'Remove:      Unregister-ScheduledTask -TaskName stock_advisor_news_watcher -Confirm:$false'
