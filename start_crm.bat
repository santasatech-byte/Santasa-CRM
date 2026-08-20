@echo off
title Santasa IVF CRM - Live Background Engine
echo ========================================================
echo   Starting Santasa IVF Hospital CRM (FastAPI + Vite)
echo ========================================================
echo.

cd /d "d:\Santasa IVF\CRM\hospital_crm\backend"
start "Santasa CRM Backend API (Port 8000)" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

cd /d "d:\Santasa IVF\CRM\hospital_crm\frontend"
start "Santasa CRM Frontend App (Port 3000)" cmd /k "npm run dev"

echo.
echo ========================================================
echo   [OK] CRM Servers are Running Permanently!
echo   - Local Desktop Access:  http://localhost:3000/
echo   - Mobile Wi-Fi Access:   http://pG.local:3000/
echo   - Mobile Sync Webhook:   http://pG.local:8000/api/v1/telephony/mobile-sync/call-log
echo ========================================================
echo.
pause
