# Start the local prototype without exposing either server to the LAN.
$ErrorActionPreference = 'Stop'
$dashboardPython = if ($env:LANEKI_PYTHON) { $env:LANEKI_PYTHON } else { Join-Path $PSScriptRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $dashboardPython -PathType Leaf)) {
    throw 'Python environment missing. Follow README.md and set LANEKI_PYTHON.'
}
$dashboardLogs = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Force -Path $dashboardLogs | Out-Null
$dashboardStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $env:LANEKI_MODE) { $env:LANEKI_MODE = 'demo' }
$dashboardApi = Start-Process -FilePath $dashboardPython -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8001') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dashboardLogs "$dashboardStamp-api.out.log") -RedirectStandardError (Join-Path $dashboardLogs "$dashboardStamp-api.err.log") -PassThru
$dashboardUi = Start-Process -FilePath $dashboardPython -ArgumentList @('-m', 'streamlit', 'run', 'app.py', '--server.address', '127.0.0.1', '--server.port', '8501', '--server.headless', 'true') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dashboardLogs "$dashboardStamp-ui.out.log") -RedirectStandardError (Join-Path $dashboardLogs "$dashboardStamp-ui.err.log") -PassThru
@{ api = $dashboardApi.Id; dashboard = $dashboardUi.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dashboardLogs "$dashboardStamp-pids.json")
Write-Host "Prototipoa: http://127.0.0.1:8501; modua=$env:LANEKI_MODE"
Write-Host "Demo API: http://127.0.0.1:8001/docs; logs: $dashboardLogs"
