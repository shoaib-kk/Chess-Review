# Host the Player Twin feature locally (Windows).
#
# Starts two processes, each in its own window:
#   1. Player Modelling Engine  -> http://127.0.0.1:8000  (inline tasks, no Redis)
#   2. Vite frontend dev server -> http://localhost:5173
#
# The "Player Twin" tab in the frontend talks only to the engine on :8000, so
# these two are all you need to model a player and play their digital twin. The
# main review backend (:8001, requires PostgreSQL) is only needed for the other
# tabs and is intentionally not started here.
#
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File .\run_player_twin.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Create one and install deps:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv; .\.venv\Scripts\pip install -r player_model\requirements.txt"
    exit 1
}

Write-Host "Starting Player Modelling Engine on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process -FilePath $python -ArgumentList "-m", "player_model.run_local" -WorkingDirectory $root

if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Installing frontend dependencies (first run) ..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend"); npm install; Pop-Location
}

Write-Host "Starting frontend dev server on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $root "frontend")

Write-Host ""
Write-Host "Both processes launched in separate windows." -ForegroundColor Green
Write-Host "Open http://localhost:5173 and click the 'Player Twin' tab." -ForegroundColor Green
Write-Host "Close those windows (or Ctrl+C in them) to stop." -ForegroundColor Green
