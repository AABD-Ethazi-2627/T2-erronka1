@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================================
echo   Iniciando Laneki IoT Dashboard y API Backend
echo ========================================================

echo [1/2] Iniciando API Backend (FastAPI)...
start "Laneki API (FastAPI)" ".\venv\Scripts\uvicorn.exe" main:app --reload --port 8000

echo [2/2] Iniciando Dashboard Web (Streamlit)...
start "Laneki Dashboard (Streamlit)" ".\venv\Scripts\streamlit.exe" run app.py

echo.
echo ========================================================
echo   Listo! Se han abierto las ventanas de los servidores:
echo   - Dashboard Web:  http://localhost:8501
echo   - Swagger API:    http://127.0.0.1:8000/docs
echo ========================================================
