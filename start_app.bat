@echo off
title TPA Poster Sender
echo ========================================================
echo   Launching TPA Poster Sender (Local 100%% FREE Mode)
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run app.py
pause
