$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'No .venv found. Install uv and run uv sync, or create a Python venv and install the project.'
    }
    uv sync
}

Write-Host 'Starting ResQ API on http://127.0.0.1:8000'
& $venvPython -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
