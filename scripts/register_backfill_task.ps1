# Registers the daily news backfill task (02:00 local). Each run continues the backfill where
# it stopped; the script's lock file stops two runs from overlapping, and a run that finds
# every source complete only fetches the last few days.
# Running this script again replaces the task instead of adding a second one.
$ErrorActionPreference = 'Stop'

$taskName = 'stock_advisor_news_backfill'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\backfill_news.py'

# Find the conda env's python at registration time; do not hard-code it.
$python = (& conda run -n stock_advisor python -c "import sys; print(sys.executable)" | Select-Object -Last 1).Trim()
if (-not (Test-Path $python)) { throw "Could not find the stock_advisor env python: '$python'" }

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '02:00'
# StartWhenAvailable: a missed run happens at the next login. No time limit: a run can take hours.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Continues the news history backfill, then scores and clusters new items.' -Force | Out-Null
Write-Host "Registered '$taskName' (daily 02:00) using $python"
