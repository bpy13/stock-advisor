# Registers the news watcher task. It starts at user logon, runs `news_cli --watch` with no time
# limit, and restarts after a failure. A second instance never starts while one runs.
# Running this script again replaces the task instead of adding a second one.
$ErrorActionPreference = 'Stop'

$taskName = 'stock_advisor_news_watcher'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repoRoot 'scripts\run_watcher.ps1'

# Find the conda env's python at registration time; do not hard-code it.
$python = (& conda run -n stock_advisor python -c "import sys; print(sys.executable)" | Select-Object -Last 1).Trim()
if (-not (Test-Path $python)) { throw "Could not find the stock_advisor env python: '$python'" }

# The wrapper script appends the watcher output to data\cache\news\watcher_log.txt.
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`" -Python `"$python`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $repoRoot
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description 'Watches news feeds and sends Telegram alerts for high-impact events.' `
    -Force | Out-Null
Write-Host "Registered '$taskName' (at logon of $user) using $python"
Write-Host "Log file: $(Join-Path $repoRoot 'data\cache\news\watcher_log.txt')"
Write-Host ''
Write-Host 'Start now:   Start-ScheduledTask -TaskName stock_advisor_news_watcher'
Write-Host 'Stop:        Stop-ScheduledTask -TaskName stock_advisor_news_watcher'
Write-Host 'Remove:      Unregister-ScheduledTask -TaskName stock_advisor_news_watcher -Confirm:$false'
