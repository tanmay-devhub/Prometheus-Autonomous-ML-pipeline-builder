@echo off
setlocal EnableDelayedExpansion
title Prometheus Launcher

:: ROOT is the prometheus\ folder (where this file lives)
set "ROOT=%~dp0"
set "FRONT=%ROOT%frontend"

echo ============================================================
echo  Prometheus - Autonomous ML Pipeline Builder
echo ============================================================
echo.

:: ── Step 1: Check Docker ─────────────────────────────────────
echo [1/6] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Start Docker Desktop and re-run.
    pause
    exit /b 1
)
echo       Docker OK.
echo.

:: ── Step 2: Redis + MLflow ───────────────────────────────────
echo [2/6] Starting Redis and MLflow (docker-compose)...
cd /d "%ROOT%"
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] docker-compose failed. Check docker-compose.yml.
    pause
    exit /b 1
)
echo       Redis and MLflow started.
echo       MLflow UI: http://localhost:5000
echo.

:: ── Step 3: Ollama ───────────────────────────────────────────
echo [3/6] Checking Ollama...
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not detected. Starting in a new window...
    start "Ollama" cmd /k "ollama serve"
    timeout /t 5 /nobreak >nul
) else (
    echo       Ollama already running.
)
start /b "" cmd /c "ollama pull llama3.1:8b >nul 2>&1"
start /b "" cmd /c "ollama pull deepseek-coder:6.7b >nul 2>&1"
echo.

:: ── Step 4: Python dependencies ──────────────────────────────
echo [4/6] Installing Python dependencies...
cd /d "%ROOT%"
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo       Python dependencies installed.
echo.

:: ── Step 5: FastAPI backend + Celery ─────────────────────────
echo [5/6] Starting FastAPI backend and Celery worker...
start "Prometheus Backend" cmd /k "cd /d "%ROOT%" && set PYTHONPATH=%ROOT% && python -m uvicorn backend.main:app --reload --reload-dir backend --port 8000"
timeout /t 3 /nobreak >nul
start "Prometheus Celery" cmd /k "cd /d "%ROOT%" && set PYTHONPATH=%ROOT% && python -m celery -A backend.celery_app worker --loglevel=info --pool=solo"
echo       Backend:  http://localhost:8000
echo       API docs: http://localhost:8000/docs
echo.

:: ── Step 6: Next.js frontend ─────────────────────────────────
echo [6/6] Starting Next.js frontend...
cd /d "%FRONT%"
if not exist "node_modules" (
    echo       Running npm install (first time only)...
    npm install
)
start "Prometheus Frontend" cmd /k "cd /d "%FRONT%" && npm run dev -- --port 3002"
echo       Frontend: http://localhost:3002
echo.

echo ============================================================
echo  All services started!
echo.
echo   Frontend  ->  http://localhost:3002
echo   Backend   ->  http://localhost:8000
echo   API docs  ->  http://localhost:8000/docs
echo   MLflow    ->  http://localhost:5000
echo.
echo  Close the individual cmd windows to stop each service.
echo  To stop Redis + MLflow: cd to this folder, run: docker-compose down
echo ============================================================
echo.
pause
