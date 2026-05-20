@echo off
set "ROOT=%~dp0"
title Prometheus Launcher

echo ============================================================
echo  Prometheus v2 - Autonomous ML Pipeline Builder
echo ============================================================
echo.

:: ── [1] Docker ────────────────────────────────────────────────
echo [1/5] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Start Docker Desktop first.
    pause
    exit /b 1
)
docker-compose up -d
echo       Redis + MLflow started.
echo.

:: ── [2] Ollama ────────────────────────────────────────────────
echo [2/5] Checking Ollama...
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo [WARN] Starting Ollama...
    start "Ollama" cmd /k "python -m ollama serve"
    timeout /t 5 /nobreak >nul
) else (
    echo       Ollama already running.
)
echo.

:: ── [3] FastAPI backend ───────────────────────────────────────
echo [3/5] Starting backend (port 8000)...
cd /d "%ROOT%"
start "Prometheus Backend" cmd /k "set PYTHONPATH=%ROOT%&& python -m uvicorn main:app --port 8000 --reload"
timeout /t 3 /nobreak >nul
echo       API:  http://localhost:8000
echo       Docs: http://localhost:8000/docs
echo.

:: ── [4] Celery worker ─────────────────────────────────────────
echo [4/5] Starting Celery worker (classification + regression)...
start "Prometheus Celery" cmd /k "set PYTHONPATH=%ROOT%&& python -m celery -A celery_app worker --loglevel=info --pool=solo"
timeout /t 2 /nobreak >nul
echo.

:: ── [5] Frontend ──────────────────────────────────────────────
echo [5/5] Starting Next.js frontend...
start "Prometheus Frontend" "%ROOT%start_frontend.bat"

echo.
echo ============================================================
echo  All services starting!
echo.
echo   Frontend  ->  http://localhost:3000
echo   Backend   ->  http://localhost:8000
echo   API docs  ->  http://localhost:8000/docs
echo   MLflow    ->  http://localhost:5000
echo ============================================================
echo.
pause
