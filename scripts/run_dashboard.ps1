# Runs the dashboard (streamlit run app.py) on a fixed port and starts it again whenever it stops.
# The scheduled task stock_advisor_dashboard (register_dashboard_task.ps1) calls this at boot.
# The port is fixed (default 8502) so bookmarks keep working: hk-estate's dashboard holds 8501,
# and without a fixed port Streamlit silently moves to the next free one.
# Starts and stops go to data\cache\dashboard_log.txt, Streamlit's own output to
# data\cache\dashboard_server_log.txt (both gitignored).
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [int]$Port = 8502
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logDir = Join-Path $repoRoot 'data\cache'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'dashboard_log.txt'
$serverLog = Join-Path $logDir 'dashboard_server_log.txt'
$env:PYTHONIOENCODING = 'utf-8'

Set-Location $repoRoot
while ($true) {
    Add-Content -Path $log -Value "$(Get-Date -Format s) starting on port $Port"
    # --server.headless: no browser tab and no first-run e-mail prompt (nobody is there to answer).
    # cmd does the redirect so the python stderr lines land in the log without PowerShell wrapping them.
    cmd /c "`"$Python`" -m streamlit run app.py --server.port $Port --server.headless true >> `"$serverLog`" 2>&1"
    Add-Content -Path $log -Value "$(Get-Date -Format s) stopped with code $LASTEXITCODE; restarting in 30 s"
    Start-Sleep -Seconds 30
}
