# Iniciar Laneki IoT Dashboard y API
Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Iniciando Laneki IoT Dashboard y API Backend" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Iniciar FastAPI
Write-Host "[1/2] Iniciando API Backend en http://127.0.0.1:8000 ..." -ForegroundColor Yellow
Start-Process -FilePath ".\venv\Scripts\uvicorn.exe" -ArgumentList "main:app --reload --port 8000"

# 2. Iniciar Streamlit Dashboard
Write-Host "[2/2] Iniciando Dashboard Web en http://localhost:8501 ..." -ForegroundColor Green
Start-Process -FilePath ".\venv\Scripts\streamlit.exe" -ArgumentList "run app.py"

Write-Host "`nListo! Se han abierto las ventanas de los servidores:" -ForegroundColor Cyan
Write-Host "  - Dashboard Web:  http://localhost:8501" -ForegroundColor Green
Write-Host "  - Swagger API:    http://127.0.0.1:8000/docs" -ForegroundColor Yellow
