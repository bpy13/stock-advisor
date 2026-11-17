# Starts the news watcher and appends its output to data\cache\news\watcher_log.txt.
# The scheduled task calls this script with the env python's path.
#
# Two ways the watcher can stop, both seen (Task 5.2b, 2026-11-17):
# - dead: the watcher and this wrapper ended on 2026-11-11 without a line. The scheduled task's
#   15-minute repeat (register_watcher_task.ps1) starts this wrapper again; while it runs, the
#   repeat does nothing (MultipleInstances IgnoreNew).
# - stuck or starved: the watcher logs a "cycle:" line every poll (about once a minute), so a log
#   that has not grown for $QuietMinutes means it is stuck. This wrapper then kills it and starts
#   it again.
param(
    [Parameter(Mandatory = $true)][string]$Python,
    # Start-up (imports, models, opening the 6 GB store) logs little; leave it room.
    [int]$QuietMinutes = 30
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $repoRoot 'data\cache\news'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'watcher_log.txt'

function Write-WatcherLog([string]$text) {
    Add-Content -Path $log -Value "$(Get-Date -Format s) wrapper: $text"
}

# The size read through an open handle: the directory entry's size and time can lag while
# another process holds the file open for appending.
function Get-LogLength {
    $stream = [System.IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
    try { return $stream.Length } finally { $stream.Dispose() }
}

Set-Location $repoRoot
# Task Scheduler's restart-on-failure only covers a failed launch, not a crash mid-run, so this
# loop restarts the watcher itself after a non-zero exit. A clean exit (code 0) ends the loop.
while ($true) {
    # Written before python starts its heavy imports, so even a slow start leaves a line.
    Write-WatcherLog "starting the watcher (pid $PID; restarts it after $QuietMinutes quiet minutes)"
    # cmd does the redirect so the python stderr lines land in the log without PowerShell wrapping them.
    $proc = Start-Process -FilePath 'cmd.exe' -NoNewWindow -PassThru `
        -ArgumentList "/c `"`"$Python`" -m stock_advisor.news_cli --watch >> `"$log`" 2>&1`""
    $null = $proc.Handle  # keep a handle so ExitCode is readable after the exit
    $lastLength = Get-LogLength
    $lastGrowth = Get-Date
    $stuck = $false
    while (-not $proc.WaitForExit(60000)) {
        $length = Get-LogLength
        if ($length -ne $lastLength) {
            $lastLength = $length
            $lastGrowth = Get-Date
        } elseif (((Get-Date) - $lastGrowth).TotalMinutes -ge $QuietMinutes) {
            $stuck = $true
            & taskkill.exe /T /F /PID $proc.Id | Out-Null  # cmd and the python under it
            $proc.WaitForExit()
            break
        }
    }
    if ($stuck) {
        Write-WatcherLog "log quiet for $QuietMinutes minutes; killed the stuck watcher; restarting in 60 s"
    } else {
        $code = $proc.ExitCode
        if ($code -eq 0) { exit 0 }
        Write-WatcherLog "watcher exited with code $code; restarting in 60 s"
    }
    Start-Sleep -Seconds 60
}
