@echo off
title Prometheus Frontend
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo Installing npm packages...
    npm install
    echo.
)

echo  Starting Next.js frontend...
echo  URL: http://localhost:3002
echo  Press Ctrl+C to stop.
echo.
npm run dev -- -p 3002
