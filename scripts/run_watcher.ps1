# Starts the news watcher and appends its output to data\cache\news\watcher_log.txt.
# The scheduled task calls this script with the env python's path.
param([Parameter(Mandatory = $true)][string]$Python)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $repoRoot 'data\cache\news'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'watcher_log.txt'

Set-Location $repoRoot
# Task Scheduler's restart-on-failure only covers a failed launch, not a crash mid-run, so this
# loop restarts the watcher itself after a non-zero exit. A clean exit (code 0) ends the loop.
while ($true) {
    # cmd does the redirect so the python stderr lines land in the log without PowerShell wrapping them.
    cmd /c "`"$Python`" -m stock_advisor.news_cli --watch >> `"$log`" 2>&1"
    $code = $LASTEXITCODE
    if ($code -eq 0) { exit 0 }
    Add-Content -Path $log -Value "$(Get-Date -Format s) watcher exited with code $code; restarting in 60 s"
    Start-Sleep -Seconds 60
}
