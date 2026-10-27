# Starts the news watcher and appends its output to data\cache\news\watcher_log.txt.
# The scheduled task calls this script with the env python's path.
param([Parameter(Mandatory = $true)][string]$Python)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $repoRoot 'data\cache\news'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'watcher_log.txt'

Set-Location $repoRoot
# cmd does the redirect so the python stderr lines land in the log without PowerShell wrapping them.
cmd /c "`"$Python`" -m stock_advisor.news_cli --watch >> `"$log`" 2>&1"
exit $LASTEXITCODE
