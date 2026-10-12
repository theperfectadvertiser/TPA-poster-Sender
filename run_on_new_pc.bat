@echo off
title TPA Poster Sender - Auto Setup and Launch
echo ========================================================
echo   Setting up and Launching TPA Poster Sender...
echo   (Installs Python and libraries automatically if missing)
echo ========================================================
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File run.ps1
pause
