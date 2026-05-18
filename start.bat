@echo off
set "ROOT=%~dp0"
title Prometheus Launcher

echo ============================================================
echo  Prometheus - Autonomous ML Pipeline Builder
echo ============================================================
echo.

:: ── [1] Docker ────────────────────────────────────────────────
echo [1/6] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Start Docker Desktop first.
    pause
    exit /b 1
)
echo       Docker OK.
echo.

:: ── [2] Redis + MLflow ────────────────────────────────────────
echo [2/6] Starting Redis + MLflow...
cd /d "%ROOT%"
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] docker-compose failed. Check docker-compose.yml.
    pause
    exit /b 1
)
echo       MLflow UI: http://localhost:5000
echo.

:: ── [3] Ollama ────────────────────────────────────────────────
echo [3/6] Checking Ollama...
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama not running, starting it now...
    start "Ollama" cmd /k "ollama serve"
    timeout /t 5 /nobreak >nul
) else (
    echo       Ollama already running.
)
start /b "" cmd /c "ollama pull llama3.1:8b >nul 2>&1"
start /b "" cmd /c "ollama pull deepseek-coder:6.7b >nul 2>&1"
echo.

:: ── [4] Python dependencies ───────────────────────────────────
echo [4/6] Installing Python dependencies...
cd /d "%ROOT%"
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo       Python deps OK.
echo.

:: ── [5] FastAPI backend + Celery ─────────────────────────────
echo [5/6] Starting backend + Celery worker...
cd /d "%ROOT%"
start "Prometheus Backend" cmd /k "set PYTHONPATH=%ROOT%&& python -m uvicorn backend.main:app --reload --reload-dir backend --port 8000"
timeout /t 3 /nobreak >nul
start "Prometheus Celery"  cmd /k "set PYTHONPATH=%ROOT%&& python -m celery -A backend.celery_app worker --loglevel=info --pool=solo"
echo       Backend:  http://localhost:8000
echo       API docs: http://localhost:8000/docs
echo.

:: ── [6] Next.js frontend ─────────────────────────────────────
echo [6/6] Starting Next.js frontend...
start "Prometheus Frontend" "%ROOT%start_frontend.bat"
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
echo  To start ONLY the frontend, run: start_frontend.bat
echo  To stop Redis + MLflow:          docker-compose down
echo ============================================================
echo.
pause
