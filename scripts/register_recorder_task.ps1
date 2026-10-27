# Registers the daily minute-recorder scheduled task (22:00 local, runs when logged on).
# Running this script again replaces the task instead of adding a second one.
$ErrorActionPreference = 'Stop'

$taskName = 'stock_advisor_minute_recorder'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\record_minutes.py'

# Find the conda env's python at registration time; do not hard-code it.
$python = (& conda run -n stock_advisor python -c "import sys; print(sys.executable)" | Select-Object -Last 1).Trim()
if (-not (Test-Path $python)) { throw "Could not find the stock_advisor env python: '$python'" }

# conhost --headless: python runs with no console window.
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument "--headless `"$python`" `"$script`"" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '22:00'
# StartWhenAvailable: a missed run happens at the next login.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Appends the latest 1m and 60m bars for news targets and holdings.' -Force | Out-Null
Write-Host "Registered '$taskName' (daily 22:00) using $python"
