@echo off
title TPA Poster Sender - Auto Setup & Launch
echo ========================================================
echo   Setting up and Launching TPA Poster Sender...
echo   (Installs Python & libraries automatically if missing)
echo ========================================================
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File run.ps1
pause
